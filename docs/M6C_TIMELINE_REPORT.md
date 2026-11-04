# M6C — Unified schedule timeline

Verified on 2026-11-04, Windows / Asia/Saigon. Branch: `feat/m6c-unified-timeline`, created from clean, fast-forwarded `main` at `50fb596` (M6B merged as PR #13). Ready for technical review. No merge or deployment occurred; the repository remains PRIVATE.

The owner reports a successful real React/Muse rescue with Apply and Undo. That report is separate from this task's verification: no real Meta request was made for M6C.

## Defect and change

The main schedule, Before and After each mapped only activity records. Busy intervals were already stored and supplied to Python as constraints, but only the separate What changed section displayed them. A valid accepted schedule therefore looked incomplete.

All three views now use `web/src/Timeline.tsx`. It combines the displayed activities with the selected day's existing interruption records for rendering only. Before and After receive the **same unchanged interruption array**. After's activity records still come only from the accepted, Python-validated proposal. My day uses the persisted local activity/interruption records, including after Apply or reload. No constraint is fabricated from a proposal item.

Items sort by numeric start minute. When starts tie, busy intervals precede activities, then end time and stable identity provide a deterministic order. Overlapping intervals keep their full original ranges: the renderer does not truncate, merge or reschedule them, or imply that conflicts were solved before validation. Repeated busy identities render once per timeline. Distinct records with identical labels/times remain distinct.

Busy cards preserve the original label, start and end, and display the original local day key as an English date. Their `<time>` attribute is a local date/time without UTC conversion. There is no storage migration or added date assignment. The separate **What changed** section remains available for editing and overlap context. Seeing the interval there and in the schedule is intentional; it appears only once inside each schedule list.

## Visual and interaction semantics

| Item | Presentation |
| --- | --- |
| Fixed activity | Existing Fixed badge and green border; original controls and shortening restrictions retained. |
| Flexible activity | Existing Flexible badge and lavender border, with explicit shortening permission. |
| Unavoidable busy time | Amber card, dashed outline/brown border, dated time range, duration, explicit Unavoidable busy time label and “Reserved by you” description. No priority, completion checkbox or AI activity controls. |
| Moved/shortened activity | Violet adjusted card and explicit old/new time or duration text. |
| Still-unscheduled activity | Remains in the separate Still unscheduled section, with no assigned time and no implication of another date. |

After Apply, changed-activity annotations are derived from the real current acceptance snapshot and persisted activity values. They survive reload. Annotations are shown only while that acceptance revision is current, so later manual edits are not presented as accepted AI changes. Undo restores the original activities and the same busy records; the corresponding annotations disappear or reflect the restored acceptance history. Nothing new is persisted for display.

Named ordered lists identify Daily schedule, Before schedule and After schedule. Comparison cards use level-four headings beneath Before/After level-three headings. Labels, rather than color alone, distinguish activities from constraints. Busy labels and metadata wrap on narrow screens, and all text remains React-escaped. A busy-only day also displays its reserved interval without inventing an activity. Completed work remains explicitly marked in My day; the proposal workflow continues to handle pending activities only.

The existing calm teal/mint/amber direction, visible control focus, 24-hour time display, English date formatting and reduced-motion behavior are retained. Review used the installed frontend-design guidance and current [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md).

## Safety and preserved contracts

No files under `core/` or `api/` changed. The agent correction loop, exact live gate, request limit, SDK retries/timeouts, Python validator, request/response contracts, input conversion and credential handling are unchanged. `web/src/state.ts` and `web/src/api.ts` are unchanged. Busy intervals remain `busy_windows`; they are never inserted into `ProposedPlan.scheduled` or `postponed_ids`. Outcome counts still refer to activities.

Apply still requires confirmation and fresh Python revalidation. Keep original, Undo, local persistence, date navigation, completed-state handling and stale/in-flight result rejection remain covered by existing tests. There is no cross-day AI scheduling, framework/dependency change, background generation or public API exposure. Streamlit and its tests are unchanged. `.env` remains ignored and untracked; its contents were not inspected.

## Verification

| Command | Result |
| --- | --- |
| `.venv/Scripts/python.exe -m pytest -q` | **284 passed in 27.07s**. All existing Python tests retained. |
| `npm.cmd test` from `web/` | **47 passed**, 4 files, **6.58s** including environment/setup. All 41 existing frontend tests retained, plus 6 focused tests. |
| `npm.cmd run typecheck` | **PASS**, TypeScript no-emit check. |
| `npm.cmd run build` | **PASS**, 25 modules, 182ms Vite build. JS **272.72 kB / 83.46 kB gzip**; CSS **21.70 kB / 5.33 kB gzip**. |
| Diff/credential checks | No core, API, Streamlit, storage-contract or transport changes; `.env` untracked; repository PRIVATE. |

The six new React tests cover:

1. Mixed chronological Daily/Before/After timelines, one busy card per list, original label/date/times, adjusted styling, and activity-only proposal payloads.
2. Apply, a React remount representing reload, persisted movement/shortening labels, unscheduled work, Undo and date isolation without additional generation.
3. Busy-only days and continued editing through What changed.
4. Overlapping activities/busy intervals retaining their full ranges, source-data immutability, active busy state and escaped labels.
5. Identity-based duplicate suppression while preserving distinct same-label/same-time events.
6. Fixed/Flexible classification and exclusion of unscheduled work from timed cards.

Integration tests reuse the genuine deterministic Python-validated, hand-authored fixture. Fetch is mocked in React tests. The existing Python test guard blocks real networking; no automated Meta calls occurred.

## Browser QA and screenshots

Inspected the **production build** served by `npm.cmd run preview` on loopback port 4173, with the existing isolated `tests/browser_api_fixture.py` at 8001. That harness blocks external networking and `.env` reads and forces real-SDK MockTransport. It is test-only and was not modified. A fresh preview origin initially showed an empty plan; all test activities and the visitor were entered through the actual controls for November 5.

One explicit Find a new plan click produced exactly **two offline hand-authored completions**, an invalid first proposal and a valid correction. These are not Muse output. Before contained study 09:00–10:00, visitor 09:15–09:45, Fixed call 10:00–10:30 and reading 11:00–11:30. After contained the same visitor, the same Fixed call and study moved/shortened to 10:30–11:00; reading was explicitly unscheduled.

Confirmed Apply, fresh validation, reload and Undo through the browser. After reload, My day retained the visitor card once and retained the accepted study changes. Undo restored the original study/reading slots without changing the visitor. Navigating to November 6 showed an empty day; returning to November 5 and reloading preserved the restored mixed timeline. What changed still exposed the visitor editor. No form save, reload, navigation or Undo generated another completion.

Desktop was checked at **1440×1000**, mobile at **390×844**, and narrow wrapping at **360×800**. No horizontal document overflow was observed. The main timeline and comparison kept readable labels, time ranges and chronological DOM order. Mobile screenshots show the accepted busy card and the moved/shortened/unscheduled details in separate viewport captures. These are viewport checks, not a full physical-device or assistive-technology audit. Native date-calendar localization remains the existing browser/OS limitation.

| Screenshot | Evidence |
| --- | --- |
| [Desktop original — offline](screenshots/m6c/desktop-original-offline.jpg) | Original study and overlapping visitor are both visible with their full ranges. |
| [Desktop comparison — offline](screenshots/m6c/desktop-comparison-offline.jpg) | The identical visitor appears in both Before and After, alongside Fixed and adjusted activities. |
| [Desktop accepted details — offline](screenshots/m6c/desktop-applied-details-offline.jpg) | Accepted movement/shortening, still-unscheduled work, Undo and retained editing context after reload. |
| [Mobile accepted busy card — offline](screenshots/m6c/mobile-applied-busy-offline.jpg) | Visitor remains in the main accepted timeline, with label/date/time and explicit constraint classification. |
| [Mobile accepted changes — offline](screenshots/m6c/mobile-applied-unscheduled-offline.jpg) | Adjusted study and explicitly unscheduled reading remain readable. |

## Review handoff

The implementation is presentation-only. A chronological card list is not a time-scaled calendar: overlapping original intervals remain visible as separate cards, with exact ranges. The Python validator remains the sole scheduling authority. Busy intervals are editable through What changed and are never AI-schedulable activities. The owner's reported real Muse success was not repeated or used as new automated evidence.

Local startup instructions remain in [web/README.md](../web/README.md). Standard manual preview can run with `DAYRESCUE_ENABLE_LIVE_AI=0`; ordinary busy cards require no model request. For offline rescue QA, use only the explicitly isolated test harness with its specified fixture inputs. Temporary browser viewport overrides were reset, the QA tab closed, and the owned preview/API servers stopped.

Commit and branch details are supplied in the final handoff. Stop for technical review. Do not merge or deploy automatically.
