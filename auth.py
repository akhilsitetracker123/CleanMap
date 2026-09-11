"""Username/password login for CleanMap (streamlit-authenticator)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Literal

import extra_streamlit_components as stx
import streamlit as st
import streamlit_authenticator as stauth

from ui_theme import APP_NAME, inject_theme

LOGOUT_MARKER_COOKIE = "cleanmap_logged_out"
COOKIE_MANAGER_KEY = "cleanmap_cookie_mgr"
AUTHENTICATOR_KEY = "cleanmap_authenticator"
AUTHENTICATOR_FP_KEY = "cleanmap_authenticator_fp"

APP_STATE_KEYS = (
    "validation_result",
    "file_key",
    "mandatory_columns",
    "mandatory_columns_select",
    "column_types",
    "lookup_tables",
    "lookup_stats",
    "field_definition",
    "cloud_saved_upload_key",
    "cloud_saved_output_key",
    "local_mode_confirmed",
)


def _to_plain_dict(value: Any) -> Any:
    """Convert Streamlit secrets AttrDict (and similar) to plain Python objects."""
    if value is None:
        return {}
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if isinstance(value, dict):
        return {str(key): _to_plain_dict(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain_dict(item) for item in value]
    return value


def auth_is_configured() -> bool:
    try:
        return bool(_build_credentials().get("usernames"))
    except Exception:
        return False


def configured_usernames() -> list[str]:
    """Return usernames defined in secrets (for safe login-page hints)."""
    try:
        return sorted(_build_credentials()["usernames"].keys())
    except Exception:
        return []


def _build_credentials() -> dict[str, Any]:
    auth = _to_plain_dict(st.secrets["auth"])
    credentials = _to_plain_dict(auth.get("credentials", {}))
    usernames_raw = credentials.get("usernames", {})
    if not isinstance(usernames_raw, dict):
        usernames_raw = _to_plain_dict(usernames_raw)

    usernames: dict[str, Any] = {}
    for username, user_data in usernames_raw.items():
        user_data = _to_plain_dict(user_data)
        password = str(user_data.get("password", "")).strip()
        usernames[str(username).strip().lower()] = {
            "email": str(user_data.get("email", "")).strip(),
            "name": str(user_data.get("name", username)).strip(),
            "password": password,
        }
    return {"usernames": usernames}


def _auth_secrets_fingerprint() -> str:
    """Hash auth secrets so cached authenticator refreshes after Cloud secret edits."""
    auth = _to_plain_dict(st.secrets.get("auth", {}))
    payload = {
        "cookie_name": auth.get("cookie_name"),
        "cookie_key": auth.get("cookie_key"),
        "cookie_expiry_days": auth.get("cookie_expiry_days"),
        "usernames": _build_credentials().get("usernames", {}),
    }
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _get_cookie_manager() -> stx.CookieManager:
    if COOKIE_MANAGER_KEY not in st.session_state:
        st.session_state[COOKIE_MANAGER_KEY] = stx.CookieManager(key="cleanmap_cookie_manager")
    return st.session_state[COOKIE_MANAGER_KEY]


def mount_cookie_manager() -> None:
    """Mount cookie manager in the app so browser cookies can be set/deleted."""
    _get_cookie_manager().get_all()


def _logout_marker_active() -> bool:
    try:
        return _get_cookie_manager().get(LOGOUT_MARKER_COOKIE) == "1"
    except Exception:
        return False


def _set_logout_marker() -> None:
    manager = _get_cookie_manager()
    manager.set(
        LOGOUT_MARKER_COOKIE,
        "1",
        expires_at=datetime.now() + timedelta(days=30),
    )


def _clear_logout_marker() -> None:
    try:
        _get_cookie_manager().delete(LOGOUT_MARKER_COOKIE)
    except Exception:
        pass


def _ensure_auth_session_keys() -> None:
    """Initialize keys required by streamlit-authenticator (must not be deleted)."""
    defaults = {
        "name": None,
        "authentication_status": None,
        "username": None,
        "email": None,
        "roles": None,
        "logout": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _invalidate_authenticator_cache() -> None:
    st.session_state.pop(AUTHENTICATOR_KEY, None)
    st.session_state.pop(AUTHENTICATOR_FP_KEY, None)


def _get_authenticator() -> stauth.Authenticate:
    """Return a single authenticator per session (library creates CookieManager key='init')."""
    _ensure_auth_session_keys()
    fingerprint = _auth_secrets_fingerprint()
    cached_fp = st.session_state.get(AUTHENTICATOR_FP_KEY)
    if AUTHENTICATOR_KEY in st.session_state and cached_fp != fingerprint:
        _invalidate_authenticator_cache()

    if AUTHENTICATOR_KEY in st.session_state:
        return st.session_state[AUTHENTICATOR_KEY]

    auth = _to_plain_dict(st.secrets["auth"])
    credentials = _build_credentials()
    if not credentials.get("usernames"):
        raise ValueError("No auth users found in secrets.")
    for username, user_data in credentials["usernames"].items():
        if not user_data.get("password"):
            raise ValueError(f"Missing password for auth user '{username}' in secrets.")

    authenticator = stauth.Authenticate(
        credentials,
        auth.get("cookie_name", "cleanmap_auth"),
        auth.get("cookie_key", "change_me"),
        float(auth.get("cookie_expiry_days", 30)),
        auto_hash=True,
    )
    # Reuse our cookie manager so streamlit-authenticator does not mount a second one.
    authenticator.cookie_controller.cookie_model.cookie_manager = _get_cookie_manager()
    st.session_state[AUTHENTICATOR_KEY] = authenticator
    st.session_state[AUTHENTICATOR_FP_KEY] = fingerprint
    return authenticator


def _try_restore_session_from_cookie() -> None:
    """Restore login from the browser cookie after a page refresh."""
    if not auth_is_configured():
        return
    if st.session_state.get("logout") or _logout_marker_active():
        return
    if st.session_state.get("authentication_status"):
        return
    authenticator = _get_authenticator()
    try:
        authenticator.login(location="unrendered", key="cleanmap_cookie_restore")
    except Exception:
        return


def get_authenticated_username() -> str | None:
    """Return logged-in username, or None if the user still needs to sign in."""
    if not auth_is_configured():
        if st.session_state.get("local_mode_confirmed"):
            return "local"
        return None

    if st.session_state.get("logout") or _logout_marker_active():
        return None

    _try_restore_session_from_cookie()

    if st.session_state.get("authentication_status"):
        username = st.session_state.get("username")
        return str(username) if username else None
    return None


def render_login_page() -> None:
    _ensure_auth_session_keys()
    inject_theme()
    st.markdown(
        f"""
        <div style="text-align:center;padding:2rem 0 1rem;">
            <h1 style="font-size:2.5rem;margin-bottom:0.25rem;">{APP_NAME}</h1>
            <p style="color:#A1A1A8;">Sign in to validate and store migration files in the cloud.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not auth_is_configured():
        st.warning(
            "Login is not configured yet. For local use, the app runs without sign-in. "
            "See **CLOUD_SETUP.md** to enable username/password and cloud storage."
        )
        if st.button("Continue without login (local only)", type="primary"):
            st.session_state["local_mode_confirmed"] = True
            st.rerun()
        return

    try:
        authenticator = _get_authenticator()
    except Exception as exc:
        st.error(f"Login is misconfigured in app secrets: {exc}")
        st.info(
            "In Streamlit Cloud, open **App settings → Secrets** and paste the full "
            "contents of your local `.streamlit/secrets.toml` (not the `.example` file). "
            "Save, wait for the app to redeploy, then hard-refresh this page."
        )
        return

    usernames = configured_usernames()
    st.caption(
        f"Sign in with your **username** (not email). "
        f"Configured account(s): {', '.join(f'`{name}`' for name in usernames) or 'none'}."
    )

    try:
        authenticator.login(
            location="main",
            fields={
                "Form name": APP_NAME,
                "Username": "Username",
                "Password": "Password",
                "Login": "Sign in",
            },
            key="cleanmap_login_main",
        )
    except Exception as exc:
        st.error(f"Login error: {exc}")
        return

    if st.session_state.get("authentication_status"):
        st.session_state["logout"] = None
        st.session_state.pop("cleanmap_pending_logout", None)
        _clear_logout_marker()
        st.rerun()

    if st.session_state.get("authentication_status") is False:
        st.error("Incorrect username or password.")
        st.caption(
            "Use the username shown above (e.g. `admin`), not your email. "
            "If you recently updated Streamlit Cloud secrets, save secrets, redeploy, "
            "then hard-refresh this page (Cmd/Ctrl+Shift+R)."
        )
    elif st.session_state.get("authentication_status") is None:
        st.caption("Enter the credentials provided by your admin.")


