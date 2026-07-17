"""Canonical model: normalise the two sheets into preparation instances.

`build_preparations` produces one row per (client, preparation, stage);
`build_blocks` collapses those into one bar per preparation for the chart;
`validate_preparations` enforces the 1-year-end + Number-meetings invariant.
"""

import numpy as np
import pandas as pd

from .config import (GCM_PREP_STAGES, PREP_AUDIT, PREP_VAL_1, PREP_VAL_2,
                     PREP_YEAR_END, SHOW_AUDIT_TAIL, VAL_STAGES_1, VAL_STAGES_2,
                     YEAR_END_STAGES)
from .parsing import _clean_str, _fmt, _to_int, cell, to_date


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
