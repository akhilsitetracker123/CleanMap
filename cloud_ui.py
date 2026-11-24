"""UI helpers for CleanMap cloud file storage."""

from __future__ import annotations

from typing import Any

import streamlit as st

from cloud_storage import (
    CloudFile,
    CloudStorageBackend,
    bytes_to_filelike,
    friendly_cloud_error,
    guess_mime,
    read_source_bytes,
)

CLOUD_CATEGORIES = (
    ("uploads", "Main Excel"),
    ("lookups", "Lookup reference"),
    ("field_definitions", "Field definition"),
    ("outputs", "Cleansed output"),
)

CATEGORY_LABELS = dict(CLOUD_CATEGORIES)


def workflow_cloud_enabled(cloud: CloudStorageBackend | None, username: str) -> bool:
    return cloud is not None and username != "local"


def cloud_file_label(item: CloudFile) -> str:
    return f"{display_file_name(item.name)} · {CATEGORY_LABELS.get(item.category, item.category)}"


def filter_lookup_cloud_files(files: list[CloudFile], object_name: str) -> list[CloudFile]:
    """Prefer lookup files named for this object (e.g. Account_...)."""
    needle = object_name.lower()
    prefixed = [f for f in files if f.name.lower().startswith(f"{needle}_")]
    if prefixed:
        return prefixed
    matched = [f for f in files if needle in f.name.lower()]
    return matched or files


def load_workflow_file_from_cloud(
    cloud: CloudStorageBackend,
    username: str,
    category: str,
    selectbox_key: str,
    *,
    object_name: str | None = None,
    empty_message: str | None = None,
) -> tuple[object | None, str | None]:
    """
    Show a cloud file dropdown and return (file-like source, cache key).
    """
    try:
        files = cloud.list_files(username, category)
    except Exception as exc:
        st.error(friendly_cloud_error(exc))
        return None, None

    if object_name and category == "lookups":
        files = filter_lookup_cloud_files(files, object_name)

    if not files:
        st.info(
            empty_message
            or "No matching files in cloud. Use sidebar **Upload files to cloud** first "
            f"(category: {CATEGORY_LABELS.get(category, category)})."
        )
        return None, None

    options = {cloud_file_label(item): item for item in files}
    labels = list(options.keys())
    selected_label = st.selectbox(
        "Choose from cloud",
        options=labels,
        key=selectbox_key,
    )
    item = options[selected_label]
    try:
        data = cloud.download_bytes(item.path)
    except Exception as exc:
        st.error(friendly_cloud_error(exc))
        return None, None

    display_name = display_file_name(item.name)
    source = bytes_to_filelike(data, display_name)
    st.success(f"Loaded from cloud: **{display_name}**")
    return source, f"cloud:{item.path}"


def display_file_name(storage_name: str) -> str:
    """Strip the upload timestamp prefix from stored object names."""
    parts = storage_name.split("_", 2)
    if len(parts) == 3 and parts[0].isdigit() and len(parts[0]) == 8:
        return parts[2]
    if "_" in storage_name:
        return storage_name.split("_", 1)[-1]
    return storage_name


def handle_pending_cloud_delete(cloud: CloudStorageBackend | None) -> None:
    """Delete a cloud file after the user clicks Delete (button callback order)."""
    if cloud is None:
        st.session_state.pop("cloud_pending_delete_path", None)
        return
    path = st.session_state.pop("cloud_pending_delete_path", None)
    if not path:
        return
    try:
        cloud.delete_file(path)
        st.session_state["cloud_last_action"] = "deleted"
    except Exception as exc:
        st.session_state["cloud_last_error"] = str(exc)
    st.rerun()


def render_cloud_storage_sidebar(cloud: CloudStorageBackend, username: str) -> None:
    """Sidebar panel: upload files to cloud, browse all files, download, delete."""
    st.divider()
    if not st.toggle("Upload files to cloud", key="cloud_storage_open"):
        return

    st.caption(
        "Store files here, or load saved files in Steps 1, 3, and 4 via **Load from cloud**."
    )

    category = st.selectbox(
        "File type",
        options=[key for key, _ in CLOUD_CATEGORIES],
        format_func=lambda key: CATEGORY_LABELS.get(key, key),
        key="cloud_upload_category",
    )
    upload_file = st.file_uploader(
        "Choose file",
        type=["xlsx", "xls"],
        key="cloud_sidebar_uploader",
    )

    if st.button("Upload to cloud", type="primary", use_container_width=True):
        if upload_file is None:
            st.warning("Choose a file first.")
        else:
            try:
                upload_file.seek(0)
                data = read_source_bytes(upload_file)
                cloud.save_bytes(
                    username,
                    category,
                    upload_file.name,
                    data,
                    content_type=guess_mime(upload_file.name),
                )
                st.session_state["cloud_last_action"] = "uploaded"
                st.session_state.pop("cloud_last_error", None)
                st.rerun()
            except Exception as exc:
                st.error(friendly_cloud_error(exc))

    last_action = st.session_state.pop("cloud_last_action", None)
    if last_action == "uploaded":
        st.success("File uploaded to cloud.")
    elif last_action == "deleted":
        st.success("File deleted from cloud.")
    cloud_error = st.session_state.pop("cloud_last_error", None)
    if cloud_error:
        st.error(f"Cloud action failed: {cloud_error}")

    st.markdown("##### All files in cloud")
    try:
        files = cloud.list_all_files(username)
    except Exception as exc:
        st.error(friendly_cloud_error(exc))
        st.caption(
            "Update secrets at share.streamlit.io → your app → Settings → Secrets, "
            "then redeploy. See CLOUD_SETUP.md in the GitHub repo."
        )
        return

    if not files:
        st.caption("No files in cloud yet.")
        return

    for item in files:
        label = CATEGORY_LABELS.get(item.category, item.category)
        display_name = display_file_name(item.name)
        st.markdown(f"**{display_name}**")
        st.caption(f"{label} · {item.name}")

        action_cols = st.columns([1, 1])
        with action_cols[0]:
            try:
                data = cloud.download_bytes(item.path)
                st.download_button(
                    "Download",
                    data=data,
                    file_name=display_name,
                    mime=guess_mime(display_name),
                    key=f"cloud_dl_{item.path}",
                    use_container_width=True,
                )
            except Exception as exc:
                st.caption(f"Error: {exc}")

        with action_cols[1]:
            if st.button(
                "Delete",
                key=f"cloud_del_{item.path}",
                use_container_width=True,
                type="secondary",
            ):
                st.session_state["cloud_pending_delete_path"] = item.path
                st.rerun()

        st.divider()


def save_output_to_cloud(
    cloud: CloudStorageBackend | None,
    username: str,
    filename: str,
    data: bytes,
) -> str | None:
    if cloud is None or username == "local":
        return None
    try:
        return cloud.save_bytes(username, "outputs", filename, data)
    except Exception as exc:
        st.warning(f"Could not save output to cloud: {exc}")
        return None