def clear_app_session_state() -> None:
    for key in APP_STATE_KEYS:
        st.session_state.pop(key, None)


def perform_logout() -> None:
    """Clear auth cookie/session and app workflow state."""
    _ensure_auth_session_keys()
    _invalidate_authenticator_cache()

    if auth_is_configured():
        authenticator = _get_authenticator()
        if st.session_state.get("authentication_status"):
            authenticator.authentication_controller.logout()
        else:
            st.session_state["authentication_status"] = None
            st.session_state["username"] = None
            st.session_state["name"] = None
            st.session_state["email"] = None
            st.session_state["roles"] = None
            st.session_state["logout"] = True
        _delete_auth_cookie(authenticator)
    else:
        st.session_state["authentication_status"] = None
        st.session_state["username"] = None
        st.session_state["name"] = None
        st.session_state["logout"] = True

    st.session_state["logout"] = True
    _set_logout_marker()
    clear_app_session_state()


def _delete_auth_cookie(authenticator: stauth.Authenticate) -> None:
    """Remove the remember-me cookie from the browser."""
    auth = st.secrets.get("auth", {})
    cookie_name = str(auth.get("cookie_name", "cleanmap_auth"))
    manager = _get_cookie_manager()
    try:
        manager.delete(cookie_name)
        manager.set(cookie_name, "", expires_at=datetime.now() - timedelta(days=1))
    except Exception:
        pass
    try:
        authenticator.cookie_controller.delete_cookie()
    except Exception:
        pass


def handle_pending_logout() -> None:
    """Run logout before auth checks (Streamlit button callback order)."""
    if st.session_state.pop("cleanmap_pending_logout", False):
        perform_logout()
        st.rerun()


def render_logout_button(
    location: Literal["sidebar", "header"] = "sidebar",
) -> None:
    """Show Log out and return to the sign-in page."""
    container = st.sidebar if location == "sidebar" else st

    if not auth_is_configured():
        if st.session_state.get("local_mode_confirmed"):
            if container.button(
                "Log out",
                key=f"cleanmap_logout_{location}_local",
                use_container_width=location == "sidebar",
            ):
                st.session_state["cleanmap_pending_logout"] = True
                st.rerun()
        return

    if not st.session_state.get("authentication_status"):
        return

    if location == "sidebar":
        container.divider()

    if container.button(
        "Log out",
        key=f"cleanmap_logout_{location}",
        use_container_width=location == "sidebar",
        type="secondary",
    ):
        st.session_state["cleanmap_pending_logout"] = True
        st.rerun()
