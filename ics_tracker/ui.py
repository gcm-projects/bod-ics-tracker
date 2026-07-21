"""The Streamlit app UI: sidebar, KPIs, timeline chart, check-off, summary."""

import os

import pandas as pd
import plotly.express as px
import streamlit as st

from .auth import greeting, logout_control, require_login
from .checkoff import load_checkoff, save_checkoff
from .config import (ASSESS_LINE_COLOR, AUDIT_LINE_COLOR, BOD_LINE_COLOR,
                     CHECKOFF_STEPS, CHECKOFF_STEPS_BY_PREP,
                     LOCAL_WORKBOOK_PATH, PREP_AUDIT, PREP_COLORS, PREP_ORDER,
                     PREP_VAL_1, PREP_VAL_2, PREP_YEAR_END)
from .data import load_data
from .model import build_blocks, build_preparations, validate_preparations
from .parsing import _fmt
from .sharepoint import fetch_workbook_bytes, sharepoint_configured

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


def run():
    st.set_page_config(page_title="ICS FS Timeline Tracker",
                       page_icon="📊", layout="wide")
    require_login()  # inert until [auth] secrets exist; then gates the app

    # ----- Sidebar + greeting ---------------------------------------------- #
    st.sidebar.title("📊 ICS FS Tracker")

    # Personalised greeting in the MAIN area (shown once signed in).
    hello = greeting()
    if hello:
        st.markdown(f"## {hello}")

    # ----- Load the tracker workbook --------------------------------------- #
    # Primary source is SharePoint (via Microsoft Graph). A local file is the
    # dev-only fallback used when [sharepoint] secrets aren't configured.
    if sharepoint_configured() and st.sidebar.button("🔄 Refresh data"):
        fetch_workbook_bytes.clear()   # force a re-fetch from SharePoint
    loader = st.empty()
    loader.markdown(_LOADER_HTML, unsafe_allow_html=True)  # purple spinner
    try:
        if sharepoint_configured():
            ye_df, val_df = load_data(fetch_workbook_bytes())
        elif os.path.exists(LOCAL_WORKBOOK_PATH):
            ye_df, val_df = load_data(LOCAL_WORKBOOK_PATH)
        else:
            loader.empty()
            st.error("No data source configured. Add the [sharepoint] secrets "
                     "(or place a local workbook for dev).")
            logout_control()
            st.stop()
    except Exception as e:
        loader.empty()
        st.error(f"Couldn't load the tracker workbook: {e}")
        logout_control()
        st.stop()
    loader.empty()   # clear the loader once data is ready

    preps_all = build_preparations(ye_df, val_df)
    issues = validate_preparations(ye_df, val_df, preps_all)

    # ----- Sidebar: view + filters ----------------------------------------- #
    view = st.sidebar.radio(
        "View", ["Combined (all preparations)", "Year End only", "Valuation only"])
    if view.startswith("Year End"):
        preps = preps_all[preps_all["PrepType"] == PREP_YEAR_END]
    elif view.startswith("Valuation"):
        preps = preps_all[preps_all["PrepType"].isin([PREP_VAL_1, PREP_VAL_2])]
    else:
        preps = preps_all
    preps = preps.copy()

    st.sidebar.markdown("### Filters")
    owners = sorted(preps["Owner"].dropna().unique()) if not preps.empty else []
    auditors = sorted(preps["Auditor"].dropna().unique()) if not preps.empty else []
    sel_owners = st.sidebar.multiselect("Owner", owners, default=owners)
    sel_auditors = st.sidebar.multiselect("Auditor", auditors, default=auditors)
    client_query = st.sidebar.text_input("Search client name").strip().lower()

    if not preps.empty:
        if sel_owners:
            preps = preps[preps["Owner"].isin(sel_owners)]
        if sel_auditors:
            preps = preps[preps["Auditor"].isin(sel_auditors)]
        if client_query:
            preps = preps[preps["Client"].str.lower().str.contains(client_query)]

    # Optional date-range filter (based on overall span in view)
    # if not preps.empty:
    #     min_d = preps["Start"].min().date()
    #     max_d = preps["Finish"].max().date()
    #     dr = st.sidebar.date_input("Date range", (min_d, max_d),
    #                                min_value=min_d, max_value=max_d)
    #     if isinstance(dr, (list, tuple)) and len(dr) == 2:
    #         lo, hi = pd.Timestamp(dr[0]), pd.Timestamp(dr[1])
    #         preps = preps[(preps["Finish"] >= lo) & (preps["Start"] <= hi)]

    # ----- Header + KPIs --------------------------------------------------- #
    st.title("GCM Preparation Timeline")

    n_preps = 0 if preps.empty else preps.groupby(["Client", "PrepType"]).ngroups
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clients", 0 if preps.empty else preps["Client"].nunique())
    c2.metric("Preparations", n_preps)
    if not preps.empty:
        c3.metric("Earliest milestone", preps["Finish"].min().strftime("%b %d, %Y"))
        c4.metric("Latest milestone", preps["Finish"].max().strftime("%b %d, %Y"))

    # ----- Validation gate ------------------------------------------------- #
    if issues:
        with st.expander(f"⚠️ {len(issues)} data check(s) failed "
                         f"(preparations ≠ 1 + Number meetings)", expanded=False):
            for msg in issues:
                st.markdown(f"- {msg}")
            st.caption("These usually mean a board-meeting block is blank, a "
                       "date is missing, or a client is absent from one sheet.")
    else:
        st.success("✅ All clients match the rule: preparations = 1 + Number meetings.")

    # ----- Timeline -------------------------------------------------------- #
    # One solid bar per preparation (ICS Prep End -> GCM Finalise End),
    # coloured by which preparation it is: year-end vs board meeting 1 / 2.
    blocks = build_blocks(preps)
    if blocks.empty:
        st.info("No timeline data for the current filters.")
    else:
        order = (blocks.groupby("ClientLabel")["Start"].min()
                 .sort_values().index.tolist())
        prep_types_present = [p for p in PREP_ORDER
                              if p in blocks["PrepType"].unique()]
        fig = px.timeline(
            blocks,
            x_start="Start",
            x_end="Finish",
            y="ClientLabel",
            color="PrepType",
            color_discrete_map=PREP_COLORS,
            category_orders={"ClientLabel": order, "PrepType": prep_types_present},
            hover_data={"As-of date": True, "Target date": True, "Days": True,
                        "Owner": True, "Auditor": True, "BOD date": True,
                        "Assessment date": True,
                        "Start": "|%b %d, %Y", "Finish": "|%b %d, %Y"},
        )

        # Per-preparation hover. customdata = [As-of, Target, Days, Owner,
        # Auditor]. On the year-end bar, relabel Target as the Draft Audit
        # Deadline; on the board-meeting bars drop it (the board date is already
        # shown by the red dashed line).
        def _hover(name):
            lines = ["<b>%{y}</b>",
                     "GCM Start: %{base|%b %d, %Y}",
                     "GCM Finish: %{x|%b %d, %Y}",
                     f"Preparation: {name}",
                     "As-of date: %{customdata[0]}"]
            if name in (PREP_YEAR_END, PREP_AUDIT):
                # Year-end targets the audit deadline; its BOD date just mirrors
                # board meeting 1, so it's omitted here to avoid confusion.
                lines.append("Draft Audit Deadline: %{customdata[1]}")
            else:
                lines.append("BOD date: %{customdata[5]}")
            lines.append("Assessment Deadline: %{customdata[6]}")
            lines += ["Business days: %{customdata[2]}",
                      "Owner: %{customdata[3]}",
                      "Auditor: %{customdata[4]}"]
            return "<br>".join(lines) + "<extra></extra>"

        for t in fig.data:
            t.hovertemplate = _hover(t.name)

        fig.update_yaxes(autorange="reversed", title="")
        fig.update_layout(
            height=max(360, 34 * len(order) + 160),
            legend_title="Preparation",
            margin=dict(l=10, r=10, t=30, b=10),
            bargap=0.30,
        )
        # Per-client dashed reference lines, drawn on that client's own row so
        # the gap between GCM finishing and the deadline is visible per client.
        #
        # A shape's numeric y coordinate maps to the category's position in the
        # axis's categoryarray -- which px REVERSES for timelines (so the chart
        # reads top-down). Index into that array, never into our `order` list,
        # or every line lands on the mirrored row.
        cats = fig.layout.yaxis.categoryarray
        cats = list(cats) if cats else order

        def _row_marker(row, when, color):
            if pd.isna(when) or row["ClientLabel"] not in cats:
                return
            idx = cats.index(row["ClientLabel"])
            fig.add_shape(
                type="line", xref="x", yref="y", layer="above",
                x0=when, x1=when, y0=idx - 0.45, y1=idx + 0.45,
                line=dict(color=color, width=1.6, dash="dash"),
            )

        # Red = board meeting date (BOD) on each valuation bar's row.
        for _, r in blocks[blocks["PrepType"].isin(
                [PREP_VAL_1, PREP_VAL_2])].iterrows():
            _row_marker(r, r["BODDate"], BOD_LINE_COLOR)
        # Light blue = draft audit deadline on each year-end bar's row.
        for _, r in blocks[blocks["PrepType"] == PREP_YEAR_END].iterrows():
            _row_marker(r, r["Target"], AUDIT_LINE_COLOR)
        # Bright purple = assessment deadline. The sheet only fills this in
        # where it applies (year-end for 1-meeting clients, and each board
        # meeting), so a blank date simply draws no line.
        for _, r in blocks[blocks["PrepType"] != PREP_AUDIT].iterrows():
            _row_marker(r, r["AssessDate"], ASSESS_LINE_COLOR)

        st.plotly_chart(fig, width="stretch")

    st.caption(
        "**How to read this chart**\n\n"
        "- **Each bar** — one preparation, spanning **ICS Prep End → GCM "
        "Finalise End** (GCM's preparation window)\n"
        "- **Bar colour** — preparation type (see legend: year-end vs board "
        "meeting 1 / 2)\n"
        "- **Client label** — the client's year-end date, as M/D\n"
        "- 🔴 **Red dashed line** — board meeting date (BOD)\n"
        "- 🔵 **Light blue dashed line** — draft audit deadline (year-end)\n"
        "- 🟣 **Purple dashed line** — assessment deadline\n"
        "- **Hover a bar** — to see key details"
    )

    # ----- Per-preparation check-off --------------------------------------- #
    st.markdown("---")
    st.subheader("✅ Step check-off")
    st.caption("One row per preparation. Tick completed milestones — saved to "
               "disk and persists across runs. (Audit Draft Deadline applies to "
               "year-end only.)")

    checkoff = load_checkoff()
    prep_state = checkoff.get("preparations", {})

    if preps.empty:
        st.info("No preparations in the current filter to check off.")
    else:
        instances = (preps[["Client", "PrepType"]].drop_duplicates()
                     .sort_values(["Client", "PrepType"]))
        table_rows = []
        for _, inst in instances.iterrows():
            client, ptype = inst["Client"], inst["PrepType"]
            applicable = CHECKOFF_STEPS_BY_PREP[ptype]
            saved = prep_state.get(f"{client} :: {ptype}", {})
            row = {"Client": client, "Preparation": ptype}
            for sname in CHECKOFF_STEPS:
                row[sname] = bool(saved.get(sname, False)) if sname in applicable else False
            row["Done"] = sum(bool(row[s]) for s in applicable)
            table_rows.append(row)

        edit_df = pd.DataFrame(table_rows)
        col_config = {s: st.column_config.CheckboxColumn(s) for s in CHECKOFF_STEPS}
        col_config["Client"] = st.column_config.TextColumn("Client", disabled=True)
        col_config["Preparation"] = st.column_config.TextColumn(
            "Preparation", disabled=True)
        col_config["Done"] = st.column_config.NumberColumn("Done", disabled=True)

        edited = st.data_editor(
            edit_df,
            column_config=col_config,
            column_order=["Client", "Preparation", *CHECKOFF_STEPS, "Done"],
            hide_index=True,
            width="stretch",
            key="editor_prep",
        )

        if st.button("💾 Save check-off", type="primary"):
            checkoff.setdefault("preparations", {})
            for _, r in edited.iterrows():
                applicable = CHECKOFF_STEPS_BY_PREP[r["Preparation"]]
                key = f"{r['Client']} :: {r['Preparation']}"
                checkoff["preparations"][key] = {s: bool(r[s]) for s in applicable}
            save_checkoff(checkoff)
            st.success("Saved.")

    # ----- Detail table ---------------------------------------------------- #
    # Built from the SAME blocks as the chart, so the summary matches the bars:
    # one row per preparation, spanning ICS Prep End -> GCM Finalise End.
    with st.expander("📋 Preparation summary (ICS Prep End → GCM Finalise End)"):
        if blocks.empty:
            st.info("Nothing to show.")
        else:
            summary = blocks[blocks["PrepType"] != PREP_AUDIT].copy()
            summary["ICS Prep End (Start)"] = summary["Start"].apply(_fmt)
            summary["GCM Finalise End (Finish)"] = summary["Finish"].apply(_fmt)
            summary = summary.rename(columns={
                "PrepType": "Preparation",
                "As-of date": "As-of",
                "Days": "Business days",
                "Target date": "Board mtg / audit deadline",
                "Assessment date": "Assessment deadline",
            }).sort_values(["Client", "Preparation"])
            cols = ["Client", "Preparation", "As-of",
                    "ICS Prep End (Start)", "GCM Finalise End (Finish)",
                    "Business days", "Board mtg / audit deadline",
                    "Assessment deadline", "Owner", "Auditor"]
            st.dataframe(summary[cols], hide_index=True, width="stretch")

    # Signed-in caption + log out, last so it pins to the sidebar bottom-left.
    logout_control()
