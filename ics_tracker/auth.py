"""Authentication (Microsoft Entra ID via st.login / st.user).

The gate is INERT until an [auth] section is added to secrets: deploy first
with no [auth] block and the app is open; add the secrets later and the gate
switches on automatically — no code change needed.
"""

import html

import streamlit as st

# Only these email domains may use the app. Defence-in-depth on top of the
# single-tenant Entra registration: even if Azure is ever misconfigured
# (multi-tenant, guests, wrong metadata URL), non-org accounts are blocked
# here. Case-insensitive, exact-domain match.
ALLOWED_EMAIL_DOMAINS = ("global.ky",)


def _auth_configured():
    """True only when an [auth] section is present in secrets."""
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def _user_identifiers():
    """Lower-cased email / UPN identifiers from the signed-in user's token."""
    ids = []
    for key in ("email", "preferred_username", "upn", "unique_name"):
        v = getattr(st.user, key, None)
        if v:
            ids.append(str(v).strip().lower())
    return ids


def _domain_ok(email):
    """True if one email/UPN is a clean org-domain account (not a B2B guest).

    B2B guest UPNs look like `user_gmail.com#EXT#@yourtenant` — if the tenant
    domain is the allowed one, that string would otherwise pass the endswith
    check, so guests are rejected explicitly via the #EXT# marker.
    """
    email = str(email or "").strip().lower()
    if "#ext#" in email:
        return False
    return email.endswith(tuple(f"@{d.lower()}" for d in ALLOWED_EMAIL_DOMAINS))


def _email_allowed():
    """True only if the signed-in user has an allowed org-domain identifier."""
    return any(_domain_ok(i) for i in _user_identifiers())


def require_login():
    """Block the app behind Microsoft sign-in when auth is configured."""
    if not _auth_configured():
        return  # auth not set up yet -> app stays open (deploy-first mode)
    # Fail closed: if login state is unavailable for any reason, require sign-in.
    if not getattr(st.user, "is_logged_in", False):
        _login_screen()
        st.stop()
    # Signed in — restrict to the organisation's email domain(s). Blocks Gmail
    # / personal / guest accounts even if the Entra config lets them through.
    if not _email_allowed():
        _access_denied_screen()
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


def _access_denied_screen():
    """Shown to a signed-in user whose email is outside the allowed domain(s)."""
    who = next(iter(_user_identifiers()), "your account")
    allowed = " / ".join(f"@{d}" for d in ALLOWED_EMAIL_DOMAINS)
    # Centre the whole block in the middle of the screen by pinning the keyed
    # container (deterministic st-key class) to the vertical centre.
    st.markdown(
        "<style>.st-key-denied_box{position:fixed;top:50%;left:0;right:0;"
        "transform:translateY(-50%)}</style>",
        unsafe_allow_html=True)
    with st.container(key="denied_box", horizontal_alignment="center"):
        st.markdown(
            "<div style='text-align:center'>"
            "<div style='font-size:3.4rem;line-height:1'>🚫</div>"
            "<h1 style='margin:.5rem 0 .3rem;font-weight:800;color:#ef4444'>"
            "Access restricted</h1>"
            "<p style='color:gray;margin:0 0 1.4rem'>"
            f"<b>{html.escape(who)}</b> isn't a Global Captive Management "
            f"({html.escape(allowed)}) account.<br>Please sign out and use your "
            "work account.</p></div>",
            unsafe_allow_html=True)
        st.button("Sign out", type="primary", on_click=st.logout)


def signed_in_name():
    """The signed-in user's display name, or '' when not signed in.

    Falls back to the email local part when no display name is present.
    """
    if not _auth_configured() or not getattr(st.user, "is_logged_in", False):
        return ""
    return (getattr(st.user, "name", None)
            or getattr(st.user, "email", "") or "").strip()


def first_name():
    """The signed-in user's first name, or '' when not signed in."""
    name = signed_in_name()
    return name.split(" ")[0] if name else ""


def greeting():
    """First-name greeting for the main screen, or None when not signed in."""
    first = first_name()
    return f"Hi, {first}! 👋🏼" if first else None


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
