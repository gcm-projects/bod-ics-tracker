"""
ICS FS Process Tracker
----------------------
Interactive timeline + checklist tool for the ICS / GCM financial-statement
workflow.

The tracker holds TWO source sheets, keyed by client:

  * "Year End"          — exactly one preparation per client (the audited
                          year-end): Actuary -> ICS Prep -> GCM Prep ->
                          ICS Comments -> GCM Finalize -> Audit Draft.
  * "Valuation date FS" — one preparation PER BOARD MEETING (up to two,
                          laid out as two side-by-side blocks): New Valuation
                          -> ICS Prep -> GCM Prep -> ICS Comments -> GCM Finalize.

Business rule (verified against the source):

    preparations per client = 1 (year-end, always) + Number meetings

    => 1 meeting  -> 2 preparations
       2 meetings -> 3 preparations

Rather than show the two sheets separately, this app normalises BOTH into one
canonical table of *preparation instances* (build_preparations) so a single
timeline shows every window in which GCM is preparing a client's accounts.

Run with:  streamlit run app.py
"""

import json
import os
import re
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
APP_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(APP_DIR, "checkoff_state.json")
EXCEL_EPOCH = pd.Timestamp("1899-12-30")

# Ordered stage chains. Each tuple = (stage label, start col, end col). Column
# names are resolved case/spelling-insensitively (see `cell`), so the sheets'
# inconsistent spellings ("GCM finalise end" vs "GCM Finalize End") don't bite.
YEAR_END_STAGES = [
    ("ICS Prep",     "Actuary Date",      "ICS Prep End"),
    ("GCM Prep",     "ICS Prep End",      "GCM Prep End"),
    ("ICS Comments", "GCM Prep End",      "ICS Comments End"),
    ("GCM Finalize", "ICS Comments End",  "GCM Finalise End"),
    ("Audit Draft",  "GCM Finalise End",  "Proposed Draft Audit Deadline"),
]
VAL_STAGES_1 = [
    ("ICS Prep",     "New valuation date", "ICS Prep End"),
    ("GCM Prep",     "ICS Prep End",       "GCM Prep End"),
    ("ICS Comments", "GCM Prep End",       "ICS Comments End"),
    ("GCM Finalize", "ICS Comments End",   "GCM Finalise End"),
]
# Board meeting 2 is the SAME layout shifted right; pandas suffixes the
# duplicated headers with ".1", so the second block is block 1 + ".1".
VAL_STAGES_2 = [(s, f"{sc}.1", f"{ec}.1") for s, sc, ec in VAL_STAGES_1]

# The three preparation kinds, in the order we want legend/colour assignment.
PREP_YEAR_END = "Year End GCM Prep"
PREP_VAL_1 = "GCM Prep Board Meeting 1"
PREP_VAL_2 = "GCM Prep Board Meeting 2"
# Chart-only category: the auditor's phase, drawn as a faded tail on the
# year-end bar (GCM Finalize end -> proposed audit deadline).
PREP_AUDIT = "Audit Draft (auditor)"
PREP_ORDER = [PREP_YEAR_END, PREP_AUDIT, PREP_VAL_1, PREP_VAL_2]

# Toggle the faded audit-draft tail on the year-end bar. Off for now.
SHOW_AUDIT_TAIL = False

STAGES_BY_PREP = {
    PREP_YEAR_END: [s[0] for s in YEAR_END_STAGES],
    PREP_VAL_1: [s[0] for s in VAL_STAGES_1],
    PREP_VAL_2: [s[0] for s in VAL_STAGES_1],
}
ALL_STAGES = ["ICS Prep", "GCM Prep", "ICS Comments", "GCM Finalize", "Audit Draft"]

STAGE_COLORS = {
    "ICS Prep": "#4C78A8",
    "GCM Prep": "#F58518",
    "ICS Comments": "#54A24B",
    "GCM Finalize": "#B279A2",
    "Audit Draft": "#E45756",
}

# Stages that make up GCM's preparation window: from ICS Prep End (when ICS
# hands off) through GCM Finalise End. ICS Prep (ICS's own prep) sits before
# this window and Audit Draft (the auditor's phase) after it, so both are
# excluded. The GCM Prep stage begins at ICS Prep End, so the window starts there.
GCM_PREP_STAGES = ["GCM Prep", "ICS Comments", "GCM Finalize"]

