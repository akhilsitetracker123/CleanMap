#!/usr/bin/env python3
"""Verify Bitbucket cloud credentials from .streamlit/secrets.toml (run locally)."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SECRETS = ROOT / ".streamlit" / "secrets.toml"


def main() -> int:
    if not SECRETS.is_file():
        print(f"Missing {SECRETS}")
        return 1

    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    cfg = tomllib.loads(SECRETS.read_text()).get("cloud") or {}
    workspace = cfg.get("bitbucket_workspace", "")
    repo = cfg.get("bitbucket_repo", "")
    user = cfg.get("bitbucket_username", "")
    secret = cfg.get("bitbucket_app_password", "")

    if not all([workspace, repo, user, secret]):
        print("Fill bitbucket_workspace, bitbucket_repo, bitbucket_username, bitbucket_app_password in secrets.toml")
        return 1

    if secret in ("REPLACE_APP_PASSWORD", "paste_bitbucket_api_token", "PASTE_BITBUCKET_API_TOKEN_HERE"):
        print(
            "bitbucket_app_password must be a Bitbucket API token (or App Password), "
            "not your login password."
        )
        return 1

    url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo}"
    r = httpx.get(url, auth=(user, secret), timeout=30.0)
    print(f"GET {url}")
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"OK — repo: {data.get('full_name')} (private={data.get('is_private')})")
        return 0
    if r.status_code == 401:
        print("Auth failed (401). Use Atlassian email + API token — not your login password.")
    elif r.status_code == 403:
        print(
            "Auth OK but token scopes are wrong (403). Admin/delete scopes do NOT include "
            "repository read/write."
        )
        try:
            detail = r.json().get("error", {}).get("detail", {})
            required = detail.get("required") or []
            granted = detail.get("granted") or []
            if required:
                print(f"  Required: {', '.join(required)}")
            if granted:
                print(f"  Granted:  {', '.join(granted)}")
        except Exception:
            pass
        print(
            "\nFix: create a NEW token at id.atlassian.com → Security → API tokens "
            "with scopes:\n"
            "  • read:repository:bitbucket\n"
            "  • write:repository:bitbucket\n"
            "(Optional: read:workspace:bitbucket, read:user:bitbucket)\n"
            "Do not rely on admin:repository / admin:workspace only."
        )
    else:
        print((r.text or "")[:500])
    if r.status_code not in (401, 403):
        return 1
    if r.status_code == 403:
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())