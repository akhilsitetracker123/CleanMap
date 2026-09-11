"""UI helpers for CleanMap cloud file storage."""

from __future__ import annotations

import io
from typing import Any

import streamlit as st

from cloud_storage import CloudStorage, bytes_to_filelike, guess_mime, read_source_bytes

CLOUD_CATEGORIES = (
    ("uploads", "Main Excel uploads"),
    ("lookups", "Lookup reference files"),
    ("field_definitions", "Field definition files"),
    ("outputs", "Cleansed outputs"),
)


def render_cloud_files_panel(cloud: CloudStorage, username: str) -> None:
    st.markdown("##### My cloud files")
    st.caption("Files saved to your private cloud folder.")
    for category, label in CLOUD_CATEGORIES:
        files = cloud.list_files(username, category)
        with st.expander(f"{label} ({len(files)})", expanded=False):
            if not files:
                st.caption("No files yet.")
                continue
            for item in files[:20]:
                cols = st.columns([3, 1])
                with cols[0]:
                    st.text(item.name)
                with cols[1]:
                    try:
                        data = cloud.download_bytes(item.path)
                        st.download_button(
                            "Get",
                            data=data,
                            file_name=item.name.split("_", 1)[-1]
                            if "_" in item.name
                            else item.name,
                            mime=guess_mime(item.name),
                            key=f"cloud_dl_{item.path}",
                        )
                    except Exception as exc:
                        st.caption(f"Error: {exc}")


def resolve_main_file_from_cloud(
    cloud: CloudStorage,
    username: str,
) -> tuple[Any, str | None]:
    files = cloud.list_files(username, "uploads")
    if not files:
        st.info("No saved uploads yet. Upload a file below — it will be saved to the cloud.")
        return None, None

    labels = [file.name for file in files]
    selected_name = st.selectbox(
        "Select a saved upload",
        options=labels,
        key="cloud_main_file_select",
    )
    selected = next(file for file in files if file.name == selected_name)
    try:
        data = cloud.download_bytes(selected.path)
    except Exception as exc:
        st.error(f"Could not load cloud file: {exc}")
        return None, None
    st.success(f"Loaded from cloud: **{selected.name}**")
    return bytes_to_filelike(data), f"cloud:{selected.path}"


def save_uploaded_file_to_cloud(
    cloud: CloudStorage | None,
    username: str,
    category: str,
    source: Any,
    filename: str,
) -> str | None:
    if cloud is None or username == "local":
        return None
    try:
        data = read_source_bytes(source)
        path = cloud.save_bytes(
            username,
            category,
            filename,
            data,
            content_type=guess_mime(filename),
        )
        return path
    except Exception as exc:
        st.warning(f"Could not save {filename} to cloud: {exc}")
        return None


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
