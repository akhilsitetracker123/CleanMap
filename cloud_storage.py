"""Supabase cloud storage for CleanMap uploads and outputs."""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import streamlit as st

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MIME_XLS = "application/vnd.ms-excel"


@dataclass
class CloudFile:
    name: str
    path: str
    category: str
    size: int | None
    updated_at: str | None


def cloud_is_configured() -> bool:
    try:
        cloud = st.secrets.get("cloud", {})
        return bool(
            cloud.get("enabled")
            and cloud.get("supabase_url")
            and cloud.get("supabase_key")
            and cloud.get("bucket")
        )
    except Exception:
        return False


_CLOUD_STORAGE_KEY = "cleanmap_cloud_storage"


def get_cloud_storage() -> "CloudStorage | None":
    if not cloud_is_configured():
        return None

    cached = st.session_state.get(_CLOUD_STORAGE_KEY)
    # Drop instances created before new methods were added (reload/dev deploy cache).
    if cached is not None and not hasattr(cached, "list_all_files"):
        del st.session_state[_CLOUD_STORAGE_KEY]
        cached = None

    if cached is None:
        cloud = st.secrets["cloud"]
        st.session_state[_CLOUD_STORAGE_KEY] = CloudStorage(
            url=str(cloud["supabase_url"]),
            key=str(cloud["supabase_key"]),
            bucket=str(cloud["bucket"]),
        )
    return st.session_state[_CLOUD_STORAGE_KEY]


class CloudStorage:
    def __init__(self, url: str, key: str, bucket: str) -> None:
        from supabase import create_client

        self.bucket = bucket
        self._client = create_client(url, key)

    def _user_prefix(self, username: str, category: str) -> str:
        safe_user = _safe_path_part(username)
        safe_category = _safe_path_part(category)
        return f"{safe_user}/{safe_category}"

    def save_bytes(
        self,
        username: str,
        category: str,
        filename: str,
        data: bytes,
        content_type: str = MIME_XLSX,
    ) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_name = _safe_path_part(filename)
        path = f"{self._user_prefix(username, category)}/{timestamp}_{safe_name}"
        self._client.storage.from_(self.bucket).upload(
            path,
            data,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return path

    def list_files(self, username: str, category: str | None = None) -> list[CloudFile]:
        prefix = _safe_path_part(username)
        if category:
            prefix = self._user_prefix(username, category)

        entries = self._client.storage.from_(self.bucket).list(prefix)
        files: list[CloudFile] = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", ""))
            if not name or name.endswith("/"):
                continue
            metadata = entry.get("metadata") or {}
            path = f"{prefix}/{name}" if not name.startswith(prefix) else name
            if category:
                file_category = category
            else:
                parts = path.split("/")
                file_category = parts[1] if len(parts) >= 2 else "files"
            files.append(
                CloudFile(
                    name=name,
                    path=path,
                    category=file_category,
                    size=_coerce_int(metadata.get("size")),
                    updated_at=str(metadata.get("lastModified") or entry.get("updated_at") or ""),
                )
            )
        files.sort(key=lambda item: item.name, reverse=True)
        return files

    def list_all_files(self, username: str) -> list[CloudFile]:
        files: list[CloudFile] = []
        for category in ("uploads", "lookups", "field_definitions", "outputs"):
            files.extend(self.list_files(username, category))
        files.sort(key=lambda item: item.name, reverse=True)
        return files

    def delete_file(self, path: str) -> None:
        self._client.storage.from_(self.bucket).remove([path])

    def download_bytes(self, path: str) -> bytes:
        return self._client.storage.from_(self.bucket).download(path)

    def create_signed_url(self, path: str, expires_seconds: int = 3600) -> str:
        result = self._client.storage.from_(self.bucket).create_signed_url(
            path, expires_seconds
        )
        if isinstance(result, dict):
            return str(result.get("signedURL") or result.get("signedUrl") or "")
        return str(result)


def read_source_bytes(source: Any) -> bytes:
    if isinstance(source, bytes):
        return source
    if isinstance(source, (str,)):
        return open(source, "rb").read()
    if hasattr(source, "read"):
        if hasattr(source, "seek"):
            source.seek(0)
        return source.read()
    raise TypeError(f"Unsupported file source type: {type(source)!r}")


def guess_mime(filename: str) -> str:
    if filename.lower().endswith(".xls"):
        return MIME_XLS
    return MIME_XLSX


def bytes_to_filelike(data: bytes) -> io.BytesIO:
    buffer = io.BytesIO(data)
    buffer.seek(0)
    return buffer


def _safe_path_part(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value.strip())
    return cleaned or "file"


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
