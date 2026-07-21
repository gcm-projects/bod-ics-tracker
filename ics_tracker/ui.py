"""App shell: page config, the auth gate, navigation and shared sidebar chrome.

Page content lives in `ics_tracker.views`. Keeping the gate here means every
page is protected in one place — a page can never render before `require_login`
has run.
"""

import streamlit as st

from .auth import logout_control, require_login
from .config import LOGO_LIGHT
from .views import dashboard, ics_fs, non_ics_fs


def run():
    st.set_page_config(page_title="GCM FS Tracker",
                       page_icon="📊", layout="wide")
    require_login()  # gates EVERY page: nothing below runs until signed in

    # Branding above the page navigation (st.navigation pins the page list to
    # the top of the sidebar, so st.logo is the slot that sits above it).
    #
    # Always the COLOUR mark: st.logo takes one image, and st.context.theme is
    # documented as unreliable exactly when it matters — it "may be incorrect"
    # on first load and when the user switches theme (streamlit#11920). That
    # served the white mark on a light background, where it's invisible. The
    # colour mark stays legible on both. To use the white mark instead, pin the
    # theme in .streamlit/config.toml ([theme] base="dark") so it can't be wrong.
    st.logo(LOGO_LIGHT, size="large")

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
