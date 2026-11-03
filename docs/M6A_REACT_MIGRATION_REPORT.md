# M6A — React/FastAPI integration report

Verified locally on 2026-11-03, Windows, Asia/Saigon. Ready for technical review of the local vertical slice. No merge or deployment is authorized or performed. No real Meta request was made during this milestone.

## Release protection

PR #11 (M5D) was confirmed merged. Work began with a clean tree, fast-forwarded `main` at `7a7a98176a36e4c3c62d3522b3b005bb763c25e1`, on `feat/m6a-react-migration`. The repository remains **PRIVATE**. The final delivery message supplies the committed SHA.

`app.py`, `ui/`, `core/`, all 251 pre-existing tests, and the original `requirements.txt` are unchanged. The existing Streamlit release remains the fallback. API dependencies are installed separately through `requirements-api.txt`; full tests now require that file. `.env` remains ignored and untracked. Its contents were not inspected or copied.

## Implemented journey

| Area | Result |
| --- | --- |
| First launch | Empty selected local date, sunrise illustration, Make your day, explicit demo-only sample action. No automatic seed or storage write. |
| Activities | Named native-dialog editor, local planned date/start/duration, priority, Fixed/Flexible, explicit shortening minimum, stable IDs, editing/removal and explicit completion. Date edits move only the chosen record. |
| My day | Chronological readable cards, date navigation, today's current local clock, current/upcoming pending work, elapsed slots still pending, visible editing. |
| My week | Seven actual local dates; chronological previews, completion/unscheduled labels, selected-day creation and navigation. No AI operation across dates. |
| Interruption | Distinct amber action, named dated unavoidable busy interval, affected pending activities and named Fixed conflicts. User must explicitly edit a commitment; Fixed is never silently downgraded. |
| Rescue | Explicit button → Python preflight → existing live boundary → existing bounded agent/SDK → fresh Python validation → review. The process gate is mandatory at the API. |
| Review | Real accepted scheduled items, counts from ValidationResult, Before/After, kept/moved/shortened descriptions, postponed work still unscheduled, unverified escaped rationale, optional validation/trace. No optimality claim. |
| Acceptance | Original remains unchanged during review. Explicit confirmation, fresh Python validation against the current clock, date/input binding checked before and after the request, then a local revision snapshot. Keep original and persisted Undo work. |

Only pending activities are converted into the existing DayContext. Completed activities remain local and separate. Unscheduled work stays on its selected date without an assigned slot until explicitly edited and scheduled. The UI permits 8 activities total per date and 0–10 interruptions; the existing core's 1–8 pending-activity contract is reused. Streamlit's original 3–8 editing contract is unchanged.

Today uses the browser's actual local minute. Future selected dates use 00:00 as their pending-work clock; past dates cannot request rescue in the UI. Dates are local `YYYY-MM-DD` keys made with local getters, parsed at local noon for calendar navigation. UTC timestamps are used only for acceptance metadata, never date keys. The existing core still handles integer minutes within one day.

## Architecture and safety

`web/` contains React, TypeScript and Vite, with no component framework or scheduling library. `api/` adds transport Pydantic models and conversion through the existing `build_day_context()`. It delegates to unchanged `detect_hard_conflicts()`, `generate_live_result()`, `run_agent()`, `prepare_agent_result()` and `validate_plan()`. Frontend overlap previews and storage-integrity checks are not scheduling authorities.

