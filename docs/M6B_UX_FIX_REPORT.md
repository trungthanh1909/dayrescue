# M6B — React connectivity and UX fix report

Verified on 2026-11-04, Windows / Asia/Saigon. Ready for technical review of the local application. No real Meta calls, deployment, public endpoint or merge occurred.

Implementation commit: **`a5f164251da17bdb3b12f7ba5ad50896d846570f`**. This report is added in a documentation-only follow-up commit; the final handoff supplies the branch-tip SHA. Branch: `feat/m6b-react-ux-fixes`, based on fast-forwarded `main` at `68f01df` (M6A merged as PR #12). The working tree was clean before branching, and the repository remains PRIVATE.

## Reproduced connection issue and root cause

Started React/Vite with no process listening on API port 8001. The original UI reproduced the owner's exact error, **“The local service did not respond.”** Vite logged `ECONNREFUSED 127.0.0.1:8001` for `/api/health` and `/api/validate`. The app could still edit browser-local plans, but its conflict-check button remained enabled. Health was read only once on mount, so starting FastAPI later did not update the cached state without a reload. There was no explicit retry action.

This reproduces a concrete cause of the reported symptoms; the owner's original process logs were not available, so this is not a claim that every possible connection failure has that cause. Starting Vite alone does not start FastAPI. An unreachable API is separate from a reachable API whose live-generation gate is disabled. A disabled Rescue button under the latter condition is correct behavior.

| Condition | Evidence and resulting behavior |
| --- | --- |
| API stopped | Reproduced the original error and proxy connection refusal. Updated UI says **Planning service unavailable**, offers **Retry connection**, and disables online actions while local editing works. |
| API running, gate `0` | Direct and proxied health both returned HTTP 200 with `live_enabled:false`. Without reloading, Retry updated the UI to **AI planning is currently disabled**. Conflict checking worked against the actual Python endpoint; generation remained disabled. |
| API gate exactly `1`, transport mocked | Used only `tests/browser_api_fixture.py`, which blocks external networking and `.env` reads and forces real-SDK MockTransport. The connection and outcomes were explicitly labeled offline. Generation started only after Find a new plan clicks. |
| API starts after React | Browser retry recovered without reload. Automated tests also covered the 15-second health poll and confirmed every automatic/retry request was GET health, with no resumed POST or generation. |
| Port occupied | Launched a second API while the owned test API held 8001: nonzero exit with Windows bind error 10048 and the new recovery hint. The first process remained running; no unrelated process was stopped. |
| Missing dependencies | Controlled simulation using `.venv/Scripts/python.exe -S -m api` (site-packages disabled) exited 1 with an explicit `requirements-api.txt` installation instruction. Normal dependencies were present; none were uninstalled. |

The default Vite proxy and expected origins were already correct and are unchanged. Both `http://127.0.0.1:8001/api/health` and `http://127.0.0.1:5173/api/health` returned `200`, `status:ok`, `live_enabled:false` during production-API verification. The launcher continues to bind only to loopback with proxy-header trust disabled. Its new diagnostics cover missing API packages and startup/import/bind failures without exposing credentials.

## Implemented UX changes

**Connection feedback.** A persistent connection panel distinguishes initial checking, unavailable service, reachable service with AI disabled, enabled AI, and the offline test harness. Retry reads only health. Health requests have a five-second timeout, do not overlap, abort on unmount, poll every 15 seconds while visible, and refresh on window focus. Reconnection never repeats a failed check or rescue. A gate rejection after a previously enabled page refreshes health without retrying generation. Lost results leave the original plan intact and explain recovery without implying that the interrupted action was repeated. Developer commands, ports and implementation terms are inside Advanced connection help.

**Interruption follow-through.** Saving an interruption brings a prominent affected-activity summary into view and focuses its heading after the modal closes. Overlaps are deduplicated across the day's interruptions. Flexible activities have a clear **Find a new plan** CTA, availability explanation and consent text about sending selected-day pending activities/interruptions to Meta. Fixed overlaps instead offer **Review commitment** and explain that their time and duration stay fixed. The existing deterministic preflight still guards all generation paths. Completed tasks are excluded, elapsed tasks remain pending, and an active overlap is labeled **In progress · still pending**. The summary explains that time already spent is not automatically deducted from the full pending activity.

**Review and language.** Renamed **Check day with Python** to **Check schedule conflicts**. Main copy describes checks and changes in ordinary scheduling language; implementation messages and execution data remain in Advanced details. Completion, explicit Apply confirmation, fresh Python revalidation, unchanged original during review, Keep original, postponed/unscheduled work, persisted Undo and date/input invalidation remain intact. Completed checks and proposals bring their result heading into view; critical errors remain visible and receive focus rather than being obscured below a long schedule. The rationale remains labeled **AI rationale · Unverified**.

**English dates and 24-hour input.** Authored day/week labels use explicit `Intl.DateTimeFormat('en-GB', ...)`; document language was already `en` and remains so. Activity, interruption and day-bound time editors now use reusable, labeled native hour/minute selects, covering every value from 00–23 and 00–59. Submission reads actual FormData values and retains `HH:mm` strings for the existing Python conversion. There is no rounding or five-minute step. Native date pickers remain browser/OS controlled; their calendar dialog can still be Vietnamese.

**Motion.** Existing teal `#205e60`, ink `#243e48`, pale sky `#f2f6f7`, mint `#e8f3ee` and amber `#fff1d8` retain the approved direction. A few existing sections receive one 280ms opacity/8px-translation reveal when they enter view. Native Web Animations and IntersectionObserver are used without dependencies; an observer watches newly inserted sections without replaying existing ones on edits. Default content is visible, so absent/failed observers or animation support do not conceal it. Reduced motion skips reveals and cancels running animations on preference changes. Errors, Fixed-conflict summaries, connection status and modal focus are not reveal targets; unsuccessful proposal sections are excluded too. Motion does not change layout dimensions.

## Preserved behavior and scope

`core/`, `api/app.py`, `app.py`, `ui/`, provider/request limits, existing Pydantic domain contracts, dependency lockfiles and the Streamlit fallback are unchanged. There are no changes to scheduling semantics, solver authority, paid-call limits or credential discovery. All model generation remains behind the exact process gate and an explicit action click; at most one correction, two provider requests, zero SDK retries and the existing finite phase timeouts remain in force. Neither polling nor form submission invokes generation. No library, database, authentication, calendar integration, cross-day optimization or public deployment was added.

`.env` remains ignored and untracked. Only its existence was checked by doctor; its contents were not inspected, printed or copied. Browser persistence remains versioned and browser/origin local. All user/model text remains escaped React text.

## Tests and build results

Verified with the existing `.venv` (Python 3.13.1, Streamlit 1.66.1, Pydantic 2.14.1, OpenAI SDK 2.54.0), Node 22.23.4 and npm 10.9.9. No dependency changes were needed.

| Check | Final result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q` | **284 passed in 24.28s**: all 281 existing tests plus an active-Flexible API test and two startup-diagnostic tests. |
| `npm.cmd test` | **41 passed**, 3 files, **5.44s** including environment/setup: all 28 earlier cases retained, with necessary label/picker adaptations, plus 10 journey/connection cases and 3 motion cases. |
| `npm.cmd run typecheck` | **PASS**, TypeScript no-emit check. |
| `npm.cmd run build` | **PASS**, 24 modules; Vite build 254ms. JS **270.19 kB / 82.77 kB gzip**; CSS **21.18 kB / 5.22 kB gzip**. |
| `scripts/doctor.py` | **DOCTOR PASS**, project virtual environment, key not set in process environment. |
| `python -m pip check` | **No broken requirements found.** |
| `scripts/demo_offline.py` | **A VALID, B VALID, C INVALID**, expected Fixed/busy conflict. Hand-authored deterministic examples only. |
| Production API + Vite proxy | Health **HTTP 200** from both addresses with generation disabled; actual conflict-check request succeeded. |

An initial full Python run produced 283 passes and the existing `test_example_scenarios[0-True]` Streamlit AppTest three-second startup timeout. This is the same intermittent local timing issue recorded in M6A. After shutting down QA previews, the complete unmodified fallback suite passed as reported above. No timeout increase, skip, fixture weakening or Streamlit change was made. The intermittent startup-test timing remains a limitation of local verification.

New frontend coverage includes unavailable/invalid health responses, health timeout and abort, late startup, polling/retry without POST replay, disabled/enabled gate distinctions, a gate changing after page load, service loss during a check, interruption save without generation, explicit CTA only, active Flexible overlap/full-duration payload, Fixed review/preflight, interruption edits invalidating review, explicit English dates under simulated `vi-VN`, all 24-hour/minute values, one-minute boundary persistence, reduced motion, one-time reveals, newly inserted sections, still critical errors and observer-failure fallback. Existing stale date/edit/in-flight results, acceptance/fresh validation, Undo, persistence and provider failures remain covered.

The API's active-Flexible test goes through actual ASGI → existing boundary/agent → real SDK MockTransport → unchanged Python validation, checking that the full original duration and current minute are transmitted. Startup tests never bind real sockets. Existing test guards block real HTTP and external sockets. Frontend tests replace fetch; no automated Meta call occurred.

## Desktop/mobile QA and screenshots

Used the available Chromium in-app browser at **1440×1000**, **390×844**, and **360×800**. The browser's native date/calendar controls used Vietnamese labels, as in the reported issue; authored headings/week labels were English and time selects contained only 24-hour digits. Browser automation did not offer a locale override, so no newly configured Vietnamese browser profile is claimed. Automated tests additionally set the navigator language to `vi-VN`. Native date popup localization remains visible and documented.

Verified local date moves through the actual editor, saving interruptions, automatic focus to the summary, normal conflict checking with AI disabled, enabled state through the offline harness, Before/After, explicit confirmation, fresh acceptance, reload persistence, Undo, Fixed-conflict review, and stale-result removal after editing an interruption. A real-time 13:00–16:00 Flexible test activity overlapped a 13:45–14:15 interruption while the browser clock showed 13:53: it stayed pending, was identified as in progress and retained its full 180-minute duration. No generation was requested for that manual active-activity example.

Two explicit Find a new plan clicks used the fixed three-activity browser fixture. Each produced one invalid hand-authored SDK completion and one valid correction: **four MockTransport completions total, two per click**, zero real Meta calls. The first proposal was confirmed/applied, reloaded and undone. The second was discarded by editing the underlying interruption. Health retries, saves, reloads and conflict checks produced no extra completions. These results demonstrate offline integration, not live Muse reliability. Manually entered records in screenshots are QA data; production first launch still seeds no plans.

Keyboard Tab reached the labeled activity input with a visible focus outline; Escape returned to the editor's invoking control. No horizontal document overflow was observed at 390px or 360px. This is browser viewport QA, not a physical-device or full screen-reader audit. Temporary viewport changes were reset, the QA tab closed, and owned API/Vite processes stopped.

| Screenshot | Evidence |
| --- | --- |
| [Desktop unavailable](screenshots/m6b/desktop-unavailable.jpg) | Clear service failure and Retry; unavailable online actions. |
| [Desktop AI disabled](screenshots/m6b/desktop-ai-disabled.jpg) | Reconnected API with gate off; distinct status. |
| [Mobile interruption, AI disabled](screenshots/m6b/mobile-interruption-disabled.jpg) | Affected activity and understandable next-step availability. |
| [Mobile time editor](screenshots/m6b/mobile-24-hour-editor.jpg) | English labels and 24-hour hour/minute controls; native date control retained. |
| [Desktop next step — offline](screenshots/m6b/desktop-next-step-offline.jpg) | Explicit Find a new plan action; hand-authored test labels. |
| [Desktop review — offline](screenshots/m6b/desktop-review-offline.jpg) | Friendly outcome and unchanged Before/After authority. |
| [Mobile review — offline](screenshots/m6b/mobile-review-offline.jpg) | Kept/moved/shortened and explicitly unscheduled work. |
| [Mobile confirmation — offline](screenshots/m6b/mobile-confirm-offline.jpg) | User approval before fresh check and application. |
| [Mobile Fixed conflict — offline](screenshots/m6b/mobile-fixed-conflict-offline.jpg) | Review commitment instead of silently moving Fixed work. |
| [Mobile active overlap — offline](screenshots/m6b/mobile-active-overlap-offline.jpg) | Active work stays pending; progress is not deducted automatically. |
| [Desktop English week — offline](screenshots/m6b/desktop-english-week-offline.jpg) | English day/date labels on actual local dates. |

Reviewed new controls and interaction changes with the installed frontend-design and web-design-guidelines skills and current [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md). Native labels/buttons, explicit focus, responsive wrapping, error visibility and reduced-motion fallback are retained. Review notes:

```text
web/src/TimePicker.tsx:6 — pass: labeled native controls, all minute values, keyboard access.
web/src/InterruptionSummary.tsx:9 — pass: named overlaps, fixed-action distinction, visible next step.
web/src/ServiceStatus.tsx:4 — pass: separate connection/gate states, health-only retry, optional diagnostics.
web/src/motion.ts:4 — pass: visible default, bounded one-time motion, reduced-motion/observer fallback.
```

## Manual run instructions and remaining limits

From the repository root, Terminal 1:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-api.txt
$env:DAYRESCUE_ENABLE_LIVE_AI = "0"
.\.venv\Scripts\python.exe -m api
```

Terminal 2:

```powershell
Set-Location web
npm.cmd ci
npm.cmd run dev
```

Open **http://127.0.0.1:5173** and keep both terminals open. If React was opened first, start the API and use Retry connection or wait for health polling. Check schedule conflicts works with the gate off. Neither the report nor M6B authorizes a paid test. Use only the existing isolated test harness for offline QA, stop it afterwards, and never expose this unauthenticated service publicly. Detailed diagnostics and gate behavior are in [web/README.md](../web/README.md).

The fallback remains `.venv/Scripts/python.exe -m streamlit run app.py` with the process gate disabled. Native date-calendar localization, single-day integer-minute scheduling, no automatic progress deduction, browser-only storage, local clock trust and lack of public-service authentication remain intentional boundaries. Motion gracefully stays static on unsupported observers/animation APIs and after a motion-preference change. The browser must run JavaScript for the React application itself; optional motion never supplies hidden-by-default styles.

No reproducible blocking issue remains in the verified local journey. Live Meta behavior was deliberately not re-tested. Stop for technical review; do not merge or deploy automatically.
