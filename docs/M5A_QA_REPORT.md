# M5A — Final Release QA Audit

## 1. Environment and commit

- Audit date: 2026-11-02, Asia/Saigon.
- Repository: `trungthanh1909/dayrescue`; GitHub metadata confirmed **private** during this audit. Visibility was not changed.
- Audited application commit: `d24cd7d0883dc2982df5588d0d408f15ea081906` (M4C, PR #7).
- The initial working tree was clean on `feat/m4c-live-streamlit`. Fetched origin, switched to main, fast-forwarded main from `c7f3b45` to `d24cd7d`, then created `feat/m5a-release-qa`. No merge commit or force operation was used.
- This QA branch changes documentation only. The application and tests remain identical to the audited main commit. Identify the report commit with `git log -1 --format=%H feat/m5a-release-qa`; the final handoff records its SHA.
- Windows (`win32`), Python 3.13.1, repository-local `.venv/Scripts/python.exe`.
- Streamlit 1.66.1; Pydantic 2.14.1; OpenAI SDK 2.54.0; python-dotenv 1.2.4; pytest 9.2.0.
- Git 2.45.1.windows.1; GitHub CLI 2.96.0; Codex CLI 0.166.0-alpha.5.1.
- Git commands required a per-command `safe.directory` setting because the sandbox account differs from the workspace owner. Git metadata writes used the approved elevated execution path; no global Git configuration was changed.

Read AGENTS.md, README.md, app.py, all core/UI modules, all test modules and conftest.py, the local verification/live diagnostic scripts, requirements.txt and .gitignore. No credential contents were read, displayed or modified.

## 2. Test results

All commands used the local virtual environment. Live generation was disabled in the verification process. Tests enabling the click path used test providers or the real SDK with in-memory MockTransport only. The suite blocks real HTTP transport and external socket connections; loopback socket connections support Windows asyncio/AppTest.

| Check | Result |
| --- | --- |
| Baseline `python -m pytest -q` | **232 passed in 21.20s**, no failures or skips reported |
| Focused `python -m pytest tests/test_app.py tests/test_live_streamlit.py tests/test_presentation.py tests/test_integration.py -q` | **84 passed in 19.42s**, including production entry-point AppTest and rendering harnesses; these are a subset of the 232 tests |
| `python scripts/doctor.py` | **DOCTOR PASS**, local virtual environment and required dependencies available |
| `python -m pip check` | **No broken requirements found.** |
| `python scripts/demo_offline.py` | A VALID; B VALID; C INVALID, with FIXED_BUSY_CONFLICT and BUSY_OVERLAP |
| Streamlit startup | **PASS**; `http://127.0.0.1:52495/_stcore/health` returned HTTP 200 and `ok`; `/` returned HTTP 200 and the Streamlit HTML shell |
| Additional offline AppTest reproduction checks | **PASS**; confirmed the two UI findings below, with no app exceptions or live requests |
| Final full regression after documentation updates | **232 passed in 17.62s**, no failures or skips reported; doctor, pip check and offline demo also passed again |

Startup ran in a hidden child process bound to loopback, with `DAYRESCUE_ENABLE_LIVE_AI=0`, MODEL_API_KEY removed from the child environment, usage telemetry disabled, external socket connect/connect_ex blocked and provider HTTP transports blocked. The verification process was stopped afterward. Health/HTML checks establish server startup; AppTest separately exercises application execution and interaction. They do not constitute a real-browser visual review.

The offline demo uses **hand-authored fixtures and deterministic Python validation**, not Muse output. Automated MockTransport checks establish the encoded application behavior, not real-world model reliability.

### Critical audit coverage

| Area | Finding and evidence |
| --- | --- |
| Startup, rerender and opt-in | `live_ai_enabled()` requires the exact process value `1`; .env is not loaded to discover the gate. Example mode always disables generation. Production startup, edits and rerenders are covered with no provider construction/calls. The UI invokes generation only inside the button-click branch; the invocation boundary checks the gate again. |
| Request bounds | `run_agent()` iterates over attempts 1 and 2 only. Hard-conflict preflight makes zero requests. Schema-valid deterministic rejection alone permits correction; malformed output/provider failures terminate. MockTransport verifies actual request counts, including 429/500 failures and correction. |
| SDK configuration and cleanup | The UI path pins muse-spark-1.3, low reasoning and 2048 completion tokens. OpenAI uses max_retries=0 and finite 5-second connect/30-second read, write and pool timeouts. Provider clients close in finally; setup and cleanup failures become safe terminal errors. These are phase timeouts, not a promised total wall-clock deadline. |
| Secrets and untrusted output | No key/header/raw provider exception is rendered by the production result path. Canary tests cover HTTP failures, timeouts, setup, cleanup and malformed output. Explanations use bounded st.text only after fresh validation; there is no execution of model text. `git ls-files .env` returned no paths; `git check-ignore .env` confirmed it is ignored. |
| Scheduling | Existing validator tests cover fixed start/duration/postponement, explicit shortening minimums and forbidden lengthening, busy/activity overlaps, elapsed time, horizon limits, touching boundaries, and unknown/missing/duplicate/double-disposition IDs. Agent and presentation revalidate proposal schemas, including mutable/tampered model instances. No false VALID was reproduced. |
| Invalid vs infeasible | Immutable preflight conflicts produce infeasible with zero calls. Two rejected proposals produce invalid and explicitly do not prove impossibility. Presentation recomputes fixed conflicts and revalidates a successful plan against current inputs before VALID or rationale display. |
| Session state | Fingerprints bind the full context and mode/scenario. Widget changes and invalid input clear results; returning to prior inputs does not restore a success. Tests cover changed bindings during invocation, mode changes, repeated clicks replacing prior success with failure, tampered results and rerenders without duplicate requests. |
| Failure handling | Existing tests cover invalid schema/JSON, empty content/choices, truncated content, unsupported envelopes, timeouts, connection failures and HTTP 400/401/403/408/429/500, invalid then valid correction, and two invalid proposals. Adapter parse errors currently map to the safe generic provider_error status; they do not retry or show a plan. |
| Demo claims | Example fixtures are explicitly labeled offline and hand-authored. Current/proposed times use HH:MM; the original and live revised tables identify Fixed/Flexible. No-conflict feedback disclaims a complete feasibility or optimality proof. Live success describes this proposal's hard-constraint validity only. Minor example-table and feedback-density issues remain below. |

Representative regression evidence is in tests/test_validator.py, test_agent.py, test_meta_client.py, test_ui_input.py, test_app.py, test_presentation.py, test_integration.py, test_live_streamlit.py and test_live_structured_probe.py. In particular: `test_no_false_valid`, `test_correction_uses_exact_feedback_and_stops_at_two`, `test_transport_failures_are_safe_terminal_errors`, `test_real_click_result_invalidated_and_never_restored`, `test_active_binding_changes_during_invocation_rejects_result` and `test_repeated_click_error_replaces_previous_success` passed.

## 3. Bugs found by severity

| Severity | Count | Disposition |
| --- | --- | --- |
| P0 | 0 reproduced | No security breach, unbounded requests, false VALID or broken core functionality found |
| P1 | 0 reproduced | No primary-journey failure or major incorrect behavior found |
| P2 | 3 | Two UI findings reported without code changes; one stale-status documentation finding corrected |

This is an audit of the stated scope and observed cases, not proof that no defects exist.

## 4. Reproduction evidence

### QA-01 — P2: crowded conflicts produce excessive repeated feedback

- **Reproduction:** with live generation disabled, select Custom day; choose 8 activities; make all fixed at 09:00 for 60 minutes; create 10 busy windows, each 09:00–10:00. Keep current time at 08:00.
- **Expected:** accurate conflict feedback that remains easy to scan, with repeated codes summarized while retaining affected activities.
- **Actual:** the hard-conflict section renders **108 separate issue rows**: 80 FIXED_BUSY_CONFLICT rows and 28 FIXED_FIXED_CONFLICT rows, plus activity captions. AppTest reproduced these exact counts with zero app exceptions. Validation itself is correct.
- **Root cause:** the validator correctly returns each conflict; `show_preflight()` renders every issue individually without grouping or a disclosure limit. The infeasible-result renderer can also repeat conflicts already shown by preflight.
- **Affected files:** app.py (`show_preflight`), ui/agent_result.py (`render_agent_result`), core/presentation.py (infeasible issue presentation). The validator needs no change.
- **Recommended minimal fix:** group repeated codes with affected activity names and place full details in a collapsed section. Deferred under the P2/no-redesign restriction.

### QA-02 — P2: offline proposed table omits Fixed/Flexible identity

- **Reproduction:** launch Example scenarios, select B · Unexpected Event, compare the original and hand-authored proposed tables.
- **Expected:** both tables identify which activities are fixed or flexible without requiring a title or cross-reference.
- **Actual:** AppTest confirms the original table includes `Status`, while the proposed table has only `Activity`, `Start`, `End`. The fixed call's title happens to indicate its type; the table has no explicit type field. The live Custom day result table already includes `Status`.
- **Root cause:** the example-mode proposed-table row dictionary omits the existing activity.fixed field.
- **Affected files:** app.py (example-mode proposed-plan table).
- **Recommended minimal fix:** add the same Fixed/Flexible Status column used by the original/live tables. Deferred as P2; no broader layout changes recommended.

### QA-03 — P2: status documentation predates merged M4C and manual correction

- **Reproduction:** at audited main commit d24cd7d, read AGENTS.md current reality/workflow and README verified status, activation/Git commands, remaining manual verification and demo outline.
- **Expected:** M4C is recorded as merged, current work targets M5A, and the user's reported successful live correction is distinguished from offline evidence.
- **Actual:** documentation says M4C awaits review, directs work to its old branch and repeatedly says live correction is untested.
- **Root cause:** status text was written before the M4C merge and the later user-reported manual result.
- **Affected files:** AGENTS.md and README.md.
- **Recommended minimal fix:** update only status, branch/workflow directions and evidence boundaries. **Fixed in this QA branch.** No new live success, token count, latency or broad reliability claim was inferred.

## 5. Fixes and regression tests

No reproducible P0/P1 issue required a production fix. Domain models, validator, agent, provider, UI, hand-authored scenarios, dependencies and tests are unchanged. No regression tests were added because there was no P0/P1 fix; the existing suite already exercises the critical contracts above. The extra AppTest checks reproduced P2 issues without changing production behavior.

Documentation changes correct QA-03, preserve the disabled-by-default gate and no-live-call restriction, and add this report. No dependencies were added. Final verification is recorded in section 2.

## 6. Unresolved issues and limits

- QA-01 and QA-02 remain open as nonblocking P2 issues; use a small, readable scenario for the final demo.
- No real browser visual/layout review or video rehearsal was performed by Codex. AppTest is evidence of widget/rendering behavior, not pixel-level layout or physical user interaction.
- User-reported manual evidence: real connectivity PASS (DAYRESCUE_READY, 382 total tokens); one structured probe PASS; Streamlit generation reached VALID after one invalid proposal and one successful correction. Codex did not repeat or independently observe these live calls during M5A.
- Arbitrary real-world model reliability, proposal usefulness/priority tradeoffs, latency across scenarios and sufficiency of the 2048-token budget are not established by offline tests or the reported manual successes. A plan postponing all flexible work may satisfy hard constraints while being unhelpful; no optimality claim is made.
- No billing, credentials, deployment, visibility changes, new feature work or automatic merge are part of this audit.

## 7. Manual testing checklist

Recorded history:

- [x] User reports real connectivity smoke PASS.
- [x] User reports structured-output probe PASS.
- [x] User reports manual Streamlit invalid-first-proposal → successful correction → VALID.

For final review/rehearsal; these boxes remain unchecked because no manual browser session was performed during M5A:

- [ ] Launch main/the reviewed QA revision with DAYRESCUE_ENABLE_LIVE_AI removed or set to 0. Confirm the generation button is disabled in both modes.
- [ ] In a normal browser, review A/B/C before/after schedules and fixture labels. Confirm HH:MM times and fixed activity identity are understandable at recording size.
- [ ] Enter a three-activity custom day, add a busy window and a fixed conflict, and review input errors, shortening controls and conflict feedback. Keep live generation disabled.
- [ ] Confirm scrolling, table widths and error text remain usable in the demo window. Review/accept QA-01 and QA-02 for the MVP.
- [ ] Rehearse the three-minute story using existing offline fixtures and accurately label the separately reported manual live evidence.
- [ ] Technical reviewer checks this report, the documentation-only diff and final regression results before authorizing a merge. Keep the repository private until separately authorized.

No additional Meta request is needed or authorized for this checklist. If the user separately elects another live test, only their Windows ADMIN session should enable generation; stop on provider failure and review the safe error rather than repeatedly clicking.

## 8. Release recommendation

**GO for the bounded hackathon MVP release candidate, for technical review.** No reproducible P0/P1 blocker was found, and the offline regression/startup checks passed. QA-01 and QA-02 are minor, known usability limitations; they do not alter Python validity or request bounds.

Complete the manual visual/rehearsal checklist before recording/submission. This recommendation does not establish real-world model reliability and does not authorize a merge, deployment, repository publication or further live requests. Stop for technical review after committing and pushing feat/m5a-release-qa.
