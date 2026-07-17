"""Small parsing helpers — the anti-corruption primitives.

These are the only functions allowed to know that the source sheets are messy
(Excel serials, inconsistent column spellings, blank/placeholder cells).
"""

import re
from datetime import datetime

import pandas as pd

from .config import EXCEL_EPOCH


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
