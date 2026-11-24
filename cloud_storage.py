"""Cloud file storage for CleanMap (Supabase or Bitbucket)."""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

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


class CloudStorageBackend(Protocol):
    bucket: str

    def save_bytes(
        self,
        username: str,
        category: str,
        filename: str,
        data: bytes,
        content_type: str = ...,
    ) -> str: ...

    def list_files(self, username: str, category: str | None = None) -> list[CloudFile]: ...

    def list_all_files(self, username: str) -> list[CloudFile]: ...

    def delete_file(self, path: str) -> None: ...

    def download_bytes(self, path: str) -> bytes: ...


def normalize_supabase_url(url: str) -> str:
    """Normalize Project URL from Supabase dashboard (Settings → API)."""
    cleaned = str(url).strip().strip('"').strip("'").rstrip("/")
    if cleaned and not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"
    return cleaned


def cloud_delete_admin_usernames() -> set[str]:
    """Usernames that may remove files from the cloud bucket (default: admin)."""
    try:
        cloud = st.secrets.get("cloud", {})
        admins = cloud.get("delete_admins")
        if isinstance(admins, (list, tuple)):
            names = {str(a).strip().lower() for a in admins if str(a).strip()}
            if names:
                return names
        if isinstance(admins, str) and admins.strip():
            return {admins.strip().lower()}
    except Exception:
        pass
    return {"admin"}


def user_can_delete_cloud_files(username: str) -> bool:
    return username.strip().lower() in cloud_delete_admin_usernames()


def _bitbucket_secrets_ready(cloud: dict) -> bool:
    return bool(
        cloud.get("bitbucket_workspace")
        and cloud.get("bitbucket_repo")
        and cloud.get("bitbucket_username")
        and cloud.get("bitbucket_app_password")
    )


def _supabase_secrets_ready(cloud: dict) -> bool:
    return bool(
        cloud.get("supabase_url")
        and cloud.get("supabase_key")
        and cloud.get("bucket")
    )


def cloud_provider() -> Literal["supabase", "bitbucket", "none"]:
    try:
        cloud = st.secrets.get("cloud", {})
        if not cloud.get("enabled"):
            return "none"
        explicit = str(cloud.get("provider", "")).strip().lower()
        if explicit == "bitbucket":
            return "bitbucket" if _bitbucket_secrets_ready(cloud) else "none"
        if explicit == "supabase":
            return "supabase" if _supabase_secrets_ready(cloud) else "none"
        # No provider set: use Bitbucket when configured. Leftover supabase_* keys are ignored
        # unless provider = "supabase" explicitly (avoids dead Supabase URLs on Streamlit Cloud).
        if _bitbucket_secrets_ready(cloud):
            return "bitbucket"
        return "none"
    except Exception:
        return "none"


def cloud_is_configured() -> bool:
    try:
        cloud = st.secrets.get("cloud", {})
        if not cloud.get("enabled"):
            return False
        provider = cloud_provider()
        if provider == "bitbucket":
            return _bitbucket_secrets_ready(cloud)
        if provider == "supabase":
            return _supabase_secrets_ready(cloud)
        return False
    except Exception:
        return False


_CLOUD_STORAGE_KEY = "cleanmap_cloud_storage"


def _cloud_config_fingerprint(cloud: dict) -> str:
    provider = cloud_provider()
    if provider == "bitbucket":
        return "|".join(
            [
                "bitbucket",
                str(cloud.get("bitbucket_workspace")),
                str(cloud.get("bitbucket_repo")),
                str(cloud.get("bitbucket_branch", "main")),
                str(cloud.get("bitbucket_root", "cleanmap-files")),
            ]
        )
    return "|".join(
        [
            "supabase",
            str(cloud.get("supabase_url")),
            str(cloud.get("bucket")),
        ]
    )


def cloud_storage_requested() -> bool:
    """True when [cloud] enabled=true in secrets (even if credentials are incomplete)."""
    try:
        return bool(st.secrets.get("cloud", {}).get("enabled"))
    except Exception:
        return False


def get_cloud_storage() -> CloudStorageBackend | None:
    if not cloud_is_configured():
        st.session_state.pop(_CLOUD_STORAGE_KEY, None)
        st.session_state.pop(f"{_CLOUD_STORAGE_KEY}_fp", None)
        return None

    cloud = st.secrets["cloud"]
    fingerprint = _cloud_config_fingerprint(cloud)
    cached = st.session_state.get(_CLOUD_STORAGE_KEY)
    cached_fp = st.session_state.get(f"{_CLOUD_STORAGE_KEY}_fp")

    if cached is not None and (
        not hasattr(cached, "list_all_files") or cached_fp != fingerprint
    ):
        del st.session_state[_CLOUD_STORAGE_KEY]
        cached = None

    if cached is None:
        if cloud_provider() == "bitbucket":
            from bitbucket_storage import BitbucketCloudStorage

            backend = BitbucketCloudStorage(
                workspace=str(cloud["bitbucket_workspace"]),
                repo=str(cloud["bitbucket_repo"]),
                branch=str(cloud.get("bitbucket_branch", "main")),
                root=str(cloud.get("bitbucket_root", "cleanmap-files")),
                api_username=str(cloud["bitbucket_username"]),
                app_password=str(cloud["bitbucket_app_password"]),
            )
        else:
            backend = SupabaseCloudStorage(
                url=normalize_supabase_url(str(cloud["supabase_url"])),
                key=str(cloud["supabase_key"]).strip(),
                bucket=str(cloud["bucket"]).strip(),
            )
        st.session_state[_CLOUD_STORAGE_KEY] = backend
        st.session_state[f"{_CLOUD_STORAGE_KEY}_fp"] = fingerprint
    return st.session_state[_CLOUD_STORAGE_KEY]


