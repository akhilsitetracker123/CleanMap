"""UI helpers for CleanMap cloud file storage."""

from __future__ import annotations

from typing import Any

import streamlit as st

from cloud_storage import CloudStorage, guess_mime, read_source_bytes

CLOUD_CATEGORIES = (
    ("uploads", "Main Excel"),
    ("lookups", "Lookup reference"),
    ("field_definitions", "Field definition"),
    ("outputs", "Cleansed output"),
)

CATEGORY_LABELS = dict(CLOUD_CATEGORIES)


def display_file_name(storage_name: str) -> str:
    """Strip the upload timestamp prefix from stored object names."""
    parts = storage_name.split("_", 2)
    if len(parts) == 3 and parts[0].isdigit() and len(parts[0]) == 8:
        return parts[2]
    if "_" in storage_name:
        return storage_name.split("_", 1)[-1]
    return storage_name


def handle_pending_cloud_delete(cloud: CloudStorage | None) -> None:
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


def render_cloud_storage_sidebar(cloud: CloudStorage, username: str) -> None:
    """Sidebar panel: upload files to cloud, browse all files, download, delete."""
    st.divider()
    if not st.toggle("Upload files to cloud", key="cloud_storage_open"):
        return

    st.caption("Store Excel files in your private cloud folder. This is separate from Step 1.")

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
                st.error(f"Upload failed: {exc}")

    last_action = st.session_state.pop("cloud_last_action", None)
    if last_action == "uploaded":
        st.success("File uploaded to cloud.")
    elif last_action == "deleted":
        st.success("File deleted from cloud.")
    cloud_error = st.session_state.pop("cloud_last_error", None)
    if cloud_error:
        st.error(f"Cloud action failed: {cloud_error}")

    st.markdown("##### All files in cloud")
    files = cloud.list_all_files(username)
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
    cloud: CloudStorage | None,
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
