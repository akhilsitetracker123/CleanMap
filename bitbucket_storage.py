"""Bitbucket Git repository storage for CleanMap cloud files."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from cloud_storage import MIME_XLSX, CloudFile, _coerce_int, _safe_path_part

API_BASE = "https://api.bitbucket.org/2.0"
CLOUD_CATEGORIES = ("uploads", "lookups", "field_definitions", "outputs")


class BitbucketCloudStorage:
    """
    Store files in a Bitbucket repo path via the Source API (one commit per upload/delete).

    Use a dedicated repository (e.g. cleanmap-data), not the application source repo.
    """

    def __init__(
        self,
        workspace: str,
        repo: str,
        branch: str,
        root: str,
        api_username: str,
        app_password: str,
    ) -> None:
        self.workspace = workspace.strip()
        self.repo = repo.strip()
        self.branch = branch.strip() or "main"
        self.root = root.strip().strip("/") or "cleanmap-files"
        self.api_username = api_username.strip()
        self.app_password = app_password.strip()
        self.bucket = self.repo  # for error messages that mention bucket

    def _auth(self) -> tuple[str, str]:
        return self.api_username, self.app_password

    def _repo_slug_url(self) -> str:
        return f"{API_BASE}/repositories/{self.workspace}/{self.repo}"

    def _user_prefix(self, username: str, category: str) -> str:
        safe_user = _safe_path_part(username)
        safe_category = _safe_path_part(category)
        return f"{self.root}/{safe_user}/{safe_category}"

    def _request(
        self,
        method: str,
        url: str,
        *,
        timeout: float = 60.0,
        **kwargs: Any,
    ) -> httpx.Response:
        with httpx.Client(timeout=timeout) as client:
            response = client.request(method, url, auth=self._auth(), **kwargs)
        if response.status_code >= 400:
            text = response.text[:500]
            raise RuntimeError(f"Bitbucket API {response.status_code}: {text}")
        return response

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
        url = f"{self._repo_slug_url()}/src"
        self._request(
            "POST",
            url,
            data={
                "branch": self.branch,
                "message": f"CleanMap upload {path}",
            },
            files={path: (safe_name, data, content_type)},
        )
        return path

    def list_files(self, username: str, category: str | None = None) -> list[CloudFile]:
        safe_user = _safe_path_part(username)
        if category:
            dir_path = f"{self.root}/{safe_user}/{_safe_path_part(category)}"
            return self._list_directory(dir_path, category)

        files: list[CloudFile] = []
        for cat in CLOUD_CATEGORIES:
            dir_path = f"{self.root}/{safe_user}/{cat}"
            files.extend(self._list_directory(dir_path, cat))
        files.sort(key=lambda item: item.name, reverse=True)
        return files

    def _list_directory(self, dir_path: str, category: str) -> list[CloudFile]:
        encoded = "/".join(quote(part, safe="") for part in dir_path.split("/"))
        url = (
            f"{self._repo_slug_url()}/src/{quote(self.branch, safe='')}/{encoded}/"
            f"?format=flat&max_depth=2"
        )
        try:
            response = self._request("GET", url)
        except RuntimeError as exc:
            if "404" in str(exc):
                return []
            raise

        payload = response.json()
        files: list[CloudFile] = []
        for entry in payload.get("values") or []:
            if entry.get("type") != "commit_file":
                continue
            full_path = str(entry.get("path", ""))
            name = full_path.rsplit("/", 1)[-1]
            if not name:
                continue
            files.append(
                CloudFile(
                    name=name,
                    path=full_path,
                    category=category,
                    size=_coerce_int(entry.get("size")),
                    updated_at=None,
                )
            )
        files.sort(key=lambda item: item.name, reverse=True)
        return files

    def list_all_files(self, username: str) -> list[CloudFile]:
        return self.list_files(username, category=None)

    def list_entire_bucket(self) -> list[CloudFile]:
        """List all users' files under the storage root (for admin bucket view)."""
        encoded_root = quote(self.root, safe="")
        url = (
            f"{self._repo_slug_url()}/src/{quote(self.branch, safe='')}/{encoded_root}/"
            f"?format=flat&max_depth=4"
        )
        try:
            response = self._request("GET", url)
        except RuntimeError as exc:
            if "404" in str(exc):
                return []
            raise
        payload = response.json()
        files: list[CloudFile] = []
        root_prefix = f"{self.root}/"
        for entry in payload.get("values") or []:
            if entry.get("type") != "commit_file":
                continue
            full_path = str(entry.get("path", ""))
            if not full_path.startswith(root_prefix):
                continue
            rel = full_path[len(root_prefix) :]
            parts = rel.split("/")
            if len(parts) < 3:
                continue
            category = parts[1]
            if category not in CLOUD_CATEGORIES:
                continue
            name = full_path.rsplit("/", 1)[-1]
            if not name:
                continue
            files.append(
                CloudFile(
                    name=name,
                    path=full_path,
                    category=category,
                    size=_coerce_int(entry.get("size")),
                    updated_at=None,
                )
            )
        files.sort(key=lambda item: item.name, reverse=True)
        return files

    def delete_file(self, path: str) -> None:
        url = f"{self._repo_slug_url()}/src"
        # Empty file field deletes the path in Bitbucket's multipart commit API.
        self._request(
            "POST",
            url,
            data={
                "branch": self.branch,
                "message": f"CleanMap delete {path}",
            },
            files={path: ("", b"")},
        )

    def download_bytes(self, path: str) -> bytes:
        encoded = "/".join(quote(part, safe="") for part in path.split("/"))
        url = f"{self._repo_slug_url()}/src/{quote(self.branch, safe='')}/{encoded}"
        response = self._request("GET", url)
        return response.content