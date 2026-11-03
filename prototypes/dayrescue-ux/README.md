# DayRescue UX concept

Standalone M5C design prototype. All schedules, outcomes, rationale and trace rows are **hand-authored demo content**, not Muse output. No Python scheduling, API requests, persistence or production integration runs in the browser.

## Open locally

Open `index.html` in a modern browser. Keep `styles.css`, `prototype.js` and `mark.svg` beside it. No installation or credentials are needed.

Alternatively, from the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m http.server 8765 --bind 127.0.0.1 --directory prototypes/dayrescue-ux
```

Visit [the local prototype](http://127.0.0.1:8765/index.html#day). Stop the server with Ctrl+C. The server exposes only this prototype directory, not the repository root.

## Review the four screens

1. **My day** (`#day`): sample Tuesday, 3 November 2026; timeline, activity properties, date navigation and Add activity. Other dates have empty, tab-only plans. The date range is a concept, not existing backend date support.
2. **Something changed?** (`#interruption`): Family appointment, 13:00–15:00, unavoidable. Change the times to see overlapping activities. Try 10:30–11:00 for a fixed conflict, or an end before its start for an input error. Unchecking unavoidable reveals the future-concept boundary.
3. **Rescue my day** opens `#rescued` after a short simulated loading state. Compare two kept activities, a moved project block, a moved/shortened run and postponed reading. Expand the unverified rationale and advanced details. This is a prewritten proposal, not a solver. Custom inputs cannot produce a new outcome; restore the sample instead.
4. **Week ahead** (`#week`): seven illustrative days, reflowed for mobile. Thursday shows a fixed conflict; Tuesday connects to the sample interruption. Plan an activity adds a disposable concept draft, independent of My day.

All edits stay in memory and disappear on refresh. Reset demo asks before discarding edits. Screen navigation preserves unfinished interruption fields. Dates and the selected weekly day are reflected in query parameters, but activity data is never serialized into the URL or stored.

## Files and evidence

- `index.html`: semantic screen markup, form and disclosures.
- `styles.css`: palette, typography, cards, controls and responsive layouts.
- `prototype.js`: disposable interaction state and prewritten demo data.
- `mark.svg`: original sunrise mark; no third-party assets or remote fonts.
- `screenshots/`: browser-captured JPEG viewport evidence at 1440×1000 and 390×844. Pages extend below the viewport; screenshots are not full-page exports.
- `../../docs/M5C_UX_DESIGN.md`: rationale, current/future capability map, feasibility, accessibility review and verification evidence.

The Content Security Policy blocks connections and native form submission. There are no analytics, fetches, SDKs, external assets, service workers or local storage. Run a local server if a browser restricts scripts opened directly from disk.

**Design review only.** No production implementation, deployment or merge is part of M5C.
