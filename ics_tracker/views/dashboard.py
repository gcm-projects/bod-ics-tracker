"""Main Dashboard: personalised greeting and entry point to the trackers."""

import streamlit as st

from ..auth import greeting


def render():
    hello = greeting()
    if hello:
        st.markdown(f"## {hello}")
    st.caption("Welcome to the GCM financial-statement trackers.")

    st.markdown("---")
    st.subheader("Dashboard data coming soon")

    left, right = st.columns(2)
    with left:
        st.subheader("📊 ICS FS Tracker")
        st.write(
            "Live timeline of GCM's preparation windows per client, with board "
            "meeting dates, audit and assessment deadlines")
    with right:
        st.subheader("📈 Non-ICS FS Tracker")
        st.write("Not available yet — coming soon.")

    st.info("Use the navigation on the left to open a tracker.")
