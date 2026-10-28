"""Run deterministic, manually authored fixtures without any Meta API access."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.scenarios import impossible_day, late_start, unexpected_event
from core.validator import detect_hard_conflicts, validate_plan


def main() -> None:
    for name, scenario in [
        ("A: Late Start", late_start),
        ("B: Unexpected Event", unexpected_event),
        ("C: Impossible Day", impossible_day),
    ]:
        context, proposal = scenario()
        result = validate_plan(context, proposal)
        print(f"{name}: {'VALID' if result.valid else 'INVALID'} (offline validator only)")
        if name.startswith("C:"):
            print("  Provable fixed-constraint conflicts:",
                  [problem.code for problem in detect_hard_conflicts(context)])
        for issue in result.issues:
            print(f"  - {issue.code}: {issue.message}")


if __name__ == "__main__":
    main()
