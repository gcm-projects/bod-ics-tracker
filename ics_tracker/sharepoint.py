"""Fetch the tracker workbook from SharePoint via the Microsoft Graph API.

App-only (client-credentials) auth. Requires an Entra app registration with the
Graph **application** permission ``Sites.Read.All`` (or ``Sites.Selected``
granted to the ResourceCenter site), admin-consented. Credentials live in the
``[sharepoint]`` secrets section — never in the repo.

Everything Graph-specific is isolated here; the rest of the app just calls
``fetch_workbook_bytes()`` and ``sharepoint_configured()``.
"""

from urllib.parse import quote

import httpx
import streamlit as st

from .config import SP_DRIVE_NAME, SP_FILE_PATH, SP_HOSTNAME, SP_SITE_PATH

GRAPH = "https://graph.microsoft.com/v1.0"
_TIMEOUT = 60


def sharepoint_configured():
    """True when [sharepoint] credentials are present in secrets."""
    try:
        return "sharepoint" in st.secrets
    except Exception:
        return False


def _access_token():
    """App-only access token via the client-credentials flow."""
    sp = st.secrets["sharepoint"]
    resp = httpx.post(
        f"https://login.microsoftonline.com/{sp['tenant_id']}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": sp["client_id"],
            "client_secret": sp["client_secret"],
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _graph_get(path, token, **kwargs):
    resp = httpx.get(
        f"{GRAPH}{path}", timeout=_TIMEOUT,
        headers={"Authorization": f"Bearer {token}"}, **kwargs)
    resp.raise_for_status()
    return resp


@st.cache_data(show_spinner="Loading tracker data from SharePoint…", ttl=600)
def fetch_workbook_bytes():
    """Download the tracker workbook's bytes from SharePoint (cached 10 min).

    Steps: token -> resolve site -> find the document library (drive) by name
    -> download the file's content by path within that drive.
    """
    token = _access_token()

    # 1. Resolve the site by hostname + server-relative path.
    site_id = _graph_get(f"/sites/{SP_HOSTNAME}:{SP_SITE_PATH}", token).json()["id"]

    # 2. Find the document library (drive) by its display name.
    drives = _graph_get(f"/sites/{site_id}/drives", token).json()["value"]
    drive = next((d for d in drives if d.get("name") == SP_DRIVE_NAME), None)
    if drive is None:
        available = ", ".join(repr(d.get("name")) for d in drives)
        raise RuntimeError(
            f"SharePoint library {SP_DRIVE_NAME!r} not found on this site. "
            f"Available libraries: {available}")

    # 3. Download the file content by path within the drive.
    path = quote(SP_FILE_PATH, safe="/")
    return _graph_get(f"/drives/{drive['id']}/root:/{path}:/content", token).content
