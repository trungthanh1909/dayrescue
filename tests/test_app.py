from datetime import time
from pathlib import Path

import httpx
import pytest
import requests
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


@pytest.fixture(autouse=True)
def forbid_api_requests(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Offline UI must not send HTTP requests")
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked)
    monkeypatch.setattr(requests.Session, "request", blocked)


def custom_app():
    app = AppTest.from_file(str(APP)).run()
    app.radio[0].set_value("Custom day").run()
    assert not app.exception
    return app


@pytest.mark.parametrize("index,valid", [(0, True), (1, True), (2, False)])
def test_example_scenarios(index, valid):
    app = AppTest.from_file(str(APP)).run()
    app.selectbox[0].select_index(index).run()
    assert not app.exception
    assert app.button[0].disabled
    assert any("HAND-AUTHORED" in item.value for item in app.caption)
    assert len(app.columns) == 2
    if valid:
        assert "VALID" in app.success[0].value
    else:
        assert "INVALID" in app.error[0].value
        assert any("FIXED_BUSY_CONFLICT" in item.value for item in app.markdown)


def test_custom_activity_count_and_busy_window():
    app = custom_app()
    assert app.number_input[0].min == 3
    assert app.number_input[0].max == 8
    assert len(app.dataframe[0].value) == 3
    app.number_input[0].set_value(8).run()
    assert len(app.dataframe[0].value) == 8
    app.number_input[-1].set_value(1).run()
    assert len(app.dataframe[1].value) == 1
    assert app.button[0].disabled
    assert not app.success  # No proposal validity claim in custom mode.
    assert not app.exception
    assert any("does not prove full" in item.value for item in app.caption)


def test_custom_fixed_conflict_and_busy_feedback():
    app = custom_app()
    app.checkbox(key="activity_1_fixed").check().run()
    app.checkbox(key="activity_2_fixed").check().run()
    app.time_input(key="activity_2_start").set_value(time(9)).run()
    assert any("FIXED_FIXED_CONFLICT" in item.value for item in app.markdown)
    app.number_input[-1].set_value(1).run()
    app.time_input(key="busy_0_start").set_value(time(9)).run()
    assert any("FIXED_BUSY_CONFLICT" in item.value for item in app.markdown)
    assert not app.exception


def test_custom_errors_and_recovery():
    app = custom_app()
    app.number_input(key="activity_1_duration").set_value(0).run()
    assert "Please correct" in app.error[0].value
    assert not app.dataframe
    assert not app.exception
    app.number_input(key="activity_1_duration").set_value(60).run()
    app.text_input(key="activity_1_name").set_value("   ").run()
    assert app.error
    app.text_input(key="activity_1_name").set_value("Restored task").run()
    assert not app.error
    assert app.dataframe[0].value.iloc[0]["Activity"] == "Restored task"
    assert not app.exception


def test_shortening_only_applies_when_flexible_and_allowed():
    app = custom_app()
    assert not any(item.key == "activity_1_minimum" for item in app.number_input)
    app.checkbox(key="activity_1_shorten").check().run()
    app.number_input(key="activity_1_minimum").set_value(61).run()
    assert app.error
    app.checkbox(key="activity_1_fixed").check().run()
    assert not app.error
    assert not any(item.key == "activity_1_minimum" for item in app.number_input)
    assert not app.exception


@pytest.mark.parametrize("invalid_field", ["day_end", "now", "busy_end"])
def test_custom_invalid_time_relationships(invalid_field):
    app = custom_app()
    if invalid_field == "busy_end":
        app.number_input[-1].set_value(1).run()
        app.time_input(key="busy_0_end").set_value(time(12)).run()
    elif invalid_field == "day_end":
        app.time_input[2].set_value(time(6)).run()
    else:
        app.time_input[0].set_value(time(23)).run()
    assert app.error
    assert not app.dataframe
    assert not app.exception


def test_duplicate_names_keep_distinct_ids_and_mode_switches_work():
    app = custom_app()
    app.text_input(key="activity_1_name").set_value("Study").run()
    app.text_input(key="activity_2_name").set_value("Study").run()
    table = app.dataframe[0].value
    assert table["ID"].is_unique
    assert not app.error
    app.radio[0].set_value("Example scenarios").run()
    assert app.success
    app.radio[0].set_value("Custom day").run()
    assert not app.success
    assert not app.exception
