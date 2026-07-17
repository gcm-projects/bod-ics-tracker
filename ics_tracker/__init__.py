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
canonical table of *preparation instances* (model.build_preparations) so a
single timeline shows every window in which GCM is preparing a client's
accounts.

Package layout:
  config    — constants (stage chains, colours, prep types, paths)
  parsing   — cell/date coercion helpers (the anti-corruption primitives)
  data      — load + clean the workbook sheets
  model     — normalise into preparation instances / chart blocks; validation
  checkoff  — check-off state persistence
  auth      — Microsoft Entra ID login gate
  ui        — the Streamlit app (`run`)
"""