class SupabaseCloudStorage:
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

    def list_entire_bucket(self) -> list[CloudFile]:
        files: list[CloudFile] = []
        top = self._client.storage.from_(self.bucket).list("")
        for entry in top or []:
            if not isinstance(entry, dict):
                continue
            user_folder = str(entry.get("name", "")).rstrip("/")
            if not user_folder or user_folder == "/":
                continue
            files.extend(self._list_user_tree(user_folder))
        files.sort(key=lambda item: item.name, reverse=True)
        return files

    def _list_user_tree(self, user_folder: str) -> list[CloudFile]:
        files: list[CloudFile] = []
        for category in ("uploads", "lookups", "field_definitions", "outputs"):
            prefix = f"{user_folder}/{category}"
            entries = self._client.storage.from_(self.bucket).list(prefix)
            for entry in entries or []:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name", ""))
                if not name or name.endswith("/"):
                    continue
                metadata = entry.get("metadata") or {}
                path = f"{prefix}/{name}"
                files.append(
                    CloudFile(
                        name=name,
                        path=path,
                        category=category,
                        size=_coerce_int(metadata.get("size")),
                        updated_at=str(
                            metadata.get("lastModified") or entry.get("updated_at") or ""
                        ),
                    )
                )
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


# Backward-compatible alias
CloudStorage = SupabaseCloudStorage


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


def bytes_to_filelike(data: bytes, filename: str = "upload.xlsx") -> io.BytesIO:
    buffer = io.BytesIO(data)
    buffer.name = filename
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


def friendly_cloud_error(exc: Exception) -> str:
    """User-safe message for cloud storage failures (no secrets)."""
    name = type(exc).__name__
    text = str(exc).lower()
    provider = cloud_provider()

    if provider == "bitbucket":
        if "privilege scopes" in text or "required" in text and "granted" in text:
            return (
                "Bitbucket API token is missing **repository** scopes. Your token has admin/delete "
                "scopes only; CleanMap needs **read:repository:bitbucket** and "
                "**write:repository:bitbucket**. Create a new token at Atlassian → Security → "
                "API tokens and select those two repository scopes (not admin:repository alone)."
            )
        if "401" in text or "403" in text or "unauthorized" in text:
            return (
                "Bitbucket rejected credentials. Your **Bitbucket login password cannot be used** "
                "here — use a **Bitbucket API token** (recommended) or legacy App Password.\n\n"
                "- **bitbucket_username**: your Atlassian account **email** (e.g. the one on "
                "Bitbucket → Personal settings → Email aliases).\n"
                "- **bitbucket_app_password**: paste the **API token** only (create at "
                "Bitbucket → Personal settings → API tokens). Scopes: "
                "**read:repository:bitbucket** and **write:repository:bitbucket** (or "
                "equivalent Repository read/write). Token must have access to workspace "
                "**sitetraker** and repo **cleanmap-data**.\n\n"
                "If you still use an App Password (deprecated): set **bitbucket_username** to your "
                "Bitbucket **username** from Account settings — not your email."
            )
        if "404" in text:
            return (
                "Bitbucket repository or path not found. Verify **bitbucket_workspace**, "
                "**bitbucket_repo**, and **bitbucket_branch** in secrets."
            )
        if "connecterror" in name.lower() or "connect" in text:
            return "Could not connect to Bitbucket API (api.bitbucket.org)."
        return f"Bitbucket storage error ({name}). See CLOUD_SETUP.md."

    if "connecterror" in name.lower() or "connect" in text or "nodename" in text:
        return (
            "Could not connect to Supabase. Check that **supabase_url** in Streamlit "
            "Cloud secrets matches your active project (Supabase → Settings → API → "
            "Project URL). Paused or deleted projects will fail with this error.\n\n"
            "If you use **Bitbucket** for file storage instead, set `provider = \"bitbucket\"` "
            "under `[cloud]` and **remove** `supabase_url`, `supabase_key`, and `bucket` from "
            "secrets, then reboot the app."
        )
    if "401" in text or "unauthorized" in text or "invalid" in text and "api" in text:
        return (
            "Supabase rejected the API key. Use the **service_role** (secret) key in "
            "**supabase_key**, not the anon key."
        )
    if "404" in text or "bucket" in text or "not found" in text:
        return (
            "Storage bucket not found. Create a private bucket named **cleanmap-files** "
            "(or match the **bucket** value in secrets)."
        )
    return f"Cloud storage error ({name}). Check cloud provider settings in secrets."
