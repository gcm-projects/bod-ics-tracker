"""App shell: page config, the auth gate, navigation and shared sidebar chrome.

Page content lives in `ics_tracker.views`. Keeping the gate here means every
page is protected in one place — a page can never render before `require_login`
has run.
"""

import streamlit as st

from .auth import logout_control, require_login
from .views import dashboard, ics_fs, non_ics_fs

# App branding shown ABOVE the page navigation. st.navigation always pins the
# page list to the top of the sidebar, so a plain st.sidebar.title() would land
# underneath it — st.logo is the supported slot for branding above the nav.
# Drawn as an inline SVG (bar-chart mark + wordmark) so it needs no asset file,
# in a violet that reads well on both light and dark themes.
_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="210" height="34"
     viewBox="0 0 210 34">
  <rect x="0"  y="14" width="6" height="14" rx="1.5" fill="#6366F1"/>
  <rect x="9"  y="8"  width="6" height="20" rx="1.5" fill="#8B5CF6"/>
  <rect x="18" y="18" width="6" height="10" rx="1.5" fill="#a78bfa"/>
  <text x="32" y="25" font-family="Segoe UI, Helvetica, Arial, sans-serif"
        font-size="18" font-weight="700" fill="#8B5CF6">GCM FS Tracker</text>
</svg>"""


def run():
    st.set_page_config(page_title="GCM FS Tracker",
                       page_icon="📊", layout="wide")
    require_login()  # gates EVERY page: nothing below runs until signed in

    # Branding above the page navigation (see _LOGO_SVG note).
    st.logo(_LOGO_SVG, size="large")

    # Explicit url_path per page: all three render functions share the name
    # `render`, so Streamlit can't derive distinct paths on its own.
    nav = st.navigation([
        st.Page(dashboard.render, title="Main Dashboard", icon="🏠",
                url_path="dashboard", default=True),
        st.Page(ics_fs.render, title="ICS FS Tracker", icon="📊",
                url_path="ics-fs-tracker"),
        st.Page(non_ics_fs.render, title="Non-ICS FS Tracker", icon="🗂️",
                url_path="non-ics-fs-tracker"),
    ])
    nav.run()

    # Signed-in caption + log out, last so it pins to the sidebar bottom-left.
    logout_control()
