# M5D — Streamlit UX integration

Date: 3 November 2026, Asia/Saigon. Branch: `feat/m5d-streamlit-ux`. Recommendation: **ready for technical review**. No merge or deployment is authorized by this report.

## Prerequisite and scope

GitHub PR #10 was verified **MERGED**, merged at `2026-11-03T10:24:45Z`, with merge commit `e663ef4580ee28a0fe146c5bb220b1d9a2ebe4fa`. Fetched origin, fast-forwarded main from `96059c9` to `e663ef4`, then created the requested branch. The starting working tree was clean.

Read AGENTS.md, the approved M5C design document and prototype, current application/UI code, the existing domain/validation/orchestration and presentation contracts, and relevant regression tests. Applied the installed frontend-design and web-design-guidelines skills. This milestone follows the approved daily-planner direction within native Streamlit rather than reproducing the standalone prototype's shell.

Changed production files: `app.py`, `ui/agent_result.py`, `ui/conflicts.py`, `ui/live_generation.py`; added `ui/planner.py` and `.streamlit/config.toml`. Added one test module, this report and seven screenshots. **All core files, existing 235 tests, A/B/C fixtures and dependency declarations are unchanged.** No dates, persistence, weekly scheduling, database, new dependency or framework migration was introduced.

## What changed

### Today's plan

Custom day now shows its chronological activity cards near the top, before the editing controls. Cards expose start/end, duration, priority, Fixed/Flexible and either an explicit shortening minimum or “Shortening not allowed.” Current time and the day window remain local times; there is no invented calendar date.

The full existing editor is available in the collapsed **Edit planned activities** disclosure. It retains current time, day bounds, the 3–8 activity limit, names, times, durations, priority, fixed flags and optional shortening minima. A reserved native container lets the schedule render above the widgets only after conversion succeeds. Invalid inputs clear old results and withhold schedule cards/tables rather than displaying a stale plan.

### Something changed?

The existing 0–10 busy-window controls are grouped as interruptions. Every interruption is explicitly unavoidable busy time; no movable-interruption toggle or soft constraint was added. The original widget keys and domain conversion remain intact.

Each valid busy interval shows a readable summary of overlapping activities and their Fixed/Flexible identities. Overlap uses half-open intervals for feedback, so touching endpoints do not conflict. No detected overlap is explicitly **not** proof of full feasibility. `detect_hard_conflicts()` remains the preflight authority. Fixed-conflict errors and affected activities remain visible outside the technical disclosures; codes and full detail remain available on demand.

### Rescued day

A valid agent result first shows a short outcome summary, followed by **Before · Original plan** and **After · Proposed plan**. Times and shortening descriptions come from actual activity/proposal values by stable activity ID, not matching titles or model rationale. Kept, moved/adjusted and postponed groups come from fresh deterministic validation, including when stored disposition lists have been altered.

Postponed items have an explicit **Still unscheduled** section with their original times and “Not assigned to another day.” A proposal scheduling no flexible work is displayed honestly with an empty-schedule message and its unscheduled items. No optimality or guaranteed usefulness claim is made, and the proposal never silently replaces or saves the original.

Successful results pass the existing `prepare_agent_result()` guard and an additional detached-schema/fresh-validation check in `prepare_comparison()` before cards or summaries render. Failed, stale or malformed results do not display a revised schedule or rationale. Invalid, infeasible and provider failures retain visible critical messages and original-input recovery guidance.

### Optional detail and evidence labels

Original/proposed tables, fixed-check details, validation status/codes and the bounded agent trace are in collapsed disclosures. AI rationale remains explicitly unverified, bounded by the existing presentation layer and rendered using `st.text`, never custom HTML or executable content.

Example mode still uses the original hand-authored A/B/C fixtures and real deterministic Python validation. It is prominently labeled offline and not Muse output. It shows a comparison only for an accepted fixture proposal; C's rejected revised schedule is withheld. Example mode's Generate button remains disabled. Custom mode's explicit **Generate with Muse Spark** button keeps its original key and gating behavior and is styled as the primary action.

## Design and safety implementation

The native theme adopts the M5C canvas `#f2f6f7`, ink `#243e48`, teal `#205e60` and white surfaces. Local cards use green for Fixed, lavender for Flexible/adjusted and amber for interruptions/unscheduled work, with text labels rather than color alone. Native Streamlit layout, forms, expanders, keyboard behavior and focus styling are retained.

