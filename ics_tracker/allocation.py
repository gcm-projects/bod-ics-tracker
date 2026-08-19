"""Client Allocation workbook: reviewer / management roles per client.

Loaded from a DIFFERENT SharePoint library than the tracker (see
``sharepoint.fetch_allocation_bytes``). It lets the dashboard show the
"Your preparations" / "Your board meetings" panels to First/Second reviewers
and management members, not just the owner.

The allocation's ``Company Name`` is reconciled to the tracker's ``Client Name``
— they're spelled inconsistently, so we normalise, then fall back to an explicit
alias map (``ALLOCATION_ALIASES``) for the few that still differ.
"""

import io
import re

import pandas as pd
import streamlit as st

from .config import (ALLOCATION_ALIASES, LOCAL_ALLOCATION_GLOB, ROLE_FIRST,
                     ROLE_MGMT, ROLE_OWNER, ROLE_SECOND, SP_ALLOC_SHEET,
                     newest_local)
from .sharepoint import fetch_allocation_bytes, sharepoint_configured

# Values that appear in a role cell but aren't a person to match a login against
# (e.g. the second review being handled by ICS, or a shared pool).
_NON_PERSON = {"", "-", "n/a", "na", "ics", "pool", "tbd", "tba", "none", "nan"}


def _people(cell):
    """Split a role cell into individual first names, dropping non-person markers.

    Cells can hold one name, or several joined by '/', ',', '&' or 'and'
    (e.g. "Alanna/Charlene").
    """
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return []
    parts = re.split(r"[\/,&]|\band\b", str(cell))
    return [p.strip() for p in parts
            if p.strip() and p.strip().lower() not in _NON_PERSON]


def _norm(name):
    """Normalise a company/client name for matching: lower, strip punctuation
    and the common '... Ltd/Inc/...' suffixes, collapse whitespace."""
    s = str(name).lower()
    s = re.sub(r"[.,()]", " ", s)
    s = re.sub(r"\b(ltd|inc|llc|spc|the|cayman)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


@st.cache_data(show_spinner=False, ttl=600)
def parse_allocation(file_source):
    """Return a tidy frame: Company Name + FirstReview/SecondReview/MgmtMembers
    (each a list of first names). ``file_source`` may be bytes or a path."""
    if isinstance(file_source, (bytes, bytearray)):
        file_source = io.BytesIO(file_source)
    df = pd.read_excel(file_source, sheet_name=SP_ALLOC_SHEET, header=1)
    df = df[df["Company Name"].notna()].copy()
    df["Company Name"] = df["Company Name"].astype(str).str.strip()
    df = df[df["Company Name"].str.len() > 1]

    def col(prefix):
        hit = next((c for c in df.columns
                    if str(c).strip().lower().startswith(prefix)), None)
        if hit is None:
            raise KeyError(f"Allocation sheet missing a {prefix!r} column")
        return hit

    fr, sr, mm = col("first review"), col("second review"), col("management member")
    return pd.DataFrame({
        "Company Name": df["Company Name"].values,
        "FirstReview": [_people(v) for v in df[fr]],
        "SecondReview": [_people(v) for v in df[sr]],
        "MgmtMembers": [_people(v) for v in df[mm]],
    })


def load_allocation():
    """Fetch + parse the allocation workbook, or None on any failure.

    Soft by design: the dashboard degrades to owner-only when this returns None
    (SharePoint down, no local file, unexpected layout, ...).
    """
    try:
        if sharepoint_configured():
            return parse_allocation(fetch_allocation_bytes())
        local = newest_local(LOCAL_ALLOCATION_GLOB)
        return parse_allocation(local) if local else None
    except Exception:
        return None


def roles_by_client(alloc_df, tracker_clients):
    """Map each tracker client to its allocation roles.

    Returns ({client: {ROLE_FIRST: [names], ROLE_SECOND: [...], ROLE_MGMT: [...]}},
    unmatched) where ``unmatched`` lists tracker clients with no allocation row.
    """
    by_norm, by_company = {}, {}
    for _, r in alloc_df.iterrows():
        by_company[r["Company Name"]] = r
        by_norm.setdefault(_norm(r["Company Name"]), r)

    out, unmatched = {}, []
    for client in tracker_clients:
        alias = ALLOCATION_ALIASES.get(client)
        row = by_company.get(alias) if alias else by_norm.get(_norm(client))
        if row is None:
            unmatched.append(client)
            continue
        out[client] = {ROLE_FIRST: list(row["FirstReview"]),
                       ROLE_SECOND: list(row["SecondReview"]),
                       ROLE_MGMT: list(row["MgmtMembers"])}
    return out, unmatched


def name_tokens(display_name):
    """Lower-cased word tokens of a display name (handles 'First Last' and
    'Last, First')."""
    return {t.strip(",.").lower() for t in str(display_name).split() if t.strip(",.")}


def clients_for_user(tokens, roles_bc, owner_by_client):
    """{client: set(role labels)} for every client this user touches.

    Matches the user's name tokens against the tracker Owner and the three
    allocation review roles (case-insensitive first-name match).
    """
    tokens = {t for t in tokens if t}
    result = {}
    for client, owner in owner_by_client.items():
        if str(owner).strip().lower() in tokens:
            result.setdefault(client, set()).add(ROLE_OWNER)
    for client, roles in roles_bc.items():
        for label, names in roles.items():
            if any(str(n).strip().lower() in tokens for n in names):
                result.setdefault(client, set()).add(label)
    return result


def known_people(alloc_df, owner_by_client):
    """Sorted set of all people who appear as an owner or a reviewer — used to
    validate the local ``?as=`` dev-preview name."""
    people = {str(o).strip() for o in owner_by_client.values()
              if str(o).strip() and str(o).strip().lower() != "nan"}
    if alloc_df is not None:
        for col in ("FirstReview", "SecondReview", "MgmtMembers"):
            for lst in alloc_df[col]:
                people.update(n.strip() for n in lst)
    return sorted(people)
