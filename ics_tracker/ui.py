"""App shell: page config, the auth gate, navigation and shared sidebar chrome.

Page content lives in `ics_tracker.views`. Keeping the gate here means every
page is protected in one place — a page can never render before `require_login`
has run.
"""

import streamlit as st

from .auth import logout_control, require_login
from .config import LOGO_DARK, LOGO_LIGHT
from .views import dashboard, ics_fs, non_ics_fs


def _logo_for_theme():
    """Pick the logo that reads against the viewer's current theme.

    st.logo takes a single image, so we choose per run: the white mark on dark
    themes, the colour mark on light. st.context.theme reflects the viewer's
    actual choice (including their toggle), and changing it triggers a rerun.
    Unknown theme falls back to the colour mark, which stays visible either way
    (a white mark would be invisible on a light background).
    """
    try:
        theme_type = st.context.theme.type
    except Exception:
        theme_type = None
    return LOGO_DARK if theme_type == "dark" else LOGO_LIGHT


def run():
    st.set_page_config(page_title="GCM FS Tracker",
                       page_icon="📊", layout="wide")
    require_login()  # gates EVERY page: nothing below runs until signed in

    # Branding above the page navigation (st.navigation pins the page list to
    # the top of the sidebar, so st.logo is the slot that sits above it).
    st.logo(_logo_for_theme(), size="large")

    # Explicit url_path per page: all three render functions share the name
    # `render`, so Streamlit can't derive distinct paths on its own.
    nav = st.navigation([
        st.Page(dashboard.render, title="Main Dashboard", icon="🏠",
                url_path="dashboard", default=True),
        st.Page(ics_fs.render, title="ICS FS Tracker", icon="📊",
                url_path="ics-fs-tracker"),
        st.Page(non_ics_fs.render, title="Non-ICS FS Tracker", icon="📈",
                url_path="non-ics-fs-tracker"),
    ])
    nav.run()

    # Signed-in caption + log out, last so it pins to the sidebar bottom-left.
    logout_control()
