"""M5D UX checks: genuine deterministic Python results, never live Muse evidence."""

from datetime import time
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.agent import run_agent
from core.models import Activity, BusyWindow, DayContext, ProposedPlan, ScheduledItem
from core.scenarios import impossible_day, late_start, unexpected_event
from ui.agent_result import INPUT_KEY, RESULT_KEY, SavedAgentResult
from ui.planner import prepare_comparison

APP = Path(__file__).resolve().parents[1] / "app.py"
HARNESS = """
import streamlit as st
from ui.planner import apply_planner_style
from ui.agent_result import render_agent_result
apply_planner_style()
render_agent_result(st.session_state['context'], st.session_state['result'])
"""


def render_result(context, result):
    app = AppTest.from_string(HARNESS)
    app.session_state["context"] = context
    app.session_state["result"] = result
    app.run()
    assert not app.exception
    return app


def html(app, marker):
    return "\n".join(item.value for item in app.markdown if marker in item.value)


def custom_app():
    app = AppTest.from_file(str(APP)).run()
    app.radio[0].set_value("Custom day").run()
    assert not app.exception
    return app


def test_top_plan_is_chronological_and_editor_keeps_all_controls():
    app = custom_app()
    app.text_input(key="activity_1_name").set_value("Later task")
    app.time_input(key="activity_1_start").set_value(time(12))
    app.text_input(key="activity_2_name").set_value("Earlier task")
    app.checkbox(key="activity_2_fixed").check()
    app.checkbox(key="activity_1_shorten").check().run()
    cards = html(app, 'aria-label="Planned activities"')
    assert cards.index("Earlier task") < cards.index("Activity 3") < cards.index("Later task")
    assert "12:00–13:00" in cards and "60 min" in cards
    assert "Fixed" in cards and "Flexible" in cards and "Medium priority" in cards
    assert "May shorten to 30 min" in cards and "Shortening not allowed" in cards
    assert app.subheader[0].value == "Today's plan"
    assert next(e for e in app.expander if e.label == "Edit planned activities").proto.expanded is False
    assert app.number_input[0].min == 3 and app.number_input[0].max == 8
    assert app.number_input[-1].min == 0 and app.number_input[-1].max == 10
    assert app.button(key="generate_live_ai").disabled


def test_overlap_feedback_distinguishes_fixed_and_half_open_boundaries():
    app = custom_app()
    app.checkbox(key="activity_1_fixed").check()
    app.number_input[-1].set_value(1).run()
    app.time_input(key="busy_0_start").set_value(time(9))
    app.time_input(key="busy_0_end").set_value(time(10)).run()
    feedback = html(app, 'class="dr-interruption"')
    assert "Activity 1 (Fixed)" in feedback
    assert "Activity 2" not in feedback  # Starts exactly at the busy interval's end.
    assert app.error and not app.success
    assert next(e for e in app.expander if e.label == "Conflict codes and affected activities").proto.expanded is False
    assert any("FIXED_BUSY_CONFLICT" in item.value for item in app.markdown)


def test_empty_and_clear_interruptions_never_claim_full_feasibility():
    app = custom_app()
    assert any("No interruptions added" in c.value for c in app.caption)
    app.number_input[-1].set_value(1).run()
    assert "not proof of full feasibility" in html(app, 'class="dr-interruption"')
    assert not app.success


@pytest.mark.parametrize("scenario", [late_start, unexpected_event])
def test_example_comparison_and_postponement_follow_existing_python_fixtures(scenario):
    context, proposal = scenario()
    result = run_agent(context, lambda request: proposal)
    app = render_result(context, result)
    assert result.validation.valid and app.success
    assert "Before · Original plan" in [h.value for h in app.subheader]
    assert "After · Proposed plan" in [h.value for h in app.subheader]
    revised = html(app, 'aria-label="Proposed activities"')
    if scenario is late_start:
        assert "Morning reading" not in revised
        assert "Morning reading" in html(app, 'class="dr-unscheduled"')
        assert "Not assigned to another day" in html(app, 'class="dr-unscheduled"')
    else:
        assert "16:30–18:00" in revised
        assert "Moved from 13:00 to 16:30" in revised
        assert "Fixed call" in revised and "Kept at the same time and duration" in revised


