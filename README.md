# DayRescue

**When Life Interrupts, Your Plan Adapts.**

Meta Global AI Developer Hackathon 2026 — Indie Developer / Build for Your World.

DayRescue aims to let Muse Spark propose schedule tradeoffs and then run a deterministic Python validator. The validator alone decides whether a proposed plan satisfies declared hard constraints; it does **not** prove the plan optimal.

## Verified status / limitations

- **M0:** verified on Windows with Python 3.13.1, Git 2.45.1 and GitHub CLI 2.96.0; local `.venv`, dependency installation, doctor and Streamlit startup passed. Private repository: [trungthanh1909/dayrescue](https://github.com/trungthanh1909/dayrescue), initial commit `06cb2c6`.
- **M1:** typed domain models, deterministic validator and A/B/C sample fixtures verified: all 30 original unit tests pass. These are deterministic Python tests using **no Meta API**.
- **M2A:** provider-independent offline orchestration implemented and merged via PR #2 (`9315b97`). It performs preflight, validates an injected provider's structured proposal and allows one correction.
- **M2B:** Meta provider adapter implemented and merged via PR #3 (`9a42a47`). Adapter serialization/parsing is verified offline through the real OpenAI SDK and in-memory HTTP transport; see the separate M4B live result below.
- **Connectivity smoke: PASS**, as reported by the user for the local Windows ADMIN session: `muse-spark-1.3` returned `DAYRESCUE_READY`, using **382 total tokens**. This supersedes the earlier billing-blocked status. Codex did not repeat the request. Connectivity does not establish structured-output compatibility or scheduling success.
- **M3A:** Streamlit example and custom-day input workflow implemented. Custom input converts to existing Pydantic contracts and runs the narrow hard-conflict check. Example mode retains the two-column hand-authored proposal comparison.
- **M3B:** AgentResult presentation and session invalidation merged via PR #4 (`0bae0ae`) and tested offline. All five terminal statuses are supported; successful plans are revalidated against current inputs before display.
- **M4A:** completed and merged via PR #5 (`c8390d4`), with 171 offline tests at that milestone: UI conversion → DayContext → agent → real SDK with MockTransport → Python validator → presentation/session binding and AppTest rendering. This establishes offline readiness only, not real Meta scheduling compatibility.
- **M4B:** merged via PR #6 (`c7f3b45`). The user reports the real Muse Spark 1.3 structured-output probe PASS: Python VALID, fixed call preserved, study rescheduled, unexpected busy window respected, zero activities postponed. This is one scenario, not proof of optimality or general reliability.
- **M4C:** merged via PR #7 (`d24cd7d`). Custom day generation is wired behind an exact process opt-in and explicit button click. Offline verification: 232 tests passed (including AppTest), doctor PASS, pip check PASS, localhost Streamlit health/page HTTP 200 with live generation disabled. Default remains disabled. The user reports manual Streamlit live generation reached VALID after one invalid proposal and one successful correction. Codex did not repeat those requests; this single reported journey does not establish general model reliability.
- **M5A:** final release QA findings, verification and manual checklist are recorded in [docs/M5A_QA_REPORT.md](docs/M5A_QA_REPORT.md). No real Meta API requests are part of this audit.

**No fixture, text or validator result may be presented as live Muse output.**

## Windows local setup (PowerShell)

```powershell
py -3 --version
git --version
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\doctor.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\demo_offline.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Python 3.11+ required. Don't use `py -3` if it points to Python 3.10 or below; use the corresponding launcher version (`py -3.11`, for example). If PowerShell blocks `Activate.ps1`, the commands above work without activation.

Streamlit 1.66.1 is the minimum tested version for the supported `width="stretch"` dataframe API. Run all offline tests with `python -m pytest -q`; AppTest covers custom input, invalid input recovery, fixed/busy conflicts, shortening controls and all three examples. UI tests block HTTP requests through requests/httpx.

## Interactive offline preview

Select **Example scenarios** to inspect the original A/B/C fixtures and their hand-authored proposals. Python `validate_plan()` alone produces VALID/INVALID feedback.

Select **Custom day** to enter 3–8 pending activities. Each row has a name, local start time, duration in minutes, priority and fixed/flexible status. Flexible activities can explicitly allow shortening with a minimum duration. IDs are generated from row positions so duplicate names remain distinct activities. Configure current time, day start/end and 0–10 unexpected busy windows. Changes update the preview immediately; malformed inputs show Pydantic errors instead of stale validation results.

Custom mode displays the original activities and runs `detect_hard_conflicts()`. Fixed activity conflicts with elapsed time, the day horizon, busy windows or other fixed activities are shown with codes and activity names. Absence of detected conflicts does **not** prove full feasibility or optimality. Flexible activities are replanned only after an explicitly enabled live generation click.

The **Generate with Muse Spark** button is disabled by default and always disabled in Example scenarios. Ordinary imports, startup, input edits and rerenders send no API requests. Times use whole local minutes within a single day; the UI accepts 00:00–23:59 and does not offer 24:00 or overnight windows. Inputs/results are session-local and are not saved to disk. Live generation sends the captured day's context to Meta only after the user clicks.

## Enable Custom day generation locally (M4C)

For manual use, use your Windows ADMIN PowerShell session with the existing ignored `.env` containing `MODEL_API_KEY`. Do not copy or expose credentials to Codex, and do not overwrite `.env`.

```powershell
Set-Location C:\Users\ADMIN\IdeaProjects\dayrescue
git switch main
$env:DAYRESCUE_ENABLE_LIVE_AI = "1"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Select **Custom day**, enter 3–8 activities and any busy windows, then click **Generate with Muse Spark** once. Only the exact process environment value `DAYRESCUE_ENABLE_LIVE_AI=1` enables the button; `.env` is not loaded to discover this gate. Enabling alone sends no request.

`ui/live_generation.py` captures a DayContext snapshot and clears the previous result on a click. `core/live_generation.py` checks the gate again and passes the snapshot to `run_agent()`. Its lazy provider setup loads `.env` only when preflight permits the first proposal, with no environment override or interpolation. The model is pinned to `muse-spark-1.3`, reasoning `low`, existing JSON schema and 2048 completion tokens, default temperature, zero SDK retries, and 5-second connect/30-second read/write/pool timeouts. Fixed conflicts require zero provider requests and no credentials. Otherwise, a click permits one proposal and **one correction only if Python rejects the first proposal's hard constraints**. API errors, timeouts, truncation and malformed output terminate without correction/retry. Clients close in `finally`; setup/cleanup errors are sanitized too.

Widget-change callbacks immediately invalidate the input fingerprint/result. A late result is rejected if its captured fingerprint is no longer active, and every rendered valid result is schema-checked and Python-revalidated against current inputs. Success shows the revised schedule, kept/moved/postponed activities and bounded trace. A separate **AI-generated rationale (not independently verified)** section uses plain text, capped at 1000 characters, only after validation; it is never executed or interpreted as instructions. The validator verifies hard constraints, not whether tradeoffs are useful or optimal.

Do not repeatedly click after a provider failure; inspect the safe UI status and review access/configuration locally before authorizing another attempt. The user reports one successful manual live correction through this UI. Automated correction tests use offline MockTransport and do not establish real-world model reliability.

To disable again, stop Streamlit with Ctrl+C, then restart without the flag:

```powershell
Remove-Item Env:DAYRESCUE_ENABLE_LIVE_AI -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Agent result presentation

The **Agent result** section shows a result only after an enabled Custom day click. It never generates a demonstration AI result. Deterministic AgentResult fixtures exist only in tests, not in the application. Existing A/B/C proposals remain separately labeled hand-authored offline fixtures.

Data preparation is isolated in `core/presentation.py`; Streamlit rendering and session binding are in `ui/agent_result.py`. Neither invokes the agent, imports the Meta adapter, loads credentials nor sends requests. The separate `ui/live_generation.py` click handler delegates invocation to `core/live_generation.py`.

For a `valid` terminal status, the presentation layer requires a plan and a successful stored validation, rechecks its schema and reruns `validate_plan()` for the current context. Only then does it show VALID, the proposed schedule and freshly derived kept/moved/postponed activity summaries. For `infeasible`, it recomputes fixed-constraint conflicts. For `invalid`, it explains that no valid proposal was found within two attempts, without claiming the day is impossible. `provider_error` and `malformed_proposal` show fixed safe errors and suppress any stale plan, success or summaries.

The collapsed execution trace displays at most three events (preflight plus two attempts) and ten known codes per event. Unknown metadata/codes are replaced with safe placeholders; raw exception bodies and model explanations never appear in the trace. The code allowlist is for presentation sanitization, not a second set of scheduling rules. Valid proposals alone can show their separately labeled plain-text rationale.

Session results are stored with a SHA-256 fingerprint of the mode/scenario and complete canonical DayContext. Changes to meaningful inputs, invalid input or switching modes/scenarios clear the saved result. Returning to old inputs does not restore an old result. `store_agent_result()` rejects results for an input that is no longer current; `current_agent_result()` checks the binding again on every rerender. There is no persistence or background generation.

## Domain contracts

All times are local integer minutes since midnight, e.g. 09:30 = 570, using half-open intervals `[start, end)`. The intended UI accepts 3–8 *pending* activities; the backend schema permits 1–8 for minimal validator tests. Activities already completed are not modeled. An original activity has `start_minute`, `duration_minutes`, priority (`high`, `medium`, `low`) and optional `fixed` and `min_duration_minutes` (explicit shortening permission). Day context has `now_minute`, day horizon and 0–10 busy intervals. A proposal lists items scheduled with times/durations and IDs postponed. Each original ID must be scheduled exactly once or postponed exactly once. Fixed activities must retain original start and duration and cannot be postponed.

`core.validator.validate_plan()` checks duplicates, unknown/missing IDs, fixed immutability, duration/shortening permission, elapsed time, day horizon, busy overlaps, and schedule collisions. `detect_hard_conflicts()` catches provably impossible fixed constraints: fixed activity elapsed, out of bounds, clashes with busy time or other fixed activity. This is **not** a general optimizer or a complete feasibility proof.

`python scripts/demo_offline.py` and the Streamlit offline preview show three **hand-authored, offline** fixtures:

- Scenario A (late start) — a flexible activity is postponed, a fixed appointment stays.
- Scenario B (unexpected visitor) — study shifts around a new busy interval, a fixed call stays.
- Scenario C (impossible) — an unavoidable busy interval conflicts with an immutable meeting; validator rejects the plan.

These deterministic fixtures establish the Python contracts only. The separate real M4B probe and any enabled Custom day proposals must pass the same Python validation.

## Offline agent orchestration (M2A)

`core.agent.run_agent(context, provider)` accepts an existing `DayContext` and a typed callable provider. Each `ProposalRequest` contains a copied context, attempt number (1 or 2), and, for correction, the previous proposal and structured `ValidationIssue` feedback. Providers return `ProposedPlan` or a structured dictionary and must not retry internally. There is no default provider or fallback plan; deterministic stubs exist only in unit tests.

Preflight runs before any provider invocation. Immutable conflicts return `infeasible` with zero calls. Otherwise, every proposal is schema-checked and passed to `validate_plan()`. A valid result stops immediately; an invalid first proposal permits one correction. Exceptions or malformed data terminate immediately without retry. Mutable Pydantic proposal objects are revalidated and detached, and providers receive separate copies of context and feedback.

Terminal statuses:

- `valid`: Python accepted the returned `plan`; `validation.valid` is true.
- `infeasible`: deterministic preflight found fixed-constraint conflicts; `issues` contains them.
- `invalid`: both proposals failed validation; `issues` contains the final real validation issues. This status does not prove infeasibility.
- `provider_error`: a provider invocation raised an exception.
- `malformed_proposal`: provider data failed the proposal schema.

All failure statuses return `plan=None`. `validation` holds the last completed Python validation, if any, including when a later provider call fails; `issues` exposes those issues or preflight conflicts. `attempts` counts actual provider invocations, including failed ones, and never exceeds two. The trace starts with preflight at attempt 0, followed by one event per provider call: validation outcome and issue codes, or `PROVIDER_ERROR`/`MALFORMED_PROPOSAL`. It excludes raw exception text and schedule content. The agent does not log, execute model text, load credentials or make HTTP requests itself.

Run `.\.venv\Scripts\python.exe -m pytest -q` for the complete offline suite, including Streamlit AppTest. `tests/conftest.py` disables live generation by default for tests and blocks real HTTP/external socket connections; individual click tests opt in with MockTransport/test doubles only. Windows asyncio's internal localhost socketpair remains permitted. Offline test results are never real model output.

## Meta provider adapter (M2B, offline verification only)

`core.meta_client.MetaProvider` implements the callable provider interface. Construction reads explicit configuration or the process variables `MODEL_API_KEY` and `META_MODEL`; it does not read `.env` automatically. Callers must load the local `.env` explicitly without printing it. Importing/constructing the adapter makes no API request; invoking it sends a request and requires explicit authorization. Call `close()` when finished to release the SDK client.

The adapter uses the existing base URL `https://api.meta.ai/v1` and default model `muse-spark-1.3`, with configurable model ID. It sends a developer instruction containing hard constraints and one JSON user message containing the context and attempt number. Correction requests also contain the previous proposal and the exact structured validation issues. Requests use `response_format.json_schema` derived from `ProposedPlan`, `strict: false`, non-streaming output, and `max_completion_tokens=2048`. Input JSON and response content are each limited to 32,768 characters. SDK retries are disabled with `max_retries=0`; HTTP timeouts are 5 seconds for connection and 30 seconds for read/write/pool phases (not a total wall-clock deadline).

Optional `reasoning_effort` configures the documented Meta effort levels; when omitted, existing callers keep the model default and the parameter is absent from the request. The M4B probe explicitly uses `low`. Temperature remains unset, preserving Meta's documented default of `1.0`. No token budget or retry policy changes accompany this option.

Empty responses, malformed envelopes/JSON/proposals, truncation (`finish_reason=length`), unexpected finish reasons, refusals, tool calls, missing credentials, SDK failures and timeouts raise `MetaProviderError` with a fixed code. Raw model output and SDK exception bodies are excluded from its public message/traceback. No repair request or fallback is attempted. A model-provided `valid` field is rejected by the existing schema. Parsing alone is not semantic validation: `run_agent()` still passes each returned proposal to the unchanged Python validator. Adapter exceptions become the agent's existing `provider_error` status with generic `PROVIDER_ERROR` trace; the adapter's more specific code is available when handling `MetaProviderError` directly.

**API evidence and remaining assumptions (reviewed 2026-10-30):** Meta's [Chat Completions guide](https://dev.meta.ai/docs/protocols/chat-completions) documents the model, developer role, `max_completion_tokens`, top-level `reasoning_effort` and default temperature; its [structured output guide](https://dev.meta.ai/docs/structured-output) documents `json_schema` and non-strict schema normalization. The [reasoning guide](https://dev.meta.ai/docs/reasoning) confirms `low` support and that reasoning consumes the output budget. The installed SDK's timeout/retry behavior is verified by transport tests. The user verified these settings for one real M4B scenario and reports a successful manual Streamlit correction journey. Arbitrary custom-day quality, budget sufficiency across scenarios and representative latency remain unverified. No mocked result is evidence of live Muse output.

## Offline end-to-end readiness (M4A)

Run `.\.venv\Scripts\python.exe -m pytest tests/test_integration.py -q` for focused integration coverage, or `.\.venv\Scripts\python.exe -m pytest -q` for the full unit/integration/AppTest suite. The integration tests convert the existing A/B/C scenario inputs through `build_day_context()`, inject a real `MetaProvider` configured with `httpx.MockTransport`, and render the resulting AgentResult through the production presentation helpers in an AppTest-only harness.

Coverage includes validated Late Start and Unexpected Event plans, immutable conflicts with zero provider requests, invalid→valid correction with exact feedback, two invalid proposals, timeout/HTTP failures, malformed proposal JSON and stale input/result invalidation. Request counts are checked at the HTTP transport boundary: at most two per agent run, zero SDK retries and finite timeouts. Tests also check that credentials/raw errors are absent from traces and that ordinary production UI rerenders never invoke MetaProvider. Real HTTP transport is blocked; localhost socketpairs are allowed solely for Windows asyncio.

All encoded completion envelopes and failure responses are test code. The production UI never runs mock generation; live generation requires the M4C gate and explicit click. B/C integration inputs retain the existing domain fixtures' minimal activity counts; custom UI's 3–8 count is covered separately by AppTest. Malformed JSON from the Meta adapter raises a sanitized adapter error and therefore reaches presentation as the existing `provider_error` status, without attempting a correction.

## Structured-output probe (M4B, manual execution only)

The user has already verified the single M4B request as Python VALID. No repeat probe is required for M4C. The commands below document the standalone probe for future separately authorized diagnosis. Codex never runs it live. Credentials stay in the user's ignored local `.env`.

From the repository root, this command sends **zero requests** and does not load `.env`:

```powershell
.\.venv\Scripts\python.exe scripts\live_structured_probe.py
```

For a separately authorized single diagnostic request, the user can run:

```powershell
Set-Location C:\Users\ADMIN\IdeaProjects\dayrescue
.\.venv\Scripts\python.exe scripts\live_structured_probe.py --live
```

The exact `--live` flag is required. It loads `.env` using python-dotenv without overriding process variables or interpolating values. The probe pins `muse-spark-1.3` (ignoring `META_MODEL` for this probe), uses `reasoning_effort="low"`, existing `json_schema`/`strict: false`, 2048 completion tokens and the adapter's finite timeouts/zero SDK retries. Temperature is omitted. Missing credentials stop before provider construction. With credentials, it calls `MetaProvider(ProposalRequest(context, attempt=1))` exactly once using only the context from `unexpected_event()`; it discards the hand-authored proposal. It never invokes `run_agent()`, corrects a proposal or retries. The client is closed in `finally`.

The JSON report distinguishes schema parse SUCCESS/FAILURE from Python VALID/INVALID, lists validation issue codes and kept/moved-or-adjusted/postponed IDs, and checks fixed-call preservation and unexpected-event respect. API failures expose fixed sanitized codes only, without raw bodies, exception text, credentials or model explanations. If no usable proposal was parsed, Python validation is NOT_RUN. Exit codes: `0` for no-live mode or a Python-valid result, `1` for an invalid proposal or other failure, `2` for missing credentials/CLI misuse. Exit `0` does not establish a successful rescue: postponing study is explicitly marked valid but potentially low-quality because study can fit elsewhere in this scenario. No result claims optimality.

**Do not repeat failed live requests automatically**, including timeout, truncation, malformed output, rate-limit or billing/access failures. Inspect the sanitized code and review the cause before separately authorizing any further request. Do not silently increase the token limit, alter the schema/API contract or add retries.

Run all automated tests offline with `.\.venv\Scripts\python.exe -m pytest -q`. Focused probe tests are in `tests/test_live_structured_probe.py`; all fake responses and alternate test providers stay in tests. They block real HTTP and sockets and also exercise the production adapter/SDK with MockTransport.

## Remaining manual verification

1. The user reports the Custom day live generation and correction journey passed in the Windows ADMIN session. Review schedule quality, tradeoffs and latency for the final demonstration; broader reliability is not established.
2. A Custom day click authorizes at most two requests, with a second only after deterministic rejection. No additional live request is required or authorized by M5A. Never claim live success from offline tests.
3. Confirm input edits clear results, rerenders send no requests and provider failures safely terminate. M4C verifies these offline through the production click path with real SDK/MockTransport.
4. Confirm `.env` remains ignored/untracked and the repository remains private until the user authorizes publication. Do not modify billing settings.

Streamlit generation remains disabled unless manually opted in. Offline MockTransport results are deterministic Python tests, never live Muse output.

## Three-minute offline demo outline

| Time | Show and say |
| --- | --- |
| 0:00–0:20 | Explain the interrupted-day problem and state: this demo is an offline deterministic preview; connectivity and one structured scenario passed separately. |
| 0:20–0:55 | Example A: postponed reading and preserved fixed appointment. Point to the **hand-authored fixture** label and Python validation. |
| 0:55–1:25 | Example B: study moves around the visitor; the fixed call stays. These are fixture proposals, not Muse output. |
| 1:25–1:50 | Example C: immutable meeting/busy conflict is rejected. Explain the integration test proves agent preflight makes zero transport requests here. |
| 1:50–2:25 | Custom day: enter three pending activities, mark one fixed and add a conflicting busy window. Show hard-conflict feedback; no AI plan is generated. |
| 2:25–2:50 | Show `python -m pytest tests/test_integration.py -v`: full mocked SDK-to-presentation path, bounded correction and safe errors. The result rendering harness exists only in tests. |
| 2:50–3:00 | State the boundary: offline pipeline verified; the user separately reports a successful manual live correction. Neither establishes general model reliability. |

## Connectivity smoke record (already passed)

The user verified `scripts/smoke_meta.py` in the Windows ADMIN session: model `muse-spark-1.3`, response `DAYRESCUE_READY`, 382 total tokens. It verified basic connectivity only. There is no need to repeat that request for M4B. Never overwrite the existing `.env`, paste its contents into chat/screenshots or commit it. If access fails again, stop requests and review the account state locally at [Meta's dashboard](https://dev.meta.ai/).

## Git

The repository is published privately. M0–M4C are merged into `main`; PR #7 merged M4C. M5A uses a separate review branch:

```powershell
git switch feat/m5a-release-qa
git status --short
git ls-files .env  # must output nothing
git push -u origin feat/m5a-release-qa
```

If pushing fails, inspect `gh auth status` and your repository state. Never force push or merge automatically. The repo remains private; the user must authorize making it public before submitting the hackathon entry.

## Planned milestones

- M1: offline validator and contracts (implemented and locally verified).
- M2A: provider-independent orchestration, bounded correction loop and offline unit tests (implemented and merged via PR #2).
- M2B: Meta adapter and SDK transport tests (implemented offline and merged via PR #3).
- Live verification: connectivity smoke and one structured scheduling probe passed in the user's local session; the user also reports a successful manual Streamlit correction journey.
- M3A: interactive offline inputs, deterministic constraint feedback and example comparison (implemented and merged via PR #1).
- M3B: safe agent result presentation, session invalidation and AppTest coverage (merged via PR #4).
- M4C: explicitly gated Custom day generation, safe presentation and offline click-to-SDK/AppTest coverage merged via PR #7. The user reports manual live generation reached VALID after one correction.
- M4A: offline integration tests, activation checklist and honest three-minute demo outline (completed and merged via PR #5).
- M4B: merged via PR #6; user's manual structured probe passed Python validation with no postponed activities. No real requests were made by Codex.
- M5A: offline final release QA on `feat/m5a-release-qa`; see the QA report. Stop for technical review before merging.
- Remaining submission work: 3-minute video and submission.

### References

- https://dev.meta.ai/docs/cookbook/quickstart-chat-completions
- https://dev.meta.ai/docs/cookbook/tool-function-calling
