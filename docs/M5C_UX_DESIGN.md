# M5C — DayRescue product UX concept

Design study dated 3 November 2026, Asia/Saigon. Branch: `feat/m5c-ux-concept`, based on main `96059c9` after fetching origin and confirming main/origin had zero commits of divergence. Scope: standalone HTML/CSS/JavaScript under `prototypes/dayrescue-ux/`, screenshots, and this document. Production Python, tests, dependencies and existing fixtures are unchanged.

## 1. Current UX and capability findings

Reviewed AGENTS.md, README.md, app.py, core/models.py, core/validator.py, core/agent.py, core/presentation.py, every module under ui/, and docs/M5A_QA_REPORT.md. The latest main includes M5B: conflict grouping and Fixed/Flexible labels in the example proposal table. The two historical M5A P2 findings are therefore not treated as current unfixed defects.

The remaining design problem is information order. The app starts with input modes, tables, deterministic checks and provider controls. An ordinary user first needs to see their activities, describe the interruption, then review specific changes. Expanded per-activity forms compete with the schedule; result metadata competes with the proposal. These are design judgments from the current implementation, not user-research findings.

| Product information | Existing contract/capability | Design treatment |
| --- | --- | --- |
| Planned activities | Activity title, start, duration, priority, fixed, explicit minimum duration | Readable timeline; Fixed/Flexible and priority on each activity |
| Unexpected commitment | BusyWindow label and same-day interval | Small interruption form and overlapping activity names |
| Shortening | Flexible activity with explicit min_duration_minutes only | Show permission and the actual change; never imply every flexible activity may shorten |
| Result | ProposedPlan plus Python ValidationResult | Kept, moved/adjusted and postponed; no optimality claim |
| Explanation/trace | AgentPresentation rationale, bounded trace, sanitized messages | Unverified rationale and optional advanced disclosure |
| Safety against stale results | Fingerprint binding and fresh validation in presentation | Withhold results after input changes; preserve this contract in any implementation |
| Date navigation / seven-day plan | No dates, timezone arithmetic, persistence or multi-day plan contract | Clearly labeled concept and disposable browser state only |
| Movable interruption | No soft BusyWindow flag | Unchecked unavoidable is labeled future-only; never silently map it to a hard busy interval |

Current UI accepts 3–8 pending activities and 0–10 busy windows; the domain model permits 1–8 activities. The prototype may show an empty day or one added draft to illustrate future entry states. That does not authorize relaxing the current UI minimum. Current inputs describe pending work in one day, not a calendar history or completed activities.

## 2. Proposed user journey

**A — My day.** See a selected date, activity names and local times. Every activity has its own Fixed/Flexible property and priority. “Add activity” opens a native dialog. “Something changed?” is the primary recovery action. A small guide explains fixed time and explicit shortening permission. Date arrows demonstrate only 2–8 November; Tuesday is the seeded rescue example.

**B — Add interruption.** Enter what came up, its start/end, and whether it is unavoidable. The adjacent preview names overlapping activities and distinguishes a flexible overlap from a fixed conflict. No overlaps detected is never presented as a feasibility proof. “Rescue my day” opens only the matching prewritten example; other inputs get an explanation and a restore path. A fixed conflict withholds any proposal. A late start would map to the existing current-time input in production; it is not modeled as a second event type here.

**C — Your rescued day.** Read a short outcome explanation, then Before/After. Two activities stay; project time moves; the run moves and shortens from 60 to its permitted 30 minutes; reading remains unscheduled. A postponed activity is not silently assigned to tomorrow. All activities remain identifiable as Fixed/Flexible. Read the rationale only with its Unverified label; advanced status and trace sit below the result.

**D — Weekly concept.** Scan seven days, select a day, inspect commitments, try a disposable draft and see Thursday’s sample fixed conflict. Tuesday links to B. Other days explain that rescue is unavailable. Weekly drafts intentionally do not update My day: no weekly source of truth or persistence is implemented. This separation is disclosed in the draft form.

The proposal does not replace the original day. There is no fake “saved,” “synced,” “accepted” or “moved to tomorrow” success. The familiar original remains available for review.

## 3. Design system and initial plan

Direction: a calm working planner with a visible day spine. A compact original sunrise mark and one gently curved green recovery note carry the identity. Most space goes to real activities. The selected date, plan and recovery action are left aligned; there is no dashboard of metrics, decorative gradient, stock photography or chat-first detour.

The initial plan compared a calendar grid with a chronological list. The list was chosen because five pending activities and hard/flexible properties matter more than empty half-hour cells. The weekly calendar structure is reserved for the future concept. Design review removed decorative hero content and additional status tiles; the result uses a single narrative outcome rather than large success numbers.

