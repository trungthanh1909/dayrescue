# DayRescue

**When Life Interrupts, Your Plan Adapts.**

Meta Global AI Developer Hackathon 2026 — Indie Developer / Build for Your World.

DayRescue aims to let Muse Spark propose schedule tradeoffs and then run a deterministic Python validator. The validator alone decides whether a proposed plan satisfies declared hard constraints; it does **not** prove the plan optimal.

## Verified status / limitations

- **M0:** verified on Windows with Python 3.13.1, Git 2.45.1 and GitHub CLI 2.96.0; local `.venv`, dependency installation, doctor and Streamlit startup passed. Private repository: [trungthanh1909/dayrescue](https://github.com/trungthanh1909/dayrescue), initial commit `06cb2c6`. Meta API smoke test remains **BLOCKED**, not PASS.
- **M1:** typed domain models, deterministic validator and A/B/C sample fixtures verified: all 30 original unit tests pass. These are deterministic Python tests using **no Meta API**.
- **M2A:** provider-independent offline orchestration implemented and merged via PR #2 (`9315b97`). It performs preflight, validates an injected provider's structured proposal and allows one correction.
- **M2B:** Meta provider adapter implemented with real OpenAI SDK serialization/parsing tested through in-memory HTTP transport only. No live Meta calls or Streamlit AI integration have been performed.
- **Live M2:** Meta account is still restricted due to a payment authorization hold; smoke test and live integration remain **BLOCKED** pending restored access and explicit authorization.
- **M3A:** interactive offline Streamlit UI implemented with example and custom-day modes. Custom input converts to existing Pydantic contracts and runs the narrow hard-conflict check. Example mode retains the two-column hand-authored proposal comparison. Focused conversion and AppTest coverage is included. No AI proposal generation or Meta agent integration is implemented.

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

Custom mode displays the original activities and runs `detect_hard_conflicts()` only. Fixed activity conflicts with elapsed time, the day horizon, busy windows or other fixed activities are shown with codes and activity names. Absence of detected conflicts does **not** prove full feasibility or optimality; flexible activities are not replanned and no custom proposal is generated.

The **Generate with AI (blocked)** button is disabled and has no request handler. Both modes operate offline. Times use whole local minutes within a single day; the UI accepts 00:00–23:59 and does not offer 24:00 or overnight windows. Inputs are session-local and are not saved to disk.

## Domain contracts

All times are local integer minutes since midnight, e.g. 09:30 = 570, using half-open intervals `[start, end)`. The intended UI accepts 3–8 *pending* activities; the backend schema permits 1–8 for minimal validator tests. Activities already completed are not modeled. An original activity has `start_minute`, `duration_minutes`, priority (`high`, `medium`, `low`) and optional `fixed` and `min_duration_minutes` (explicit shortening permission). Day context has `now_minute`, day horizon and 0–10 busy intervals. A proposal lists items scheduled with times/durations and IDs postponed. Each original ID must be scheduled exactly once or postponed exactly once. Fixed activities must retain original start and duration and cannot be postponed.

`core.validator.validate_plan()` checks duplicates, unknown/missing IDs, fixed immutability, duration/shortening permission, elapsed time, day horizon, busy overlaps, and schedule collisions. `detect_hard_conflicts()` catches provably impossible fixed constraints: fixed activity elapsed, out of bounds, clashes with busy time or other fixed activity. This is **not** a general optimizer or a complete feasibility proof.

`python scripts/demo_offline.py` and the Streamlit offline preview show three **hand-authored, offline** fixtures:

- Scenario A (late start) — a flexible activity is postponed, a fixed appointment stays.
- Scenario B (unexpected visitor) — study shifts around a new busy interval, a fixed call stays.
- Scenario C (impossible) — an unavoidable busy interval conflicts with an immutable meeting; validator rejects the plan.

These deterministic fixtures establish the Python contracts only; later the real Muse Spark model must generate proposals that pass this same validation.

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

Run `.\.venv\Scripts\python.exe -m pytest -q` for the complete offline suite. Agent tests block requests/httpx calls. Meta adapter tests use the real SDK with `httpx.MockTransport` and block socket connections. Real model behavior remains unverified; Streamlit continues to expose only the M3A offline UI with AI disabled.

## Meta provider adapter (M2B, offline verification only)

`core.meta_client.MetaProvider` implements the callable provider interface. Construction reads explicit configuration or the process variables `MODEL_API_KEY` and `META_MODEL`; it does not read `.env` automatically. Any future caller must load the local `.env` explicitly without printing it. Importing/constructing the adapter makes no API request; calling it would make a real request, so do not invoke it outside transport-mocked tests while access is restricted. Call `close()` when finished to release the SDK client.

The adapter uses the existing base URL `https://api.meta.ai/v1` and default model `muse-spark-1.3`, with configurable model ID. It sends a developer instruction containing hard constraints and one JSON user message containing the context and attempt number. Correction requests also contain the previous proposal and the exact structured validation issues. Requests use `response_format.json_schema` derived from `ProposedPlan`, `strict: false`, non-streaming output, and `max_completion_tokens=2048`. Input JSON and response content are each limited to 32,768 characters. SDK retries are disabled with `max_retries=0`; HTTP timeouts are 5 seconds for connection and 30 seconds for read/write/pool phases (not a total wall-clock deadline).

Empty responses, malformed envelopes/JSON/proposals, truncation (`finish_reason=length`), unexpected finish reasons, refusals, tool calls, missing credentials, SDK failures and timeouts raise `MetaProviderError` with a fixed code. Raw model output and SDK exception bodies are excluded from its public message/traceback. No repair request or fallback is attempted. A model-provided `valid` field is rejected by the existing schema. Parsing alone is not semantic validation: `run_agent()` still passes each returned proposal to the unchanged Python validator. Adapter exceptions become the agent's existing `provider_error` status with generic `PROVIDER_ERROR` trace; the adapter's more specific code is available when handling `MetaProviderError` directly.

**API evidence and remaining assumptions:** Meta's [quickstart](https://dev.meta.ai/docs/cookbook/quickstart-chat-completions) documents the base URL, model, developer role and completion response fields; its [structured output guide](https://dev.meta.ai/docs/structured-output) documents `json_schema` and non-strict schema normalization. [OpenAI SDK documentation](https://developers.openai.com/api/reference/python) describes timeout/retry configuration; the installed SDK's behavior is verified by transport tests. Acceptance of this exact generated schema (including `$defs` and constraints), `max_completion_tokens`, sufficient reasoning/output budget, account/model access and real latency still require a separately authorized live check after the account restriction is removed. No mocked result is evidence of live Meta compatibility or Muse output.

## Secure Meta API smoke test (ONLY once access is restored)

Meta dashboard: https://dev.meta.ai/. Credits being present and a card being added do **not** prove the API is enabled. Do not repeatedly attempt requests while the account is restricted.

```powershell
Copy-Item .env.example .env
notepad .env
# Edit .env locally, without sharing it:
# MODEL_API_KEY=your_real_key
# META_MODEL=muse-spark-1.3
.\.venv\Scripts\python.exe scripts\smoke_meta.py
```

The smoke script uses a single real Chat Completions request, timeout 30 seconds and `max_retries=0`. A nonzero exit is not a pass. Never paste the API key into prompts/screenshots and never commit `.env`.

## Git

The repository is already initialized on `main` and published privately. M3A and M2A were merged through PRs #1 and #2; M2B work uses a separate review branch:

```powershell
git switch feat/m2b-meta-provider
git status --short
git ls-files .env  # must output nothing
git push -u origin feat/m2b-meta-provider
```

If pushing fails, inspect `gh auth status` and your repository state. Never force push or merge automatically. The repo remains private; the user must authorize making it public before submitting the hackathon entry.

## Planned milestones

- M1: offline validator and contracts (implemented and locally verified).
- M2A: provider-independent orchestration, bounded correction loop and offline unit tests (implemented and merged via PR #2).
- M2B: Meta adapter and SDK transport tests (implemented offline; stop for technical review).
- Live M2: API smoke success and real Muse Spark validation/correction flow (blocked; requires restored account access and separate authorization).
- M3A: interactive offline inputs, deterministic constraint feedback and example comparison (implemented and merged via PR #1).
- Later M3 work requires separate authorization; real AI status/execution trace depend on M2 access and integration.
- M4: tests/edge cases and end-to-end demos.
- M5–M6: README, 3-minute video and submission.

### References

- https://dev.meta.ai/docs/cookbook/quickstart-chat-completions
- https://dev.meta.ai/docs/cookbook/tool-function-calling
