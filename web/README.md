# DayRescue React app — local development

React is an additional frontend. The existing Streamlit release remains available with its original setup and controls. The Python core is shared; TypeScript does not decide scheduling validity.

## Run on Windows (PowerShell)

From the repository root, install the optional API dependencies into the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
```

Terminal 1, repository root (generation disabled):

```powershell
$env:DAYRESCUE_ENABLE_LIVE_AI = "0"
.\.venv\Scripts\python.exe -m api
```

Terminal 2:

```powershell
Set-Location web
npm.cmd ci
npm.cmd run dev
```

Open **http://127.0.0.1:5173**. API binds to **127.0.0.1:8001**. Keep the default ports: CORS permits only localhost/127.0.0.1 on 5173 and 4173. Vite proxies `/api` to the local Python process. `npm.cmd` avoids PowerShell npm shim issues; standard `npm` works where configured normally. Node 22.12+ and Python 3.11+ are required; verified with Node 22.23.4 / Python 3.13.1. Stop each terminal with Ctrl+C.

The production build can be checked locally with `npm.cmd run build` and `npm.cmd run preview` (http://127.0.0.1:4173, with the same API running). These commands do not deploy anything. This unauthenticated adapter is for local use only.

## Planning and rescue

First launch is empty. Create a dated activity or explicitly try the hand-authored sample. My week selects seven local dates. Data belongs to this browser **and origin**: changing hostname/port, clearing site data or changing browsers changes the available local plans. There is no cloud sync or backup.

Each day allows 8 activities total and 10 unavoidable interruptions. Completion is explicit. Completed and unscheduled items are excluded from the pending Python payload. The future-day pending clock is 00:00; today's clock comes from the browser. Past days remain editable/viewable but cannot request rescue. Whole local minutes within one day are supported, without overnight or time-zone conversion.

Use **Check schedule conflicts** while generation is disabled. No fixed conflicts is not proof of full feasibility. Fixed commitments never move automatically. An activity can be manually assigned a different date through its editor; AI rescue always handles only the selected day.

Saving an interruption brings an affected-activity summary and **Find a new plan** into view. Flexible overlaps can be considered for a revised time; Fixed overlaps offer **Review commitment**. No generation occurs on save. A currently active activity stays pending, with its full duration included; elapsed progress is not automatically deducted.

Authored date/week labels use English. All time editors use labeled hour/minute selectors covering 00–23 and 00–59, preserving every minute. Native date-calendar dialogs may still use the browser/OS locale. Section reveals last 280ms, do not change layout, and remain optional: unavailable observers or reduced-motion preferences leave content visible.

## Connection troubleshooting

**Planning service unavailable** means the browser could not read a valid API health response. Editing and local saving continue, while online actions are disabled. Expand **Advanced: local connection help** for commands. Starting Vite alone does not start FastAPI.

Start the API from the repository root in a second terminal, then choose **Retry connection**. The frontend also polls health every 15 seconds while visible and checks on window focus. All reconnect checks are GET health requests; they never repeat a failed schedule check, submit a rescue or resume an interrupted generation. A fresh action click is always required.

**AI planning is currently disabled** means the service responded with its gate off. Conflict checking still works. It is a separate state from an unreachable service and does not imply a provider failure.

These optional diagnostics contact only loopback health endpoints:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/health
Invoke-RestMethod http://127.0.0.1:5173/api/health
```

If the direct endpoint fails, inspect the API terminal: use the project `.venv` and install `requirements-api.txt`. The launcher prints an install hint for missing dependencies and a recovery hint for startup/bind failures. An occupied port 8001 causes a nonzero exit; do not stop an unrelated process. If the direct endpoint succeeds but the proxy fails, run Vite from `web/` with the committed configuration and default ports, then retry. Do not expose either process publicly or put credentials in Vite configuration.

For an explicitly authorized manual live session, stop the API and restart it from the repository root with the process flag set to exactly `1`:

```powershell
$env:DAYRESCUE_ENABLE_LIVE_AI = "1"
.\.venv\Scripts\python.exe -m api
```

Use **Retry connection** or wait for health polling to refresh the gate. The ignored root `.env` stays server-side and is loaded only by the existing lazy invocation boundary after successful preflight. Vite's `.env` loading is disabled. Do not copy credentials into `web/`, use `VITE_` secrets, or expose this service publicly. Only an explicit **Rescue my day** or **Find a new plan** click starts generation; one click permits one proposal and at most one correction after Python rejection. Provider errors are not retried. M6A and M6B verification used no real Meta requests; M6B does not authorize another manual live test.

Review Before/After, then choose **Keep original plan** or **Apply this plan**. Confirmation triggers fresh Python validation against the current clock. Input/date changes invalidate the review. Postponed work remains unscheduled on the same date. Undo restores the prior accepted snapshot, including after reload, until later edits make that snapshot stale. Up to five acceptance snapshots per date are retained. Raw provider responses, rationale, credentials and execution diagnostics are never stored in localStorage.

## Checks

Repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\doctor.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\demo_offline.py
```

From `web/`:

```powershell
npm.cmd test
npm.cmd run build
npm.cmd audit
```

Python tests use ASGI and MockTransport, with external networking blocked by the existing test guard. Frontend tests use mocked `fetch` and genuine Python-validated hand-authored fixtures. No result from these checks is live Muse output.

The optional **test-only** browser launcher `tests/browser_api_fixture.py` replaces the API process at port 8001 with SDK MockTransport and forbids external networking and `.env` reads. It accepts only the exact three named test activities described in its module docstring. It is not a general scheduler or a production demo mode. Its UI displays an offline banner; successful test acceptances remain marked demo locally. Stop it before restarting the production API.

Streamlit fallback (repository root):

```powershell
$env:DAYRESCUE_ENABLE_LIVE_AI = "0"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

See [the migration report](../docs/M6A_REACT_MIGRATION_REPORT.md) for evidence, screenshots and remaining limitations.
The [M6B UX fix report](../docs/M6B_UX_FIX_REPORT.md) records connection diagnosis, English/24-hour controls, interruption follow-through and final regression results.