```text
Desktop                         Mobile
Navigation | My day + recovery   Brand / three navigation links
           | Date navigation    Demo notice / My day / recovery
           | Timeline | Note    Date navigation / Timeline
           |          | Guide   Recovery note / Guide

Interruption: form | overlaps    Form, then overlaps
Result:       Before | After    Before, then After, then details
Week:         seven columns     two columns + selected-day details
```

| Token | Value and role |
| --- | --- |
| Canvas / paper | `#f2f6f7` cool daylight / `#ffffff` activity surface |
| Ink / secondary text | `#243e48` / `#536b74` |
| Primary teal | `#205e60`, hover `#174b4d`; white button text |
| Recovery green | `#e8f3ee`; related green surfaces for kept/fixed context |
| Flexible lavender | `#eeedf8` with `#555078` text |
| Interruption amber | `#fff1d8` with `#81521a` text |
| Lines / errors | `#d5e0e3` structural rules; `#9b3434` error text |
| Type | Local Trebuchet MS for friendly headings; Segoe UI/Calibri for controls and body; system fallbacks; no downloads |
| Hierarchy | 32–45px page titles; 17–20px sections; 16px body baseline; 12–14px supporting text |
| Spacing | Primarily 4/8/12/16/24/32px steps; desktop main gutter 48px, mobile 20px |
| Shape | 9px buttons; 12px activity edges; 16px panels; 5px badges; 58px recovery-note corner |

Cards have a small colored left edge and explicit property labels. Changes use text, timestamps and color together. Priorities are textual, with optional small dots; they are not hard constraints or promised ranking. Before/After uses tabular time numerals. Text wraps rather than clipping long activity titles.

Controls use one teal primary action per task, white secondary controls and underlined tertiary actions. Native date/time input presentation follows the browser locale; timeline times use Intl formatting with a 24-hour display for comparison. The demonstration date is frozen deliberately, rather than pretending the user has actual commitments today.

Responsive rules: sidebar becomes top navigation at 900px; primary work areas stack at 650px; weekly overview reflows from seven to four to two columns; time fields stack at 360px. Nothing relies on dragging or hovering. Motion is limited to short color feedback; reduced-motion preferences disable transitions. The 650ms loading state opens a local sample and is labeled accordingly.

## 4. Prototype decisions and boundaries

Files: [prototype entry](../prototypes/dayrescue-ux/index.html), [CSS](../prototypes/dayrescue-ux/styles.css), [interactions](../prototypes/dayrescue-ux/prototype.js), [local opening instructions](../prototypes/dayrescue-ux/README.md). The SVG mark is original. There are no third-party images, remote fonts, packages or build step.

Screen hashes provide navigation; date and weekly selection query parameters support sharing the illustrative view. User-entered activity/event contents are never put into URLs. State exists only in memory. Reset asks before discarding edits; interruption drafts survive screen navigation; a before-unload guard warns about tab-only edits. Native dialog supplies modal keyboard behavior.

The prewritten result is shown only when the demo date, original activities, interruption label/times and unavoidable flag match the seed. Edits hide that result and its rationale. This is a **prototype match guard**, not a replacement for Python fingerprints or validation. No JavaScript scheduler or authoritative validator has been introduced. The overlap preview uses half-open interval comparisons only for feedback.

The CSP denies outbound connections, native form submission, objects and inline/external code. Scripts and styles are local. There is no provider client, API bridge, browser storage or service worker. Credentials are unnecessary and the repository’s `.env` was not opened or displayed.

Empty: adjacent demo day invites Add activity or Demo today. Loading: button becomes busy while opening the prewritten outcome; leaving the screen or editing an input cancels the timer. Errors: invalid interval focuses its input; fixed overlaps explain what must change; unsupported custom outcomes give a restore path. A stale result never leaves its old explanation visible.

Rationale and trace are also hand-authored. The advanced panel explicitly says Python did not run in this browser and labels every trace row illustrative. The user’s earlier report of a real invalid proposal followed by successful correction is separate manual evidence; this design exercise neither repeats that request nor establishes model reliability.

## 5. Realistic Streamlit implementation

These are feasibility judgments based on the existing st.columns, containers, widgets, expanders, session callbacks and presentation helpers in this repository. They are not production changes in this branch.

