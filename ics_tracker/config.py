"""Constants and configuration for the ICS FS Process Tracker."""

import os

import pandas as pd

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
# Repo root is the parent of this package directory. Runtime state (the
# check-off file) lives there, next to app.py.
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(APP_DIR, "checkoff_state.json")

# Package-relative assets (shipped with the code, so they deploy with the app).
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(PACKAGE_DIR, "assets")
LOGO_DARK = os.path.join(ASSETS_DIR, "logo-white.png")   # white mark, dark theme
LOGO_LIGHT = os.path.join(ASSETS_DIR, "full-logo.png")    # colour mark, light theme

EXCEL_EPOCH = pd.Timestamp("1899-12-30")

# --------------------------------------------------------------------------- #
# Stage chains
# --------------------------------------------------------------------------- #
# Ordered stage chains. Each tuple = (stage label, start col, end col). Column
# names are resolved case/spelling-insensitively (see parsing.cell), so the
# sheets' inconsistent spellings ("GCM finalise end" vs "GCM Finalize End")
# don't bite.
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

# --------------------------------------------------------------------------- #
# Preparation types
# --------------------------------------------------------------------------- #
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

# Milestones ticked off in the check-off table (a shorter list than the full
# workflow stages above). "GCM Start" = ICS Prep End, "GCM Finish" = GCM
# Finalise End. The audit deadline only exists for the year-end preparation.
CHECKOFF_STEPS = ["GCM Start", "GCM Finish", "Audit Draft Deadline"]
CHECKOFF_STEPS_BY_PREP = {
    PREP_YEAR_END: ["GCM Start", "GCM Finish", "Audit Draft Deadline"],
    PREP_VAL_1: ["GCM Start", "GCM Finish"],
    PREP_VAL_2: ["GCM Start", "GCM Finish"],
}

# Stages that make up GCM's preparation window: from ICS Prep End (when ICS
# hands off) through GCM Finalise End. ICS Prep (ICS's own prep) sits before
# this window and Audit Draft (the auditor's phase) after it, so both are
# excluded. The GCM Prep stage begins at ICS Prep End, so the window starts there.
GCM_PREP_STAGES = ["GCM Prep", "ICS Comments", "GCM Finalize"]

# --------------------------------------------------------------------------- #
# Colours
# --------------------------------------------------------------------------- #
STAGE_COLORS = {
    "ICS Prep": "#4C78A8",
    "GCM Prep": "#F58518",
    "ICS Comments": "#54A24B",
    "GCM Finalize": "#B279A2",
    "Audit Draft": "#E45756",
}

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
# Data source: the tracker workbook in SharePoint (fetched via Microsoft Graph)
# --------------------------------------------------------------------------- #
# WHERE the workbook lives (not secret). The Graph credentials that grant access
# live in the [sharepoint] secrets section (see secrets.toml.example).
SP_HOSTNAME = "gcmcan.sharepoint.com"
SP_SITE_PATH = "/sites/ResourceCenter"
SP_DRIVE_NAME = "Forms & Templates"           # the document library (Graph drive)
SP_FILE_PATH = "ICS/Meeting Format and Tracker/Data for tracker ICS.xlsx"

# Local-dev fallback: used ONLY when [sharepoint] secrets are absent and this
# file exists (git-ignored). Lets you run locally without Graph credentials.
LOCAL_WORKBOOK_PATH = os.path.join(APP_DIR, "data", "Final - Data for tracker ICS.xlsx")
