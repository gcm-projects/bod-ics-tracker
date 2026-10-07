"""Authentication (Microsoft Entra ID via st.login / st.user).

The gate is INERT until an [auth] section is added to secrets: deploy first
with no [auth] block and the app is open; add the secrets later and the gate
switches on automatically — no code change needed.
"""

import hmac
import html

import streamlit as st

# Only these email domains may use the app. Defence-in-depth on top of the
# single-tenant Entra registration: even if Azure is ever misconfigured
# (multi-tenant, guests, wrong metadata URL), non-org accounts are blocked
# here. Case-insensitive, exact-domain match.
ALLOWED_EMAIL_DOMAINS = ("global.ky",)

# Named external partners admitted by EXACT email (not whole domains) — so it is
# these specific people, not anyone at their firm. Their org accounts are invited
# into GCM's tenant as Entra B2B guests; here we match either the clean `email`
# claim or the encoded guest UPN (see _identifier_allowed). Lower-case.
ALLOWED_EMAILS = frozenset({
    "mhalsch@holmesmurphy.com",   # Holmes Murphy
    "jmcbain@yourcaptive.com",    # Your Captive
})

# Session-state flag marking an active external-access (shared-code) session.
_EXT_SESSION_KEY = "_external_access_label"


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


def _identifier_allowed(ident):
    """True if ONE identifier grants access: an internal org-domain account, or
    one of the named external guests (ALLOWED_EMAILS).

    B2B guest UPNs look like `mhalsch_holmesmurphy.com#EXT#@gcmtenant`. We never
    treat a #EXT# UPN as an org-domain account (that was the Gmail-guest bypass),
    but we DO admit the specific invited guests by comparing the UPN's encoded
    prefix to each allowlisted email (its '@' becomes '_'). That comparison is
    deterministic and can only ever equal the hardcoded list, so it can't widen
    access — and it works even if the tenant doesn't emit a clean `email` claim.
    """
    ident = str(ident or "").strip().lower()
    if "#ext#" in ident:
        prefix = ident.split("#ext#", 1)[0]
        return any(prefix == e.replace("@", "_") for e in ALLOWED_EMAILS)
    if ident in ALLOWED_EMAILS:                      # clean `email` claim match
        return True
    return ident.endswith(tuple(f"@{d.lower()}" for d in ALLOWED_EMAIL_DOMAINS))


def _email_allowed():
    """True if the signed-in user has an allowed internal or named-guest identity."""
    return any(_identifier_allowed(i) for i in _user_identifiers())


def require_login():
    """Block the app behind sign-in when auth is configured.

    Two ways past the gate: a Microsoft account on the allowed domain (or a named
    guest), OR a valid external access code — a code-gated path for invited
    external partners who aren't in GCM's Entra directory (see
    _external_signin_form).
    """
    if not _auth_configured():
        return  # auth not set up yet -> app stays open (deploy-first mode)
    # External partners: a shared-code session (validated at sign-in below).
    if st.session_state.get(_EXT_SESSION_KEY):
        return
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
    # External partner access (code-gated) — only renders when configured.
    _external_signin_form()


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


# --------------------------------------------------------------------------- #
# External partner access (shared access code)
# --------------------------------------------------------------------------- #
# A deliberately simple, OPT-IN path for a small number of invited external
# partners who aren't in GCM's Entra directory. It is NOT a public bypass: it
# requires a strong shared code stored server-side in the [external_access]
# secrets (never in the repo), handed to partners out of band. The control is
# absent entirely when that section is. Weaker than Microsoft sign-in (shared
# secret, no MFA, no per-user identity), so treat it as a temporary measure and
# rotate the code if it leaks.
def _external_codes():
    """{label: code} from the [external_access] secrets, or {} when unset/off."""
    try:
        if "external_access" not in st.secrets:
            return {}
        return {str(k): str(v)
                for k, v in dict(st.secrets["external_access"]).items()}
    except Exception:
        return {}


def _match_code(entered, codes):
    """The label whose code matches `entered` (constant-time), or None."""
    entered = (entered or "").strip()
    if not entered:
        return None
    for label, code in codes.items():
        if hmac.compare_digest(entered, str(code).strip()):
            return label
    return None


def _external_logout():
    """Clear an external-access session (callback for the Log out button)."""
    st.session_state.pop(_EXT_SESSION_KEY, None)


def _external_signin_form():
    """Code-gated 'External sign in' control on the login screen.

    Renders only when [external_access] codes are configured. A correct code
    starts an external session (kept in session_state for this browser session
    only); an empty/wrong code shows an error.
    """
    codes = _external_codes()
    if not codes:
        return
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        with st.expander("External sign in"):
            st.caption("For invited external partners only — enter your "
                       "access code.")
            with st.form("external_signin", clear_on_submit=True):
                code = st.text_input("Access code", type="password")
                submitted = st.form_submit_button("Sign in", type="primary")
            if submitted:
                label = _match_code(code, codes)
                if label:
                    st.session_state[_EXT_SESSION_KEY] = label
                    st.rerun()
                else:
                    st.error("Invalid access code.")


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
    if not _auth_configured():
        return
    ext = st.session_state.get(_EXT_SESSION_KEY)
    if not ext and not getattr(st.user, "is_logged_in", False):
        return
    if ext:
        who, on_click = f"{ext} (external)", _external_logout
    else:
        who = getattr(st.user, "name", None) or getattr(st.user, "email", "account")
        on_click = st.logout
    # Target ONLY this container via its deterministic `st-key-*` class, so just
    # the logout block is pinned to the bottom-left; the title + uploader stay
    # in normal flow at the top.
    st.sidebar.markdown(
        "<style>.st-key-ics_logout{position:fixed;bottom:1rem;z-index:100}</style>",
        unsafe_allow_html=True)
    with st.sidebar.container(key="ics_logout"):
        st.caption(f"Signed in as **{who}**")
        st.button("Log out", on_click=on_click)