| Proposed treatment | Feasibility within current contracts |
| --- | --- |
| Calmer copy and content order | High: present plan → interruption → outcome, with explicit current/offline mode labels |
| Card-like activity summaries | High: render escaped activity text with existing fields; keep interactive controls as native Streamlit widgets |
| Fixed/Flexible and priority | Already available in the domain and live presentation; preserve consistency across all views |
| Before/After and change descriptions | Existing plan/validation dispositions provide the identities; compare original and proposed times/durations |
| Rationale and technical trace disclosures | Existing rationale/trace preparation can remain intact; move their presentation into optional sections while keeping unverified labels |
| Interruption entry | Existing UI conversion builds BusyWindow; do not introduce an unsupported optional-commitment flag |
| Add activity | Possible with session state and existing conversion; maintain the current 3–8 pending-activity limit and shortening controls |
| Mobile layout | Basic stacking and clearer grouping are feasible; exact CSS grid, sidebar and breakpoint fidelity is not promised |

Prefer native widgets and a small static theme over styling undocumented Streamlit internals. If rendering a visual card with HTML, escape all user/model text and keep behavior in widgets. Continue bounded plain-text rationale rendering. A visual polish pass must preserve input invalidation, the process-level live gate plus explicit click, fresh validation, sanitized failures, finite timeouts, zero SDK retries and at most one correction. Friendly copy must still distinguish invalid from infeasible.

## 6. What needs a different frontend or backend

React/Next.js is not required for a calm planner, and no migration is proposed before submission. A richer client would be worth evaluating later for precise responsive calendar geometry, direct manipulation, undoable editing, smooth cross-screen drafts and per-activity comparison interactions. Those are frontend reasons; choosing React alone would not supply persistence, dates, conflict semantics or reliable scheduling.

Backend/domain changes are needed for persisted weeks, dated activities, completed-work history, timezone/daylight-saving handling, recurrence, soft interruptions, explicit plan acceptance/versioning and any automatic carryover. Existing priority is an input preference, not a proven optimization objective. An optimality claim would require a separately defined objective and evidence beyond current validation.

Do not implement the prototype by bridging a static page directly to the provider. If a future client is commissioned, expose a controlled server boundary around the existing conversion/orchestration/presentation flow. Keep credentials server-side, immutable request snapshots, schema checks, result-to-input binding and backend-only validity decisions. This is future analysis, not approval to build a service.

## 7. Safe pre-submission scope

After design review, consider only the highest-value presentation changes: clearer activity property labels, approachable task copy, compact conflict summaries, a before/after view and optional technical disclosures. M5B has already addressed property labels and conflict grouping. Do not spend remaining hackathon time recreating the prototype shell pixel for pixel.

Keep the current single-day input contract and gate. Avoid adding date navigation, weekly controls, acceptance/persistence, a soft-interruption toggle or new scheduling behavior to the live MVP. The weekly view belongs in a clearly labeled design artifact or future-roadmap segment, not the functional demo.

The recommendation is **ready for design review**. The current branch stops here; it does not implement any Streamlit redesign or authorize a merge/deployment.

## 8. Future weekly architecture recommendations

If separately funded and authorized, establish a dated plan model before designing a seven-day solver. Store activity identity, planned local date, timezone, intended duration, fixed flag, priority and explicit shortening minimum; keep actual/completed status separate from pending work. A single activity property controls Fixed/Flexible regardless of which day is selected.

Treat the week as a presentation over independently versioned days first. Build an explicit adapter from a selected day’s remaining activities and busy intervals into DayContext. Resolve dates/timezones at that boundary because the current core uses integer minutes and half-open intervals only. Test midnight/daylight-saving boundaries before supporting them; do not silently split an overnight commitment into the current contract.

Separate original plans, interruption records, proposals and accepted revisions. Bind each proposal to the exact input version and require revalidation before acceptance. Postponed means unscheduled until the user chooses a date; cross-day movement needs explicit consent and validation of both affected days. A storage technology, account system, calendar integration and recurrence engine are deferred decisions, not M5C deliverables.

## 9. Accessibility, visual QA and remaining limitations

Applied `frontend-design` and reviewed the prototype against the freshly retrieved [Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md). Sentence-case copy follows the required design skill and brief where the external checklist prefers title case.

Implemented semantic landmarks, one visible h1, ordered activities, real navigation links, labeled form controls, keyboard-operable native buttons/selects/disclosures, a skip link, visible focus, route-heading focus, status announcements, textual change labels, safe-area spacing, long-title wrapping and reduced-motion rules. Modal form focus returns to its trigger. Palette calculations for normal text: body/canvas 10.39:1; secondary/canvas 5.18:1; white/teal 7.42:1; fixed badge 6.25:1; flexible badge 6.45:1; amber warning 5.97:1. These six pairs exceed 4.5:1; this is not a claim of full WCAG certification.

