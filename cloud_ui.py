"""UI helpers for CleanMap cloud file storage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from cloud_storage import (
    CloudFile,
    CloudStorageBackend,
    friendly_cloud_error,
    guess_mime,
    read_source_bytes,
    user_can_delete_cloud_files,
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


def display_file_name(storage_name: str) -> str:
    """Strip the upload timestamp prefix from stored object names."""
    parts = storage_name.split("_", 2)
    if len(parts) == 3 and parts[0].isdigit() and len(parts[0]) == 8:
        return parts[2]
    if "_" in storage_name:
        return storage_name.split("_", 1)[-1]
    return storage_name


def _filename_from_source(source: Any, filename: str | None) -> str:
    if filename:
        return filename
    if isinstance(source, Path):
        return source.name
    name = getattr(source, "name", None)
    return str(name) if name else "upload.xlsx"


def mirror_workflow_file_to_cloud_once(
    cloud: CloudStorageBackend | None,
    username: str,
    category: str,
    dedupe_key: str,
    source: Any,
    *,
    filename: str | None = None,
) -> None:
    """Save a workflow upload to cloud once per dedupe_key (sidebar file list)."""
    if cloud is None or username == "local" or not dedupe_key:
        return
    state_key = f"cloud_sync:{category}:{dedupe_key}"
    if st.session_state.get(state_key):
        return
    fname = _filename_from_source(source, filename)
    try:
        if isinstance(source, Path):
            data = source.read_bytes()
        else:
            data = read_source_bytes(source)
        cloud.save_bytes(
            username,
            category,
            fname,
            data,
            content_type=guess_mime(fname),
        )
        st.session_state[state_key] = True
        st.session_state["cloud_last_action"] = "uploaded"
        st.session_state.pop("cloud_last_error", None)
    except Exception as exc:
        st.session_state["cloud_last_error"] = friendly_cloud_error(exc)


def mirror_bytes_to_cloud_once(
    cloud: CloudStorageBackend | None,
    username: str,
    category: str,
    dedupe_key: str,
    filename: str,
    data: bytes,
) -> None:
    if cloud is None or username == "local" or not dedupe_key or not data:
        return
    state_key = f"cloud_sync:{category}:{dedupe_key}"
    if st.session_state.get(state_key):
        return
    try:
        cloud.save_bytes(
            username,
            category,
            filename,
            data,
            content_type=guess_mime(filename),
        )
        st.session_state[state_key] = True
        st.session_state["cloud_last_action"] = "uploaded"
        st.session_state.pop("cloud_last_error", None)
    except Exception as exc:
        st.session_state["cloud_last_error"] = friendly_cloud_error(exc)


def handle_pending_cloud_delete(
    cloud: CloudStorageBackend | None,
    username: str,
) -> None:
    """Delete a cloud file after an admin clicks Delete (button callback order)."""
    if cloud is None:
        st.session_state.pop("cloud_pending_delete_path", None)
        return
    if not user_can_delete_cloud_files(username):
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


def _list_sidebar_files(cloud: CloudStorageBackend, username: str) -> list[CloudFile]:
    if user_can_delete_cloud_files(username) and hasattr(cloud, "list_entire_bucket"):
        return cloud.list_entire_bucket()
    return cloud.list_all_files(username)


def _cloud_path_owner(path: str) -> str | None:
    parts = path.replace("\\", "/").split("/")
    if not parts:
        return None
    if parts[0] == "cleanmap-files" and len(parts) >= 2:
        return parts[1]
    return parts[0]


def render_cloud_storage_setup_hint() -> None:
    st.divider()
    st.markdown("##### File bucket")
    st.info(
        "Finish cloud setup in Streamlit **Secrets**: `provider = \"bitbucket\"`, "
        "Bitbucket workspace/repo/username/API token (with repository read+write scopes). "
        "Delete old `supabase_url`, `supabase_key`, and `bucket` entries, then **Reboot** the app."
    )


def render_cloud_storage_sidebar(cloud: CloudStorageBackend, username: str) -> None:
    """Sidebar bucket: workflow uploads from computer are stored until an admin removes them."""
    st.divider()
    st.markdown("##### File bucket")
    st.caption(
        "Upload **from your computer** in the workflow only — no load-from-cloud. "
        "Each upload is saved here until an **admin** removes it."
    )
    if not user_can_delete_cloud_files(username):
        st.caption("You can download your files. Only admins can delete from the bucket.")

    last_action = st.session_state.pop("cloud_last_action", None)
    if last_action == "uploaded":
        st.success("File uploaded to cloud.")
    elif last_action == "deleted":
        st.success("File deleted from cloud.")
    cloud_error = st.session_state.pop("cloud_last_error", None)
    if cloud_error:
        st.error(f"Cloud action failed: {cloud_error}")

    try:
        files = _list_sidebar_files(cloud, username)
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

    is_admin = user_can_delete_cloud_files(username)
    for item in files:
        label = CATEGORY_LABELS.get(item.category, item.category)
        display_name = display_file_name(item.name)
        st.markdown(f"**{display_name}**")
        owner = _cloud_path_owner(item.path)
        meta = f"{label} · {item.name}"
        if is_admin and owner:
            meta = f"User **{owner}** · {meta}"
        st.caption(meta)

        if is_admin:
            action_cols = st.columns([1, 1])
        else:
            action_cols = st.columns([1])

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

        if is_admin and len(action_cols) > 1:
            with action_cols[1]:
                if st.button(
                    "Delete",
                    key=f"cloud_del_{item.path}",
                    use_container_width=True,
                    type="secondary",
                    help="Admin only — removes file from the bucket",
                ):
                    st.session_state["cloud_pending_delete_path"] = item.path
                    st.rerun()

        st.divider()


