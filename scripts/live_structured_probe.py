"""One explicitly gated live request; run manually, never as an automated check."""

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.agent import ProposalRequest
from core.meta_client import DEFAULT_MODEL, MetaProvider, MetaProviderError
from core.models import ProposedPlan
from core.scenarios import unexpected_event
from core.validator import validate_plan


SAFE_ERROR_CODES = frozenset({
    "MISSING_CREDENTIALS", "INVALID_CONFIGURATION", "INVALID_REQUEST",
    "REQUEST_TOO_LARGE", "TIMEOUT", "SDK_ERROR", "MALFORMED_RESPONSE",
    "EMPTY_RESPONSE", "TRUNCATED_RESPONSE", "UNSUPPORTED_RESPONSE",
    "MALFORMED_PROPOSAL",
})


def _live_report() -> dict[str, object]:
    # Gate in main() precedes even loading the local credentials.
    load_dotenv(ROOT / ".env", override=False, interpolate=False)
    if not os.getenv("MODEL_API_KEY", "").strip():
        raise MetaProviderError("MISSING_CREDENTIALS")
    context, _ = unexpected_event()  # Discard the hand-authored proposal.
    provider = MetaProvider(model=DEFAULT_MODEL, reasoning_effort="low")
    try:
        # Deliberately bypass run_agent(): no correction and no second invocation.
        raw = provider(ProposalRequest(context.model_copy(deep=True), attempt=1))
        try:
            parsed = ProposedPlan.model_validate(raw)
            proposal = ProposedPlan.model_validate_json(parsed.model_dump_json(warnings=False))
        except (ValueError, TypeError):
            raise MetaProviderError("MALFORMED_PROPOSAL") from None
    finally:
        provider.close()

    result = validate_plan(context, proposal)
    call = next(activity for activity in context.activities if activity.id == "call")
    scheduled_call = [item for item in proposal.scheduled if item.activity_id == call.id]
    fixed_preserved = (
        len(scheduled_call) == 1 and call.id not in proposal.postponed_ids
        and scheduled_call[0].start_minute == call.start_minute
        and scheduled_call[0].duration_minutes == call.duration_minutes
    )
    event_respected = all(
        item.end_minute <= busy.start_minute or item.start_minute >= busy.end_minute
        for item in proposal.scheduled for busy in context.busy_windows
    )
    return {
        "schema_parse": "SUCCESS",
        "python_validation": "VALID" if result.valid else "INVALID",
        "validation_issue_codes": [issue.code for issue in result.issues],
        "kept_ids": result.kept_ids,
        "moved_or_adjusted_ids": result.moved_or_adjusted_ids,
        "postponed_ids": result.postponed_ids,
        "fixed_call_preserved": fixed_preserved,
        "unexpected_event_respected": event_respected,
        "quality": (
            "VALID_BUT_POTENTIALLY_LOW_QUALITY: study can fit without postponement."
            if result.valid and "study" in result.postponed_ids else
            "Requires human review; hard-constraint validity does not establish optimality."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--live", action="store_true", help="Send exactly one provider request.")
    args = parser.parse_args(argv)
    if not args.live:
        print("PROBE NOT RUN: --live is required; no credentials loaded or API request sent.")
        return 0

    try:
        report = _live_report()
    except Exception as exc:
        # Never render exception text, raw HTTP bodies, explanations or SDK objects.
        code = exc.code if isinstance(exc, MetaProviderError) else "PROBE_ERROR"
        if code not in SAFE_ERROR_CODES:
            code = "PROBE_ERROR"
        print(json.dumps({
            "schema_parse": "FAILURE" if code == "MALFORMED_PROPOSAL" else "NOT_COMPLETED",
            "python_validation": "NOT_RUN", "error_codes": [code],
        }), file=sys.stderr)
        return 2 if code == "MISSING_CREDENTIALS" else 1

    print(json.dumps(report, indent=2))
    return 0 if report["python_validation"] == "VALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