Custom CSS targets only app-owned `dr-*` classes, including responsive card text wrapping. It contains no Streamlit DOM/test-ID selectors, generated class names, widget overrides, focus suppression or added animation. Custom HTML escapes dynamic activity names, interruption labels and displayed change text. Rationale stays in native plain text. Card titles use strong text inside semantic activity lists, avoiding duplicate generated heading anchors across Before/After.

Browser QA found native caption opacity of 0.6. Essential notes retain the caption element but use an app-owned dark text span so the rendered text remains readable without selecting or changing Streamlit internals. Main card metadata uses `#536b74`; its contrast on the canvas is about 5.18:1. Fixed/lavender/amber text pairs retain the M5C palette's contrast above 4.5:1. This is a scoped review, not full accessibility certification.

| Contract | Preservation evidence |
| --- | --- |
| Exact process opt-in and explicit click | `core/live_generation.py` unchanged; UI invocation branch, second gate check and snapshot/store flow unchanged; old gate/click tests pass |
| At most two requests; zero SDK retries; finite timeouts | Agent/provider/core invocation files unchanged; existing MockTransport request-count/configuration checks pass |
| Fingerprint invalidation and stale-result rejection | Session functions and all widget callbacks retained; original invalidation tests plus new busy-label/time/minimum cases pass |
| Python-only acceptance | Existing preparation revalidates; comparison additionally parses a detached proposal and calls the existing validator |
| Sanitized failure handling | Existing messages/trace whitelist retained; errors stay visible, raw provider exceptions never enter the new HTML |
| Local credentials | `.env` not opened or displayed; metadata checks confirm it is untracked and ignored; no secrets added to the theme config |
| Offline automation | Existing autouse fixture blocks real HTTP/external sockets; injected providers and SDK MockTransport remain test-only |
| Repository visibility | GitHub metadata verified PRIVATE; visibility unchanged |

## Verification results

Environment: Windows, Python 3.13.1 in `.venv`; Streamlit 1.66.1, Pydantic 2.14.1, OpenAI SDK 2.54.0, python-dotenv 1.2.4, pytest 9.2.0. No dependency was installed or updated.

| Verification | Result |
| --- | --- |
| First implementation against all original tests | **235 passed in 22.22s**; no existing test changed |
| Focused new UX checks | **16 passed in 5.00s** |
| Final complete suite: `.venv/Scripts/python.exe -m pytest -q` | **251 passed in 22.51s**, no failures or skips reported |
| `.venv/Scripts/python.exe scripts/doctor.py` | **DOCTOR PASS** |
| `.venv/Scripts/python.exe -m pip check` | **No broken requirements found.** |
| `.venv/Scripts/python.exe scripts/demo_offline.py` | A VALID, B VALID, C INVALID; C reports FIXED_BUSY_CONFLICT and BUSY_OVERLAP |
| Final Streamlit startup | `127.0.0.1:8502/_stcore/health`: **HTTP 200, ok**; root HTML shell: **HTTP 200**; application rendered in the browser |
| Fresh final browser session | Application rendered after clean restart; no captured console error/warning entries in the fresh tab |
| Diff checks | No changes to any core file, existing tests or requirements; `git diff --check` passed |

The test process had live AI disabled by default; the existing suite independently removes the gate and blocks external network. Tests that exercise a generation click use injected test providers or the real SDK with in-memory MockTransport only. The 16 new cases cover chronological cards and retained controls, exact overlap boundaries, zero/clear interruptions, A/B fixture comparisons and postponed work, actual shortening and forged stored dispositions, escaped user text/plain rationale, all four failure statuses, all-flexible postponement, busy label/start/end/minimum edits clearing results, and fresh rejection of a tampered proposal.

Startup/visual QA used a loopback-only Python process with `DAYRESCUE_ENABLE_LIVE_AI=0`, MODEL_API_KEY removed from the child environment, telemetry disabled, real HTTP transports blocked and external socket connect/connect_ex blocked. No browser generation request was launched. During development an already-running preview retained an older imported module; the preview was restarted before final verification. Reconnection errors from those deliberate shutdowns are not recorded as a final startup failure.

Offline fixtures and tests are **deterministic Python evidence**, not live Muse output. Earlier user-reported connectivity, structured-output and correction successes remain separate manual history; no additional Muse reliability, latency or billing claim is inferred here.

## Browser visual QA

Inspected the production Streamlit app in the Codex in-app browser at **1440×1000 desktop** and **390×844 mobile**. Also checked Custom day at **320px**, with page/client width both 320px. At 390px both remained 390px for the plan, comparison and conflict views; no horizontal page overflow was observed. Technical tables remain native, optionally scrollable controls.

