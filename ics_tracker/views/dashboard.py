"""Main Dashboard: personalised greeting, the signed-in user's preparations and
board meetings (as owner OR reviewer / management member), and the entry points
to the trackers."""

import pandas as pd
import streamlit as st

from ..allocation import (clients_for_user, known_people, load_allocation,
                          name_tokens, roles_by_client)
from ..auth import greeting, signed_in_name
from ..config import (PREP_VAL_1, PREP_VAL_2, PREP_YEAR_END, ROLE_ORDER)
from ..model import build_blocks, build_preparations
from ..sharepoint import sharepoint_configured
from ._shared import load_frames


def render():
    hello = greeting()
    if hello:
        st.markdown(f"## {hello}")
    st.caption("Welcome to the GCM financial-statement trackers.")

    # Load the tracker once and feed every data-backed section below.
    frames = load_frames(show_refresh=False, stop_on_error=False)
    if frames is None:
        st.warning("Couldn't load the tracker data right now — open the ICS FS "
                   "Tracker to retry, or try again shortly.")
    else:
        preps = build_preparations(*frames)
        blocks = build_blocks(preps)
        _my_dashboard(preps, blocks)

    st.markdown("---")
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


def _dev_person_request():
    """The raw ?as= (or legacy ?owner=) value — a LOCAL-DEV-ONLY impersonation
    hook. Honoured only when [sharepoint] is absent, so it can never take effect
    on the deployed app. Returns '' otherwise."""
    if sharepoint_configured():
        return ""
    q = st.query_params
    return (q.get("as", "") or q.get("owner", "")).strip()


def _role_str(roles):
    """Ordered, comma-joined role labels for a client (Owner first)."""
    if not roles:
        return "—"
    return ", ".join(r for r in ROLE_ORDER if r in roles)


def _my_dashboard(preps, blocks):
    """Resolve the viewer's clients (owner + reviewer roles), then render their
    preparations and board meetings."""
    owner_by_client = (preps.groupby("Client")["Owner"].first().to_dict()
                       if not preps.empty else {})
    tracker_clients = sorted(owner_by_client)

    alloc = load_allocation()            # None on failure -> owner-only (soft)
    roles_bc, unmatched = (roles_by_client(alloc, tracker_clients)
                           if alloc is not None else ({}, []))

    # Who is viewing? In local dev, ?as=<name> impersonates anyone; otherwise
    # it's the signed-in user, matched against Owner + the three review roles.
    dev_req = _dev_person_request()
    if dev_req:
        known = known_people(alloc, owner_by_client)
        match = next((p for p in known if p.lower() == dev_req.lower()), None)
        if match is None:
            st.subheader("Your preparations")
            st.warning(f"Dev preview: no one named '{dev_req}'. "
                       f"Try one of: {', '.join(known) or '(none)'}.")
            return
        tokens = {match.lower()}
        st.caption(f"🔧 Dev preview — viewing as **{match}** (via ?as=; local only).")
    else:
        tokens = name_tokens(signed_in_name())

    my = clients_for_user(tokens, roles_bc, owner_by_client)

    if alloc is None:
        st.caption("⚠️ Reviewer allocations couldn't be loaded — showing only "
                   "clients you own.")

    _my_preparations(my, owner_by_client, blocks)
    st.markdown("---")
    _my_board_meetings(my, owner_by_client, blocks)

    if dev_req and unmatched:
        st.caption(f"🔧 Unmatched tracker clients (no allocation row): "
                   f"{', '.join(unmatched)}")


