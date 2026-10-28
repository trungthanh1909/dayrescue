# DayRescue

**When Life Interrupts, Your Plan Adapts.**

Meta Global AI Developer Hackathon 2026 — Indie Developer / Build for Your World.

DayRescue aims to let Muse Spark propose schedule tradeoffs and then run a deterministic Python validator. The validator alone decides whether a proposed plan satisfies declared hard constraints; it does **not** prove the plan optimal.

## Verified status / limitations

- **M0:** scaffold ready; local Windows environment setup, GitHub repository, Streamlit startup and Meta API smoke test have **not** been verified.
- **M1:** typed domain models, deterministic validator, sample fixtures and offline unit tests implemented. These tests use **no Meta API**.
- **M2:** Muse Spark agent loop **not implemented**; Meta account is currently restricted due to a payment authorization hold and the event organizers are investigating.
- **M3:** a limited offline Streamlit scenario/validator preview is present; real user-input UI and Meta agent integration are not implemented.

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

## Domain contracts

All times are local integer minutes since midnight, e.g. 09:30 = 570, using half-open intervals `[start, end)`. The intended UI accepts 3–8 *pending* activities; the backend schema permits 1–8 for minimal validator tests. Activities already completed are not modeled. An original activity has `start_minute`, `duration_minutes`, priority (`high`, `medium`, `low`) and optional `fixed` and `min_duration_minutes` (explicit shortening permission). Day context has `now_minute`, day horizon and 0–10 busy intervals. A proposal lists items scheduled with times/durations and IDs postponed. Each original ID must be scheduled exactly once or postponed exactly once. Fixed activities must retain original start and duration and cannot be postponed.

`core.validator.validate_plan()` checks duplicates, unknown/missing IDs, fixed immutability, duration/shortening permission, elapsed time, day horizon, busy overlaps, and schedule collisions. `detect_hard_conflicts()` catches provably impossible fixed constraints: fixed activity elapsed, out of bounds, clashes with busy time or other fixed activity. This is **not** a general optimizer or a complete feasibility proof.

`python scripts/demo_offline.py` and the Streamlit offline preview show three **hand-authored, offline** fixtures:

- Scenario A (late start) — a flexible activity is postponed, a fixed appointment stays.
- Scenario B (unexpected visitor) — study shifts around a new busy interval, a fixed call stays.
- Scenario C (impossible) — an unavoidable busy interval conflicts with an immutable meeting; validator rejects the plan.

These deterministic fixtures establish the Python contracts only; later the real Muse Spark model must generate proposals that pass this same validation.

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

```powershell
git init -b main
git add .
git status --short
git ls-files .env  # must output nothing
git commit -m "feat: bootstrap DayRescue offline validator"
```

Create a **new private** repository named `dayrescue`, then push with GitHub CLI if logged in:

```powershell
gh repo create dayrescue --private --source=. --remote=origin --push
```

If that command fails, inspect `gh auth status` and your repository state. Never force push. Make the repo public before submitting the hackathon entry. The GitHub repo is **not yet confirmed as created**.

## Planned milestones

- M1: offline validator and contracts (implemented, needs user's local verification).
- M2: API smoke success; real Muse Spark proposal -> `validate_plan()` -> feedback and second/final proposal, strict bounded retries.
- M3: Streamlit form and timeline with real AI status and short execution trace.
- M4: tests/edge cases and end-to-end demos.
- M5–M6: README, 3-minute video and submission.

### References

- https://dev.meta.ai/docs/cookbook/quickstart-chat-completions
- https://dev.meta.ai/docs/cookbook/tool-function-calling