Endpoints are GET `/api/health`, POST `/api/validate`, and POST `/api/rescue`. The launcher binds 127.0.0.1:8001, disables proxy-header trust and access logs. Host and actual client must be loopback. POST requires JSON and an expected development Origin; generation additionally requires its action header. CORS permits only localhost/127.0.0.1 on ports 5173/4173, without credentials. A declared request-length guard and bounded schema lists limit ordinary requests. This is a local development adapter, not a hardened or authenticated public service. CORS behavior follows the [FastAPI documentation](https://fastapi.tiangolo.com/tutorial/cors/); Vite binds explicitly to loopback using its [server options](https://vite.dev/config/server-options).

Only the exact server process value `DAYRESCUE_ENABLE_LIVE_AI=1` enables generation. Health, preflight, startup and React rerenders do not read credentials or request completions. Vite `.env` loading is disabled. The unchanged lazy Python boundary loads the ignored root `.env` only after preflight permits invocation. Existing model `muse-spark-1.3`, low reasoning, 2048 completion tokens, zero SDK retries, finite phase timeouts and client cleanup remain intact. There is at most one correction after deterministic validation rejection, for at most two provider requests. API errors/malformed output terminate without a correction retry.

A process-local nonblocking lock prevents concurrent generation, and a bounded ten-minute UUID replay cache rejects repeated submissions. There are no background requests or automatic request retries. These controls do not impose a lifetime paid-request quota or make a public endpoint safe. HTTP input and unexpected service errors are sanitized; raw request values, provider messages and exception diagnostics are not returned. Failure results cannot expose a plan or rationale. All user/model text is rendered as escaped React text, without custom HTML insertion or execution.

The API fingerprint binds canonical inputs, date and local revision. Clock advancement is deliberately excluded from the binding, because Apply uses fresh current-clock Python validation instead of treating the request clock as frozen. The client separately binds the entire local day snapshot, invalidates on edits/date changes, discards late responses, and checks again across asynchronous acceptance. Acceptance never calls Meta.

## Browser persistence

`dayrescue.plans.v1` stores only versioned whitelisted dated activities, interruptions, bounds, demo flags and up to five prior acceptance snapshots per date. Credentials, raw responses, rationale and traces are excluded. Loading validates the schema and IDs; unsupported/corrupt versions are retained and require an explicit reset, rather than silently erased. Storage failures show that changes are only in memory. A write ID detects newer data before overwriting, and storage events load another tab's latest plans, close stale editors and invalidate review. This reduces accidental overwrites; localStorage offers no transactional multi-tab guarantee.

Undo restores a persisted snapshot only while its acceptance revision is current. Later edits disable that restoration rather than destroying newer work. Browser/origin changes or clearing site data lose access to plans. There is no cloud sync, export, encryption, account or backup. The storage reader caps 1,000 date entries and does not prune old dates automatically.

## Exact verification results

Environment: Python 3.13.1, Streamlit 1.66.1, Pydantic 2.14.1, OpenAI SDK 2.54.0, FastAPI 0.162.0, Node 22.23.4, npm 10.9.9. Installing optional FastAPI dependencies replaced none of the existing baseline Python packages. New web packages are pinned with a committed lockfile.

| Check | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q` | **281 passed in 25.86s**: all 251 originals + 30 API tests. |
| `npm.cmd test -- --run` | **28 passed**, 2 files, 9.42s including test environment/transform setup. |
| `npm.cmd run build` | **PASS**, TypeScript no-emit check + Vite production build; 19 modules. JS 260.28 kB / 79.89 kB gzip; CSS 18.42 kB / 4.74 kB gzip. |
| `scripts/doctor.py` | **DOCTOR PASS**; key not set in process environment. Only `.env` existence was checked. |
| `python -m pip check` | **No broken requirements found.** |
| `scripts/demo_offline.py` | **A VALID, B VALID, C INVALID**, with C's expected FIXED_BUSY_CONFLICT/BUSY_OVERLAP. Hand-authored offline examples only. |
| `npm.cmd audit --omit=dev` | **0 vulnerabilities** reported at verification time. |
| API startup, generation disabled | Direct `/api/health` HTTP **200**, `live_enabled:false`; Vite proxy health HTTP **200**, same value. External outbound networking blocked in the verification process. |
| React dev page | HTTP **200** at 127.0.0.1:5173; browser health, CRUD, persistence and preflight work against the actual API. |
| Streamlit fallback startup | Headless loopback port 8503, generation disabled; page and `/_stcore/health` both HTTP **200**. |

An earlier full Python run, while frontend checks ran concurrently, produced 280 passes and one existing Streamlit AppTest three-second startup timeout (`test_example_scenarios[0-True]`). The complete standalone rerun above passed without changes to Streamlit or its tests. This is a local timing observation, not hidden test failure or evidence that the fallback changed.

API tests exercise actual ASGI requests and the real SDK with in-memory MockTransport: exact gate values, no credentials/model calls on health/preflight, local host/client/Origin/action checks, schema/time/duplicate/shortening rejection, request-size/type rejection, fixed preflight with zero requests, one successful completion, invalid-then-valid two-completion correction, timeout/429/500/malformed/two-invalid failures, safe error canaries, zero retries, finite timeouts, client closure, UUID replay, all meaningful fingerprint changes and current-clock rejection at acceptance.

Frontend tests cover empty first launch/no auto-save/no POST on mount or rerender, CRUD and explicit date moves, native date/time submission, explicit completion/current activity, seven-day navigation/reload, versioned storage/corruption/quota handling, gate/preflight, failure suppression, real deterministic proposal comparison, no automatic overwrite, confirmation/cancel/keep original, fresh-check failure, late/stale responses, date/edit changes, cross-tab invalidation, acceptance persistence, Undo, unscheduled items and the explicit sample action. No real network or Meta call is permitted in automated tests.

## Browser and visual evidence

Inspected in the available Chromium in-app browser at 1440×1000 desktop, 390×844 mobile, and a 360×800 narrow form check. No horizontal document overflow was observed at the mobile widths. Native dialog Escape/focus return and Tab focus ring were checked; the console contained no captured errors or warnings at the final check. This is not a full assistive-technology or physical-device accessibility audit.

Manual flow: entered three activities through the real forms; moved an activity to November 4 and reloaded to verify its local date; observed elapsed work remaining pending; created/edited an interruption; obtained the named Fixed conflict from the actual Python API with live generation disabled. Fixed time/duration remained unchanged. Returned to a nonconflicting interruption, then ran the test-only browser harness through React → HTTP → existing boundary/agent → real SDK MockTransport → Python validator → review → confirmation → fresh Python check → local acceptance. The transport recorded **exactly two offline completions**, one invalid followed by a valid hand-authored correction. Reload preserved the accepted plan and unscheduled reading; Undo restored the original. No live Muse reliability conclusion follows.

The harness is isolated in `tests/browser_api_fixture.py`, explicitly blocks external networking and `.env` loading, and requires exact named fixture inputs. It is not imported by production. Its successful responses add an offline evidence label, displayed in the frontend. Accepted fixture data remains marked demo after reload. Production startup was restored with the gate disabled after this check. Owned preview processes are stopped at handoff.

Browser QA found a native date/time issue: the displayed control value could change before a React change event, causing an older date to save. Editors now keep native date/time values uncontrolled and read actual FormData on submission. A focused regression test covers native value changes followed by another React field edit. Week previews and Before now display chronological ordering.

| Screenshot | Content / evidence |
| --- | --- |
| [Desktop empty](screenshots/m6a/desktop-empty.jpg) | Current local date, no prepopulated plan, production gate disabled. |
| [Mobile empty](screenshots/m6a/mobile-empty.jpg) | Real empty-state controls at mobile width. |
| [Desktop plan](screenshots/m6a/desktop-plan-offline.jpg) | Manually entered test activities; explicit offline banner. |
| [Desktop week](screenshots/m6a/desktop-week-offline.jpg) | Seven actual dates and chronological test activities. |
| [Mobile week](screenshots/m6a/mobile-week-offline.jpg) | Stacked header and responsive week grid start; offline label. |
| [Mobile editor](screenshots/m6a/mobile-editor.jpg) | Native dated activity editor, shortening permission and accessible controls. Manually entered test activity. |
| [Fixed conflict](screenshots/m6a/desktop-fixed-conflict.jpg) | Actual deterministic Python result for manually entered test inputs, live disabled. |
| [Outcome summary](screenshots/m6a/desktop-proposal-offline.jpg) | Real Python validation of hand-authored SDK fixture, explicitly offline. |
| [Before/After](screenshots/m6a/desktop-comparison-offline.jpg) | Kept call, moved/shortened study, unscheduled reading. Explicitly offline; not Muse output. |
| [Confirmation](screenshots/m6a/desktop-confirm-offline.jpg) | Confirmation before fresh validation/application of the offline fixture. |
| [Mobile accepted plan](screenshots/m6a/mobile-applied-offline.jpg) | Same offline fixture after acceptance/reload; reading explicitly unscheduled and Undo visible. |

The approved M5C document/prototype informed the calm teal, pale sky/mint surfaces, sunrise mark, airy hierarchy and warm interruption action. This is not a pixel-identical replication. Real dated navigation, empty states, local-storage disclosure, completion, dialogs, persistent revisions and live-gate status replace the static concept's assumptions. Week cards wrap to four/two columns at narrower breakpoints. Before/After stacks on mobile rather than compressing two timelines. Local system fonts replace external typography dependencies; browser-native date/time widgets follow the browser locale (Vietnamese in these screenshots).

UI source was reviewed against the installed frontend-design skill and the current [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md). Semantic controls, labels, focus rings, reduced-motion handling, long-text wrapping and local assets are implemented. Review notes:

```text
web/src/App.tsx — pass: native actions, skip link, explicit state/error feedback, escaped text.
web/src/Forms.tsx — pass: labeled controls, native modal, focus return, unsaved draft warning.
web/src/styles.css — pass: visible focus, responsive wrapping, reduced motion, explicit transition properties.
```

## Limits and review handoff

No reproducible blocking defect remains in the verified local flow. The live provider path is integrated and covered through MockTransport; it was deliberately **not reverified with paid Meta requests**. Earlier user-reported live Streamlit results remain separate evidence, not proof of this frontend's live behavior.

Keep the API local. Public hosting would require an explicitly reviewed authentication/credit-control boundary, deployment topology, origin configuration and operational controls. The frontend relies on the local browser clock and timezone; there is no timezone/DST appointment engine, overnight scheduling, recurrence, notifications or multi-device sync. Undo retains bounded snapshots and protects later edits; it is not a general edit history. Mobile checks used browser viewport emulation, not physical-device keyboards or screen readers.

Cross-day recommendations remain future work: they would need an explicit user-approved candidate date, loading that date's actual constraints, separate Python validation, complete-input binding for both dates, clear confirmation and atomic undo across dates. This milestone makes no such recommendation or silent date assignment.

Local commands, gate behavior and the fallback launch are documented in [web/README.md](../web/README.md). Stop here for technical review of the pushed feature branch. Do not merge or deploy automatically.