def _upcoming_markers(blocks, my, owner_by_client):
    """Upcoming (today or later) deadline markers across the given preparations,
    tagged with the responsible Owner and the viewer's role.

    Mirrors the timeline's per-row markers: GCM Finish (every preparation),
    Board meeting (valuation preps), Audit draft deadline (year-end), Assessment
    deadline (where present). Sorted soonest-first.
    """
    today = pd.Timestamp.now().normalize()
    rows = []
    for _, b in blocks.iterrows():
        client = b["Client"]
        markers = [("GCM Finish", b["Finish"])]
        if b["PrepType"] in (PREP_VAL_1, PREP_VAL_2):
            markers.append(("Board meeting", b["BODDate"]))
        if b["PrepType"] == PREP_YEAR_END:
            markers.append(("Audit draft deadline", b["Target"]))
        markers.append(("Assessment deadline", b["AssessDate"]))
        for label, when in markers:
            if when is None or pd.isna(when):
                continue
            when = pd.Timestamp(when)
            if when.normalize() < today:
                continue
            rows.append({"Date": when, "Client": client,
                         "Owner": owner_by_client.get(client, "—"),
                         "Your role": _role_str(my.get(client)),
                         "Preparation": b["PrepType"], "Milestone": label})
    cols = ["Date", "Client", "Owner", "Your role", "Preparation", "Milestone"]
    if not rows:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(rows).sort_values("Date").reset_index(drop=True)


def _my_preparations(my, owner_by_client, blocks):
    """The viewer's preparations (clients they own or review), a count and the
    next deadlines — each tagged with the responsible Owner and their role."""
    st.subheader("Your preparations")

    if not my:
        st.info("We couldn't match your sign-in to an owner, reviewer, or "
                "management member yet. Once your name appears in the tracker or "
                "the Client Allocation sheet, your clients will show here.")
        return

    mine = blocks[blocks["Client"].isin(list(my))] if not blocks.empty else blocks
    if mine.empty:
        st.success("You're allocated to clients, but none have preparations in "
                   "the tracker yet.")
        return

    upcoming = _upcoming_markers(mine, my, owner_by_client)
    today = pd.Timestamp.now().normalize()

    c1, c2, c3 = st.columns(3)
    c1.metric("Preparations", mine.groupby(["Client", "PrepType"]).ngroups)
    c2.metric("Clients", mine["Client"].nunique())
    c3.metric("Next deadline",
              upcoming.iloc[0]["Date"].strftime("%b %d, %Y")
              if not upcoming.empty else "—")

    if upcoming.empty:
        st.caption("No upcoming deadlines — everything on your clients is in the "
                   "past.")
        return

    nxt = upcoming.iloc[0]
    days = (nxt["Date"].normalize() - today).days
    when = "today" if days == 0 else f"in {days} day{'' if days == 1 else 's'}"
    st.caption(f"Next up: **{nxt['Milestone']}** for **{nxt['Client']}** "
               f"({nxt['Preparation']}) — {when}.")

    show = upcoming.head(5).copy()
    show["When"] = show["Date"].dt.strftime("%b %d, %Y")
    show["In (days)"] = (show["Date"].dt.normalize() - today).dt.days
    st.dataframe(
        show[["When", "In (days)", "Client", "Owner", "Your role",
              "Preparation", "Milestone"]],
        hide_index=True, width="stretch")


def _my_board_meetings(my, owner_by_client, blocks):
    """A row of metric cards: all board meetings on the viewer's clients, each
    tagged with the responsible Owner and their role. Wrapped at four per row."""
    st.subheader("📅 Your board meetings")

    if my and not blocks.empty:
        board = (blocks[(blocks["PrepType"].isin([PREP_VAL_1, PREP_VAL_2]))
                        & (blocks["Client"].isin(list(my)))]
                 .dropna(subset=["BODDate"]).sort_values("BODDate"))
    else:
        board = blocks.iloc[0:0]

    if board.empty:
        st.caption("You have no board meetings scheduled.")
        return

    today = pd.Timestamp.now().normalize()
    n = len(board)
    st.caption(f"**{n}** board meeting{'' if n == 1 else 's'} scheduled.")

    per_row = 4
    meetings = list(board.itertuples(index=False))
    for i in range(0, len(meetings), per_row):
        cols = st.columns(per_row)
        for col, m in zip(cols, meetings[i:i + per_row]):
            client = str(m.Client).replace(", Ltd.", "").replace(" Ltd.", "")
            days = (m.BODDate.normalize() - today).days
            when = ("today" if days == 0 else f"{-days}d ago" if days < 0
                    else f"in {days}d")
            with col:
                st.metric(client, m.BODDate.strftime("%b %d, %Y"))
                st.caption(f"👤 {owner_by_client.get(m.Client, '—')} · "
                           f"you: {_role_str(my.get(m.Client))}")
                st.caption(f"{m.BODDate:%A} · {when}")
