"""ICS FS Process Tracker — Streamlit entrypoint.

Run with:  streamlit run app.py

All logic lives in the `ics_tracker` package; this file just wires the
Streamlit entrypoint to `ics_tracker.ui.run`. See the package docstring
(ics_tracker/__init__.py) for the domain overview.
"""

from ics_tracker.ui import run

if __name__ == "__main__":
    run()