# One solid colour per preparation type — the blocks shown on the chart. The
# audit tail reuses the year-end blue at low opacity so it reads as a faded
# continuation of the same bar.
PREP_COLORS = {
    PREP_YEAR_END: "#4C78A8",              # blue
    PREP_VAL_1:    "#F58518",              # orange
    PREP_VAL_2:    "#54A24B",              # green
    PREP_AUDIT:    "rgba(76,120,168,0.35)",  # faded blue tail
}

# Per-client dashed reference lines drawn on each client's own row.
BOD_LINE_COLOR = "#E4262C"     # red          — board meeting date (BOD)
AUDIT_LINE_COLOR = "#8ECAE6"   # light blue   — draft audit deadline (year-end)
ASSESS_LINE_COLOR = "#C77DFF"  # bright purple — assessment deadline


# --------------------------------------------------------------------------- #
# Small parsing helpers
# --------------------------------------------------------------------------- #
def to_date(v):
    """Coerce Excel serial ints OR date strings into a Timestamp (or None)."""
    if v is None:
        return None
    # Reject nulls FIRST. pd.NaT is an instance of datetime, so without this it
    # would slip through the isinstance check below and become a phantom bar.
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (pd.Timestamp, datetime)):
        return pd.Timestamp(v)
    if isinstance(v, (int, float)):
        # Large serials are real dates; small ones (e.g. 21, 45) are day-count
        # annotations used as placeholders -> treat as not a real date.
        if v > 10000:
            return EXCEL_EPOCH + pd.Timedelta(days=int(v))
        return None
    try:
        return pd.to_datetime(v)
    except Exception:
        return None


def _norm(s):
    """Normalise a column name for tolerant matching (case/spacing/spelling)."""
    return re.sub(r"\s+", " ", str(s).strip().lower()).replace("finalize", "finalise")


def cell(row, name):
    """Resolve one cell by logical name, tolerant of case/spacing/US-vs-UK
    spelling. This is the single place allowed to know the sheets are messy."""
    target = _norm(name)
    for col in row.index:
        if _norm(col) == target:
            return row[col]
    return None


def _fmt(d):
    return d.strftime("%b %d, %Y") if d is not None and pd.notna(d) else "—"


