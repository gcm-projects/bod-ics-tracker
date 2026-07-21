"""App shell: page config, the auth gate, navigation and shared sidebar chrome.

Page content lives in `ics_tracker.views`. Keeping the gate here means every
page is protected in one place — a page can never render before `require_login`
has run.
"""

import streamlit as st

from .auth import logout_control, require_login
from .views import dashboard, ics_fs, non_ics_fs


def run():
    st.set_page_config(page_title="ICS FS Timeline Tracker",
                       page_icon="📊", layout="wide")
    require_login()  # gates EVERY page: nothing below runs until signed in

    st.sidebar.title("📊 ICS FS Tracker")

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