def test_shortening_summary_recomputed_and_custom_text_escaped():
    context = DayContext(now_minute=480, activities=[
        Activity(id="fixed", title="Call", start_minute=540, duration_minutes=30, fixed=True),
        Activity(id="study", title='<img src="https://example.invalid/track"> Study', start_minute=600,
                 duration_minutes=60, min_duration_minutes=30),
        Activity(id="read", title="<script>untrusted()</script>", start_minute=720, duration_minutes=30),
    ], busy_windows=[BusyWindow(start_minute=600, end_minute=660)])
    proposal = ProposedPlan(scheduled=[ScheduledItem(activity_id="fixed", start_minute=540, duration_minutes=30),
                                      ScheduledItem(activity_id="study", start_minute=660, duration_minutes=30)],
                            postponed_ids=["read"], explanation="<script>Unverified rationale</script>")
    result = run_agent(context, lambda request: proposal)
    result.validation.kept_ids = ["forged", "forged"]
    app = render_result(context, result)
    revised = html(app, 'aria-label="Proposed activities"')
    assert "Moved from 10:00 to 11:00; Shortened from 60 to 30 min" in revised
    assert "1 kept, 1 moved or adjusted, 1 postponed" in html(app, 'class="dr-outcome"')
    assert "&lt;img" in revised and '<img src="https://' not in revised
    assert "&lt;script&gt;" in html(app, 'class="dr-unscheduled"')
    assert app.text[0].value == proposal.explanation
    assert next(e for e in app.expander if "Unverified AI rationale" in e.label).proto.expanded is False
    assert next(e for e in app.expander if e.label == "Validation details").proto.expanded is False
    assert next(e for e in app.expander if e.label == "Agent execution trace").proto.expanded is False


@pytest.mark.parametrize("status", ["invalid", "infeasible", "provider_error", "malformed_proposal"])
def test_failed_results_keep_error_visible_and_withhold_comparison(status):
    context, proposal = late_start()
    if status == "infeasible":
        context, _ = impossible_day()
        provider = lambda request: pytest.fail("Hard conflicts must skip the provider")
    elif status == "provider_error":
        def provider(request):
            raise RuntimeError("secret-provider-body")
    elif status == "malformed_proposal":
        provider = lambda request: {"unexpected": "secret-provider-body"}
    else:
        provider = lambda request: ProposedPlan()
    result = run_agent(context, provider)
    assert result.status == status
    app = render_result(context, result)
    assert app.error and not app.success and not app.text
    assert not html(app, 'aria-label="Proposed activities"')
    assert not html(app, 'class="dr-outcome"')
    assert "secret-provider-body" not in repr(app.get("root"))
    assert not any(e.error for e in app.expander)  # Critical errors are outside disclosures.
    if status == "invalid":
        assert "does not prove" in app.error[0].value


def test_all_flexible_postponed_is_explicitly_unscheduled():
    context = DayContext(now_minute=480, activities=[
        Activity(id="task", title="Study", start_minute=540, duration_minutes=60)])
    result = run_agent(context, lambda request: ProposedPlan(postponed_ids=["task"]))
    app = render_result(context, result)
    assert any("No activities scheduled" in item.value for item in app.info)
    assert "0 kept, 0 moved or adjusted, 1 postponed" in html(app, 'class="dr-outcome"')
    assert "Not assigned to another day" in html(app, 'class="dr-unscheduled"')


@pytest.mark.parametrize("field", ["label", "start", "end", "minimum"])
def test_interruption_and_minimum_edits_clear_actual_comparison_and_rationale(field):
    app = custom_app()
    app.number_input[-1].set_value(1)
    app.checkbox(key="activity_1_shorten").check().run()
    context = DayContext(day_start_minute=420, day_end_minute=1320, now_minute=480,
        activities=[Activity(id=f"activity_{i}", title=f"Activity {i}", start_minute=(8+i)*60,
                             duration_minutes=60, min_duration_minutes=30 if i == 1 else None)
                    for i in range(1, 4)],
        busy_windows=[BusyWindow(start_minute=780, end_minute=840, label="Unexpected event")])
    proposal = ProposedPlan(scheduled=[ScheduledItem(activity_id=a.id, start_minute=a.start_minute,
                            duration_minutes=30 if a.id == "activity_1" else 60) for a in context.activities],
                            explanation="Offline test-only rationale")
    result = run_agent(context, lambda request: proposal)
    app.session_state[RESULT_KEY] = SavedAgentResult(app.session_state[INPUT_KEY], result)
    app.run()
    assert app.success and app.text[0].value == proposal.explanation
    if field == "label":
        app.text_input(key="busy_0_label").set_value("Visitor").run()
    elif field in ("start", "end"):
        app.time_input(key=f"busy_0_{field}").set_value(time(13, 30)).run()
    else:
        app.number_input(key="activity_1_minimum").set_value(45).run()
    assert RESULT_KEY not in app.session_state
    assert not app.success and not app.text
    assert not html(app, 'aria-label="Proposed activities"')
    assert not app.exception


def test_rejected_or_tampered_proposal_never_produces_comparison():
    context, proposal = unexpected_event()
    result = run_agent(context, lambda request: proposal)
    result.plan.scheduled[0].start_minute = 780
    assert prepare_comparison(context, result.plan) is None
    app = render_result(context, result)
    assert app.error and not app.success
    assert not html(app, 'class="dr-outcome"')
    assert not html(app, 'aria-label="Proposed activities"')
