"""Authentication (Microsoft Entra ID via st.login / st.user).

The gate is INERT until an [auth] section is added to secrets: deploy first
with no [auth] block and the app is open; add the secrets later and the gate
switches on automatically — no code change needed.
"""

import streamlit as st


def _auth_configured():
    """True only when an [auth] section is present in secrets."""
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def require_login():
    """Block the app behind Microsoft sign-in when auth is configured."""
    if not _auth_configured():
        return  # auth not set up yet -> app stays open (deploy-first mode)
    # Fail closed: if login state is unavailable for any reason, require sign-in.
    if not getattr(st.user, "is_logged_in", False):
        st.title("📊 ICS FS Process Tracker")
        st.write("Please sign in with your Microsoft work account to continue.")
        st.button("🔐 Log in with Microsoft", type="primary", on_click=st.login)
        st.stop()


def logout_control():
    """Show who's signed in, plus a logout button (only when auth is on)."""
    if not _auth_configured() or not getattr(st.user, "is_logged_in", False):
        return
    who = getattr(st.user, "name", None) or getattr(st.user, "email", "account")
    st.sidebar.caption(f"Signed in as **{who}**")
    st.sidebar.button("Log out", on_click=st.logout)
