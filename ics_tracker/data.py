"""Data loading (anti-corruption layer): read + clean the workbook sheets."""

import pandas as pd
import streamlit as st

from .parsing import to_date


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
