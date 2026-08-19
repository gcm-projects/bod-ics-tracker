"""Shared page helpers: the workbook loader used by the data-backed pages.

Both the ICS FS Tracker and the Dashboard need the tracker workbook. Keeping the
fetch here means one source-selection + loader + error path, used two ways:
the tracker page fails hard (``st.stop``); the Dashboard fails soft (returns
``None`` so its other content still renders).
"""

import streamlit as st

from ..auth import logout_control
from ..config import LOCAL_TRACKER_GLOB, newest_local
from ..data import load_data
from ..sharepoint import fetch_workbook_bytes, sharepoint_configured

# Purple full-height loading screen shown while the workbook is fetched/parsed.
# Self-contained HTML/CSS (own class + keyframes), so it renders reliably.
_LOADER_HTML = """
<div style="display:flex;flex-direction:column;align-items:center;
            justify-content:center;min-height:65vh;gap:1.2rem">
  <div class="ics-loader"></div>
  <div style="color:#a78bfa;font-weight:600;font-size:1.05rem">
    Loading tracker data…</div>
</div>
<style>
.ics-loader{width:60px;height:60px;border-radius:50%;
  border:6px solid rgba(139,92,246,.22);border-top-color:#8B5CF6;
  animation:ics-spin .8s linear infinite}
@keyframes ics-spin{to{transform:rotate(360deg)}}
</style>
"""


def load_frames(show_refresh=True, stop_on_error=True):
    """Fetch + parse the tracker workbook. Returns (year_end_df, valuation_df).

    SharePoint (via Microsoft Graph) is the primary source; a local file is the
    dev-only fallback used when [sharepoint] secrets aren't configured. Shows the
    purple loader while fetching.

    ``show_refresh`` adds a sidebar "Refresh data" button (forces a re-fetch).
    ``stop_on_error`` — when True, an error is shown and the script is stopped
    (the tracker page can't do anything without data); when False, ``None`` is
    returned so the caller can degrade gracefully (the Dashboard).
    """
    if show_refresh and sharepoint_configured() and st.sidebar.button("🔄 Refresh data"):
        fetch_workbook_bytes.clear()   # force a re-fetch from SharePoint
    loader = st.empty()
    loader.markdown(_LOADER_HTML, unsafe_allow_html=True)  # purple spinner
    try:
        if sharepoint_configured():
            frames = load_data(fetch_workbook_bytes())
        else:
            local = newest_local(LOCAL_TRACKER_GLOB)
            if not local:
                loader.empty()
                if not stop_on_error:
                    return None
                st.error("No data source configured. Add the [sharepoint] secrets "
                         "(or place a local workbook in data/ for dev).")
                logout_control()
                st.stop()
            frames = load_data(local)
    except Exception as e:
        loader.empty()
        if not stop_on_error:
            return None
        st.error(f"Couldn't load the tracker workbook: {e}")
        logout_control()
        st.stop()
    loader.empty()   # clear the loader once data is ready
    return frames
