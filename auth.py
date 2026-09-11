"""Username/password login for CleanMap (streamlit-authenticator)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Literal

import extra_streamlit_components as stx
import streamlit as st
import streamlit_authenticator as stauth

from ui_theme import APP_NAME, inject_theme

LOGOUT_MARKER_COOKIE = "cleanmap_logged_out"
COOKIE_MANAGER_KEY = "cleanmap_cookie_mgr"

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


def auth_is_configured() -> bool:
    try:
        return bool(st.secrets.get("auth", {}).get("credentials", {}).get("usernames"))
    except Exception:
        return False


def _build_credentials() -> dict[str, Any]:
    auth = st.secrets["auth"]
    usernames_raw = auth["credentials"]["usernames"]
    if hasattr(usernames_raw, "to_dict"):
        usernames_raw = usernames_raw.to_dict()

    usernames: dict[str, Any] = {}
    for username, user_data in dict(usernames_raw).items():
        if hasattr(user_data, "to_dict"):
            user_data = user_data.to_dict()
        elif not isinstance(user_data, dict):
            user_data = dict(user_data)
        usernames[str(username).strip()] = {
            "email": str(user_data.get("email", "")),
            "name": str(user_data.get("name", username)),
            "password": str(user_data.get("password", "")),
        }
    return {"usernames": usernames}


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


def _get_authenticator() -> stauth.Authenticate:
    """Build authenticator from secrets on every run (avoids stale cached passwords)."""
    _ensure_auth_session_keys()
    auth = st.secrets["auth"]
    return stauth.Authenticate(
        _build_credentials(),
        auth.get("cookie_name", "cleanmap_auth"),
        auth.get("cookie_key", "change_me"),
        float(auth.get("cookie_expiry_days", 30)),
        auto_hash=True,
    )


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

    authenticator = _get_authenticator()
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
    elif st.session_state.get("authentication_status") is None:
        st.caption("Enter the credentials provided by your admin.")


def clear_app_session_state() -> None:
    for key in APP_STATE_KEYS:
        st.session_state.pop(key, None)


def perform_logout() -> None:
    """Clear auth cookie/session and app workflow state."""
    _ensure_auth_session_keys()

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