Exercised native activity-name editing, a Fixed flag, explicit shortening permission, busy-window count, hour/minute keyboard editing and a fixed-activity overlap. The disabled Generate control was confirmed. Reviewed actual B fixture times (Study moves from 13:00 to 16:30), mobile stacked comparison, A's explicit unscheduled reading, and critical conflict feedback outside expanders. No real model result was generated for screenshot purposes; live-result trace/rationale and failure-state coverage are AppTest evidence.

Screenshots are actual viewport captures, not full-page exports:

| File | Evidence |
| --- | --- |
| [desktop-plan.jpg](screenshots/m5d/desktop-plan.jpg) | Custom inputs, visible properties and collapsed editor |
| [mobile-plan.jpg](screenshots/m5d/mobile-plan.jpg) | Wrapped activity metadata and native navigation |
| [desktop-interruption-conflict.jpg](screenshots/m5d/desktop-interruption-conflict.jpg) | Busy inputs, affected fixed activity and visible critical error |
| [mobile-interruption-conflict.jpg](screenshots/m5d/mobile-interruption-conflict.jpg) | Readable stacked feedback and optional codes/details |
| [desktop-comparison-offline.jpg](screenshots/m5d/desktop-comparison-offline.jpg) | Real Python-validated hand-authored B comparison |
| [mobile-comparison-offline.jpg](screenshots/m5d/mobile-comparison-offline.jpg) | Sequential original/revised cards and moved-time text |
| [mobile-unscheduled-offline.jpg](screenshots/m5d/mobile-unscheduled-offline.jpg) | A's postponed reading is explicitly not reassigned |

Visual QA corrected card padding being overridden by native Markdown defaults by increasing specificity using only the app's own classes. It also prompted the caption-contrast adjustment and semantic card-title cleanup. No new backend behavior was introduced for these fixes.

## Guideline review and remaining differences

Reviewed the changed UI against the freshly retrieved [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md). Sentence case follows the approved design. Native Streamlit controls own widget labeling, focus, busy rendering and responsive columns; custom cards are read-only.

```text
ui/planner.py:55 — pass: custom activity content escaped; no scripts or interactive HTML
ui/planner.py:118 — pass: revised content gated by fresh Python validation
ui/agent_result.py:54 — pass: critical errors outside optional detail; unverified rationale plain text
ui/conflicts.py:10 — pass: readable affected activities outside collapsed technical codes
app.py:41 — P2 limitation: conversion errors are grouped; no automatic focus to the first invalid field
```

Remaining deliberate differences from M5C:

- Native page chrome, mode radio and number/count controls remain. The separate M5C sidebar, date navigation, Add Activity dialog and decorative recovery note were not copied into production.
- The 3–8 activity limit remains a native count control; editing lives in a disclosure rather than a custom modal. Interruption inputs use native expanders and retain their established labels/keys.
- Desktop Before/After uses native columns; mobile stacks them sequentially and requires scrolling. Native page spacing and typography differ from the prototype; this is **not pixel-identical replication**.
- The weekly concept stays in the standalone prototype only. There is no saved date, history, acceptance transaction, automatic carryover or calendar integration.
- Technical tables and the agent trace can require internal scrolling. Optional native captions keep their framework styling; this was not a full screen-reader, contrast or physical-device certification.
- A real provider spinner, unverified live rationale and external failures were not exercised in a live browser call. Existing/new offline AppTests verify their rendering and behavior. There is no need or authorization for a new Meta request to complete this milestone.

No blocking regression was observed in the executed checks. The grouped-field-error focus limitation and mobile scrolling are nonblocking review considerations, not a reason to expand the hackathon scope.

## Review and launch

For an ordinary offline review from the repository root:

```powershell
$env:DAYRESCUE_ENABLE_LIVE_AI = '0'
.\.venv\Scripts\python.exe -m streamlit run app.py --browser.gatherUsageStats=false
```

Review checklist:

- [x] PR #10 merged; main fast-forwarded; dedicated M5D branch created.
- [x] All original tests preserved, focused UX tests added, full suite/checks passed.
- [x] Desktop/mobile rendering inspected and screenshot evidence recorded.
- [x] Protected core/contracts/fixtures/dependencies unchanged; live generation disabled during QA.
- [ ] Technical reviewer checks the UI diff and native-layout tradeoffs before authorizing a merge.

The handoff records the final commit SHA after this report is committed. Commit/push are for review only. No automatic merge, deployment, repository publication or live API request is part of M5D.
