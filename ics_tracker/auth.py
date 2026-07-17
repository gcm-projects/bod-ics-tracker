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
        _login_screen()
        st.stop()


def _login_screen():
    """A centred, lightly styled Microsoft sign-in screen.

    Button size comes from LAYOUT (a narrow centre column), not CSS, so it stays
    compact regardless of whether custom <style> targeting Streamlit's own
    elements applies in a given Streamlit version. The 'fancy' bits (hero icon,
    coloured title) use inline styles on our OWN markup, which apply reliably.
    """
    # Optional flourish: gradient + hover on the button. Harmless if the
    # selector doesn't match the running Streamlit version (button stays the
    # theme's primary colour, still compact thanks to the column below).
    st.markdown(
        "<style>div.stButton>button{"
        "background:linear-gradient(135deg,#6366F1,#8B5CF6)!important;"
        "color:#fff!important;border:none!important;border-radius:10px;"
        "font-weight:600;box-shadow:0 4px 14px rgba(99,102,241,.35);"
        "transition:transform .12s ease,box-shadow .12s ease}"
        "div.stButton>button:hover{transform:translateY(-2px);"
        "box-shadow:0 6px 20px rgba(99,102,241,.55)}</style>",
        unsafe_allow_html=True,
    )
    # Push the block toward the middle of the screen (inline height on our own
    # div — robust, no dependency on Streamlit container selectors).
    st.markdown("<div style='height:16vh'></div>", unsafe_allow_html=True)
    st.markdown(
        "<div style='text-align:center'>"
        "<div style='font-size:3.4rem;line-height:1'>📊</div>"
        "<h1 style='margin:.5rem 0 .2rem;font-weight:800;color:#a78bfa'>"
        "ICS FS Timeline Tracker</h1>"
        "<p style='color:gray;margin:0 0 1.4rem'>Please sign in with your "
        "Microsoft work account to continue.</p></div>",
        unsafe_allow_html=True)
    # Narrow centre column keeps the button small even without any CSS.
    _, bc, _ = st.columns([2, 1, 2])
    with bc:
        st.button("🔐 Log in with Microsoft", type="primary",
                  width="stretch", on_click=st.login)


def greeting():
    """First-name greeting for the main screen, or None when not signed in."""
    if not _auth_configured() or not getattr(st.user, "is_logged_in", False):
        return None
    name = (getattr(st.user, "name", None)
            or getattr(st.user, "email", "") or "").strip()
    first = name.split(" ")[0] if name else "there"
    return f"Hi, {first}! 👋🏼"


def logout_control():
    """Signed-in caption + logout button, pinned to the bottom of the sidebar.

    The bottom pin is best-effort flexbox; if the selector doesn't match the
    running Streamlit version, the block simply sits at the end of the sidebar.
    Call this AFTER all other sidebar content so it is the last element.
    """
    if not _auth_configured() or not getattr(st.user, "is_logged_in", False):
        return
    who = getattr(st.user, "name", None) or getattr(st.user, "email", "account")
    # Target ONLY this container via its deterministic `st-key-*` class, so just
    # the logout block is pinned to the bottom-left; the title + uploader stay
    # in normal flow at the top.
    st.sidebar.markdown(
        "<style>.st-key-ics_logout{position:fixed;bottom:1rem;z-index:100}</style>",
        unsafe_allow_html=True)
    with st.sidebar.container(key="ics_logout"):
        st.caption(f"Signed in as **{who}**")
        st.button("Log out", on_click=st.logout)
