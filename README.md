# ICS Timeline Tracker

A Streamlit prototype to load `Data for tracker ICS.xlsx`, recompute internal deadlines from base dates, and visualize AE timelines with overlap risk.

## Features

- Loads `Year End` and `Valuation date FS` sheets from Excel
- Recomputes deadlines from base dates:
  - Actuary date = base + 28 days
  - ICS prep end = actuary + 5 days
  - GCM prep end = ICS prep end + 5 days
  - ICS comments end = GCM prep end + 2 days
  - GCM finalize end = ICS comments end + 8 days
  - Proposed audit draft deadline = GCM finalize end + 45 days
- Visual timeline by AE with step filters
- Workflow overlap detection for each AE
- Downloadable computed schedule CSV

## Run locally

1. Create or activate the virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Place `Data for tracker ICS.xlsx` in the app folder or upload it in the UI

4. Run Streamlit

```bash
streamlit run app.py
```

## Notes

- The app recomputes schedules using `Year End Date` for the `Year End` sheet and `New valuation date` for the `Valuation date FS` sheet.
- Overlap detection is based on full internal workflow intervals from FS Prep start through GCM Finalise end.