def _clean_str(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    s = str(v).strip()
    return s if s else "—"


def _to_int(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return int(float(v))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Data loading (anti-corruption layer)
# --------------------------------------------------------------------------- #
def _clean_clients(df, base_col):
    """Drop legend / notes / requirement / worked-example rows that live inside
    the data. The reliable domain rule: a real client always has a parseable
    base date (year-end / valuation date); notes and requirements never do."""
    df = df[df["Client Name"].notna()].copy()
    name = df["Client Name"].astype(str)
    # Worked examples are written as "Valor: 1 meeting per year" — a colon never
    # appears in a real "X, Ltd." client name, so it's a safe discriminator.
    df = df[~name.str.contains(":")]
    df = df[~name.str.startswith((
        "-", "Fully automated", "Being automated", "Estimated dates",
        "Notes", "Solution", "Example",
    ))]
    if base_col in df.columns:
        df = df[df[base_col].apply(lambda v: to_date(v) is not None)]
    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_data(file_source):
    """Return (year_end_df, valuation_df), cleaned.

    Year End headers sit on the first row; the Valuation sheet's real headers
    sit on the SECOND row (row 1 is the merged "Board meeting 1 / 2" banner).
    """
    xl = pd.ExcelFile(file_source)
    ye = xl.parse("Year End", header=0)
    val = xl.parse("Valuation date FS", header=1)
    val = val.dropna(how="all")
    return (_clean_clients(ye, "Year End Date"),
            _clean_clients(val, "New valuation date"))


# --------------------------------------------------------------------------- #
# Canonical model: one row per (client, preparation instance, stage)
# --------------------------------------------------------------------------- #
def _instance_segments(row, stages, prep_type, base_col, target_col, meta,
                       bod_col=None, assess_col=None):
    """Explode one workflow instance into its stage segments (skips gaps)."""
    base = to_date(cell(row, base_col))
    target = to_date(cell(row, target_col)) if target_col else None
    bod = to_date(cell(row, bod_col)) if bod_col else None
    # Assessment deadline is only populated where it applies (year-end for
    # 1-meeting clients; each board meeting), so a blank simply means no line.
    assess = to_date(cell(row, assess_col)) if assess_col else None
    out = []
    for stage, start_col, end_col in stages:
        start = to_date(cell(row, start_col))
        finish = to_date(cell(row, end_col))
        if start is None or finish is None or finish < start:
            continue
        if finish == start:                       # plotly needs non-zero width
            finish = finish + pd.Timedelta(days=1)
        out.append({
            **meta,
            "PrepType": prep_type,
            "BaseDate": base,
            "Target": target,
            "BODDate": bod,
            "AssessDate": assess,
            "Stage": stage,
            "Start": start,
            "Finish": finish,
            "Days": (finish - start).days,
        })
    return out


def _year_end_md_map(ye_df, val_df):
    """client -> year-end date as 'M/D' (from Year End sheet, else Valuation)."""
    md = {}
    for _, r in ye_df.iterrows():
        d = to_date(cell(r, "Year End Date"))
        if d is not None:
            md[r["Client Name"]] = f"{d.month}/{d.day}"
    for _, r in val_df.iterrows():
        d = to_date(cell(r, "Year end"))
        if d is not None:
            md.setdefault(r["Client Name"], f"{d.month}/{d.day}")
    return md


def build_preparations(ye_df, val_df):
    """Union BOTH sheets into one tidy 'preparation instances' table.

    Year End  -> one instance per client.
    Valuation -> one instance per board-meeting block (Board Meeting 1 / 2).
    """
    ye_md = _year_end_md_map(ye_df, val_df)

    def _label(client):
        md = ye_md.get(client)
        return f"{client}  ({md})" if md else str(client)

    rows = []
    for _, r in ye_df.iterrows():
        meta = {"Client": r["Client Name"],
                "ClientLabel": _label(r["Client Name"]),
                "Owner": _clean_str(cell(r, "Owner")),
                "Auditor": _clean_str(cell(r, "Auditor"))}
        rows += _instance_segments(
            r, YEAR_END_STAGES, PREP_YEAR_END,
            "Year End Date", "Proposed Draft Audit Deadline", meta,
            bod_col="BOD date", assess_col="Assessment Deadline")
    for _, r in val_df.iterrows():
        meta = {"Client": r["Client Name"],
                "ClientLabel": _label(r["Client Name"]),
                "Owner": _clean_str(cell(r, "Owner")),
                "Auditor": _clean_str(cell(r, "Auditor"))}
        rows += _instance_segments(
            r, VAL_STAGES_1, PREP_VAL_1, "New valuation date", "BOD date", meta,
            bod_col="BOD date", assess_col="Assessment Deadline")
        rows += _instance_segments(
            r, VAL_STAGES_2, PREP_VAL_2, "New valuation date.1", "BOD date.1",
            meta, bod_col="BOD date.1", assess_col="Assessment Deadline.1")

    df = pd.DataFrame(rows)
    if not df.empty:
        df["BaseDateLabel"] = df["BaseDate"].apply(_fmt)
        df["TargetLabel"] = df["Target"].apply(_fmt)
    return df


def build_blocks(preps):
    """Collapse each preparation into bars for the chart.

    Main bar spans ICS Prep End -> GCM Finalise End (GCM's preparation
    window). Year-end preparations also get a faded 'Audit Draft' tail
    (GCM Finalize end -> proposed audit deadline) as a separate translucent
    category, so it reads as a continuation of the year-end bar.
    """
    if preps.empty:
        return preps.iloc[0:0]

    agg = dict(ClientLabel=("ClientLabel", "first"),
               Start=("Start", "min"), Finish=("Finish", "max"),
               BaseDate=("BaseDate", "first"), Target=("Target", "first"),
               BODDate=("BODDate", "first"),
               AssessDate=("AssessDate", "first"),
               Owner=("Owner", "first"), Auditor=("Auditor", "first"))

    frames = []
    gcm = preps[preps["Stage"].isin(GCM_PREP_STAGES)]
    if not gcm.empty:
        frames.append(gcm.groupby(["Client", "PrepType"]).agg(**agg).reset_index())
    audit = (preps[preps["Stage"] == "Audit Draft"] if SHOW_AUDIT_TAIL
             else preps.iloc[0:0])
    if not audit.empty:
        tail = audit.groupby(["Client", "PrepType"]).agg(**agg).reset_index()
        tail["PrepType"] = PREP_AUDIT           # recolour as the faded tail
        frames.append(tail)

    if not frames:
        return preps.iloc[0:0]

    blocks = pd.concat(frames, ignore_index=True)
    # Business days (Mon-Fri) between Start and Finish; weekends excluded.
    blocks["Days"] = np.busday_count(
        blocks["Start"].values.astype("datetime64[D]"),
        blocks["Finish"].values.astype("datetime64[D]"))
    blocks["As-of date"] = blocks["BaseDate"].apply(_fmt)
    blocks["Target date"] = blocks["Target"].apply(_fmt)
    blocks["BOD date"] = blocks["BODDate"].apply(_fmt)
    blocks["Assessment date"] = blocks["AssessDate"].apply(_fmt)
    return blocks


def validate_preparations(ye_df, val_df, preps):
    """Enforce the invariant: built preps == 1 (year-end) + Number meetings.

    Returns a list of human-readable issue strings (empty == all good).
    """
    meetings = {}
    for _, r in ye_df.iterrows():
        n = _to_int(cell(r, "Number meetings"))
        if n is not None:
            meetings[r["Client Name"]] = n
    for _, r in val_df.iterrows():
        n = _to_int(cell(r, "Number meetings"))
        if n is not None:
            meetings.setdefault(r["Client Name"], n)

    actual = ({} if preps.empty
              else preps.groupby("Client")["PrepType"].nunique().to_dict())

    issues = []
    for client, n in sorted(meetings.items()):
        expected = 1 + n
        got = actual.get(client, 0)
        if got != expected:
            issues.append(
                f"**{client}** — expected {expected} preparations "
                f"(1 year-end + {n} valuation), but built {got}.")
    return issues


# --------------------------------------------------------------------------- #
# Check-off persistence
# --------------------------------------------------------------------------- #
def load_checkoff():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_checkoff(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        st.warning(f"Could not save check-off state: {e}")


# --------------------------------------------------------------------------- #
# UI
# --------------------------------------------------------------------------- #
def main():
    st.set_page_config(page_title="ICS FS Process Tracker",
                       page_icon="📊", layout="wide")

    # ----- Sidebar: data source -------------------------------------------- #
    st.sidebar.title("📊 ICS FS Tracker")
    uploaded = st.sidebar.file_uploader("Upload tracker workbook (.xlsx)",
                                        type=["xlsx"])
    if uploaded is None:
        st.info("👋 Upload your tracker workbook (.xlsx) in the sidebar to begin.")
        st.stop()

    ye_df, val_df = load_data(uploaded)
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
    st.caption("One row per preparation. Tick completed steps — saved to disk "
               "and persists across runs. (Audit Draft applies to year-end only.)")

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
            applicable = STAGES_BY_PREP[ptype]
            saved = prep_state.get(f"{client} :: {ptype}", {})
            row = {"Client": client, "Preparation": ptype}
            for sname in ALL_STAGES:
                row[sname] = bool(saved.get(sname, False)) if sname in applicable else False
            row["Done"] = sum(bool(row[s]) for s in applicable)
            table_rows.append(row)

        edit_df = pd.DataFrame(table_rows)
        col_config = {s: st.column_config.CheckboxColumn(s) for s in ALL_STAGES}
        col_config["Client"] = st.column_config.TextColumn("Client", disabled=True)
        col_config["Preparation"] = st.column_config.TextColumn(
            "Preparation", disabled=True)
        col_config["Done"] = st.column_config.NumberColumn("Done", disabled=True)

        edited = st.data_editor(
            edit_df,
            column_config=col_config,
            column_order=["Client", "Preparation", *ALL_STAGES, "Done"],
            hide_index=True,
            width="stretch",
            key="editor_prep",
        )

        if st.button("💾 Save check-off", type="primary"):
            checkoff.setdefault("preparations", {})
            for _, r in edited.iterrows():
                applicable = STAGES_BY_PREP[r["Preparation"]]
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


if __name__ == "__main__":
    main()
