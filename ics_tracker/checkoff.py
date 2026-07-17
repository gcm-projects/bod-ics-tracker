"""Check-off state persistence (per-preparation step completion)."""

import json
import os

import streamlit as st

from .config import STATE_FILE


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