Browser visual evidence uses the Codex in-app browser on the local static server. Desktop captures use 1440×1000; mobile captures use 390×844. Screenshots are viewport captures, not full-page exports. The browser’s native time inputs displayed the host’s Vietnamese AM/PM labels; the surrounding timeline retained the intended 24-hour times.

| Check | Observed result |
| --- | --- |
| Desktop A/B/C/D | Visually inspected navigation, activity cards, form, comparison and weekly concept |
| Mobile A/B/C/D | Visually inspected stacked layouts and wrapped weekly overview at 390px |
| Narrow phone | All four screens: scroll width 305px matches client width 305px at 320px viewport after correction; the initial form exposed a narrow native-time layout issue and time fields now stack at ≤360px |
| Empty day | Next-day navigation showed the empty invitation; Demo today restored the seeded date |
| Add activity / long title | Added a long activity name in the mobile dialog; 6 timeline items, no page-width overflow; focus returned to Add activity |
| Stale result | After adding an activity, Rescued day showed “Your inputs have changed” and withheld the comparison/rationale; restore returned the sample |
| Invalid interval | End before start showed inline error and focused event-end |
| Fixed overlap | 10:30–11:00 named Team check-in, explained the fixed conflict and withheld a proposal |
| Unavoidable toggle | Unchecked state disclosed movable interruptions as future-only |
| Loading | Explicit sample button showed busy state, then navigated to the hand-authored result |
| Rationale disclosure | Expanded with hand-authored and unverified labels visible |
| Advanced disclosure | Expanded with “Python validation: not run in this browser” and explicitly illustrative trace rows |
| Keyboard / weekly draft | Escape closed the activity dialog and returned focus to Add activity; weekly draft appeared with “Draft preview only” |
| Weekly conflict | Thursday selection showed both fixed commitments and the 09:30–10:00 overlap; non-Tuesday rescue explained the concept boundary |
| Offline regression | `.venv/Scripts/python.exe -m pytest -q`: **235 passed in 23.17s**, including existing AppTest; live gate set to 0 and existing fixture blocks real HTTP/external sockets |
| Example consistency | Separate deterministic Python check of the hand-authored UX data: valid=true, no issues; kept study/meeting, adjusted project/run, postponed read. No model ran |
| Static review | JavaScript syntax check passed; unique HTML IDs, control labels/names and local asset paths checked; no external resources |
| Browser console | No captured error or warning entries in the final inspected tab |
| Scope / privacy | Protected application/test/dependency paths have no diff; `.env` is untracked and ignored (metadata checks only); GitHub repository visibility verified PRIVATE |

Visual QA found an initially unpopulated comparison list; it was fixed and re-inspected with five Before entries and five After entries (including the interruption). Subsequent review added sample-date binding, canceled loading on edits/navigation and cleared reset feedback. No production defect or backend fix is claimed by these prototype corrections.

Evidence is under [screenshots](../prototypes/dayrescue-ux/screenshots/): `desktop-my-day.jpg`, `desktop-interruption.jpg`, `desktop-rescued.jpg`, `desktop-week-concept.jpg`, and their `mobile-` counterparts. Additional lower-page captures may supplement the result/weekly details.

The browser tool blocks `file:` navigation, so direct-file opening was not visually verified; the loopback static-server path was verified. One batched responsive-inspection call timed out; subsequent bounded calls recovered the tab and supplied the narrow-phone evidence above. These tool limits do not establish a prototype failure or a production scheduling result.

Guideline review findings, after corrections:

```text
prototypes/dayrescue-ux/index.html — labeled controls, landmarks and semantic navigation: pass
prototypes/dayrescue-ux/styles.css — focus, reduced motion and narrow-layout overflow: pass for checked viewports
prototypes/dayrescue-ux/prototype.js — text escaping, input-bound sample and error recovery: pass for exercised flows
```

Remaining limits: no assistive-technology certification, physical-device test, Safari/Firefox matrix or user study. Small badge/helper text needs review with users; the mobile Before/After stacks sequentially, so comparison requires scrolling. Mobile interruption feedback sits below the form. The weekly concept is a wrapped overview rather than a spatially faithful calendar. The illustrative revised day leaves unused time and postpones reading; it demonstrates possible tradeoffs, not a necessity to postpone or a best plan. Prototype additions have no generated result. Provider failures are documented for production feasibility but cannot genuinely occur without a provider in this artifact.

Review questions: Is the daily timeline the right primary view? Is sequential mobile comparison acceptable for the hackathon? Which presentation-only changes, if any, justify the remaining budget? Weekly planning requires a separately approved scope.

No live requests, billing changes, dependency installation, deployment, visibility changes or automatic merge were performed. Stop for design review.
