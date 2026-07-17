# ICS FS Process Tracker

A Streamlit app that turns the ICS / GCM financial-statement tracker workbook
into a single interactive timeline. It normalises the **Year End** and
**Valuation date FS** sheets into one canonical set of *GCM preparation
windows* per client, so you can see — across the whole year — when GCM is
preparing each client's accounts and how that lines up with board meetings and
deadlines.

## What it shows

- **One timeline, all preparations.** Each client gets a bar per preparation:
  the year-end prep plus one per board meeting (`1 meeting → 2 preparations`,
  `2 meetings → 3 preparations`).
- Each bar spans **ICS Prep End → GCM Finalise End** (GCM's working window),
  coloured by preparation type.
- Per-client dashed reference lines: 🔴 board meeting date (BOD),
  🔵 draft audit deadline (year-end), 🟣 assessment deadline.
- A validation panel that flags any client where the data breaks the
  `preparations = 1 + Number meetings` rule.
- Per-preparation step check-off and a summary table.

## Expected workbook

The app reads two sheets from the uploaded `.xlsx`:

- **`Year End`** — one row per client (headers on row 1).
- **`Valuation date FS`** — one row per client with two side-by-side
  board-meeting blocks (real headers on **row 2**, under the merged
  "Board meeting 1 / 2" banners).

Column names are matched case/spelling-insensitively, so minor variations
(e.g. `GCM finalise end` vs `GCM Finalize End`) are tolerated.

## Run locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
streamlit run app.py
```

Then upload your tracker workbook in the sidebar — the app is **upload-only**
and ships with no data.

## Deploy to Streamlit Community Cloud

1. **Push to GitHub.** The repo already has a `.gitignore` that keeps secrets,
   the virtual environment, `*.xlsx`, and `checkoff_state.json` out of version
   control.
   ```bash
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```
2. **Create the app** at <https://share.streamlit.io> → **Create app** → pick
   the repo, branch `main`, and main file `app.py`. Choose your app URL.
3. **Python version.** In *Advanced settings*, select the newest **supported**
   version (Community Cloud may not yet offer the very latest). Dependencies in
   `requirements.txt` are intentionally unpinned (except `streamlit` and
   `Authlib`) so they resolve for whatever version you pick.
4. **Make it private** while you set up authentication: app *Settings →
   Sharing* → restrict viewers to your own email.

## Authentication (Microsoft Entra ID)

Auth is wired in but **inert until secrets exist** — deploy first, then switch
it on by adding an `[auth]` section (no code change needed).

1. **Register an app** in Azure → *Entra ID → App registrations*. Add a **Web**
   redirect URI for each environment:
   - local: `http://localhost:8501/oauth2callback`
   - prod:  `https://<your-app>.streamlit.io/oauth2callback`
2. **Local testing:** `pip install Authlib`, copy
   `.streamlit/secrets.toml.example` → `.streamlit/secrets.toml`, fill in the
   values (use the localhost `redirect_uri`), then `streamlit run app.py`.
   Generate the cookie secret with
   `python -c "import secrets; print(secrets.token_hex(32))"`.
3. **Production:** in the Community Cloud app, *Settings → Secrets*, paste the
   same keys but set `redirect_uri` to the `…streamlit.io/oauth2callback` URL.
4. Use your **tenant** metadata URL to restrict sign-in to your organisation:
   `https://login.microsoftonline.com/<TENANT_ID>/v2.0/.well-known/openid-configuration`
   (the docs' `/consumers/` endpoint is for *personal* Microsoft accounts).

Once secrets are present, the app requires Microsoft sign-in and shows a
"Log out" control in the sidebar.

## Known limitations

- **Python version:** develop and deploy on the same version where practical.
  This project was developed on Python 3.14; pick the closest version Community
  Cloud offers.
- **Check-off persistence is not durable in the cloud.** `checkoff_state.json`
  is written to the server's local disk, which is ephemeral on Community Cloud
  (resets on reboot/redeploy and isn't shared across sessions). Fine for a
  single-user prototype; a database would be needed for shared, durable state.
