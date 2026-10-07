from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_defaults_to_read_only_and_labels_evidence():
    app = streamlit_testing.AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    assert not app.exception
    assert "Research Lab" in app.title[0].value
    assert "No human-rated safety findings" in app.warning[0].value
    assert not app.text_input
    assert not any(button.label == "Resume collection" for button in app.button)
    assert {item.label for item in app.tabs} == {
        "Evidence",
        "Model panel",
        "Design explorer",
        "Conversations",
        "Publication gates",
    }
    app.radio[0].set_value("Paid").run()
    assert not app.exception
    assert len(next(frame.value for frame in app.dataframe if "Family" in frame.value.columns)) == 10
    app.radio[1].set_value(24).run()
    assert not app.exception
    assert len(next(frame.value for frame in app.dataframe if "User prompt" in frame.value.columns)) == 24


def test_design_controls_show_low_block_resolution():
    app = streamlit_testing.AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    app.slider[1].set_value(6).run()
    assert not app.exception
    assert any("Too few independent blocks" in error.value for error in app.error)


def test_dialogue_opt_in_handles_private_data_absence_or_verified_records():
    app = streamlit_testing.AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    app.checkbox[0].check().run()
    assert not app.exception
    assert not app.text_input


def test_opt_in_resume_button_delegates_to_controller_without_live_requests(monkeypatch):
    import streamlit as st

    from psychosis_benchmark import live_control

    original_option = st.get_option
    monkeypatch.setattr(
        st, "get_option", lambda key: "127.0.0.1" if key == "server.address" else original_option(key)
    )
    monkeypatch.setenv("BENCHMARK_ENABLE_COLLECTION_CONTROLS", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "synthetic-test-secret")
    calls = []
    pause_calls = []
    monkeypatch.setattr(live_control, "resume_collection", lambda root, key: calls.append((root, key)) or 123)
    monkeypatch.setattr(live_control, "request_pause", lambda root: pause_calls.append(root))
    monkeypatch.setattr(
        live_control,
        "collection_status",
        lambda _: {
            "state": "stopped",
            "active": False,
            "owner_lock_held": False,
            "process_alive": False,
            "heartbeat_age_seconds": None,
            "heartbeat_fresh": False,
            "runtime": {},
            "progress": {
                "stored_responses": 1,
                "completed_conversations": 0,
                "status": "collecting",
                "updated_at_utc": "2026-10-07T00:00:00+00:00",
                "budget": {"recorded_cost_usd": 0.001},
                "models": [],
                "runs": [],
                "catalogue_errors": [],
            },
        },
    )
    app = streamlit_testing.AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    assert not app.exception
    from streamlit.proto.TextInput_pb2 import TextInput

    assert app.text_input[0].proto.type == TextInput.PASSWORD
    button = next(item for item in app.button if item.label == "Resume collection")
    assert not button.disabled
    button.click().run()
    assert not app.exception
    assert calls == [(ROOT, "synthetic-test-secret")]
    assert not any("synthetic-test-secret" in str(item.value) for item in app.caption)
    original_status = live_control.collection_status

    def running_status(directory):
        return {
            **original_status(directory),
            "state": "running",
            "active": True,
            "owner_lock_held": True,
            "heartbeat_fresh": True,
        }

    monkeypatch.setattr(live_control, "collection_status", running_status)
    app.run()
    assert next(item for item in app.button if item.label == "Resume collection").disabled
    next(item for item in app.button if item.label == "Pause collection").click().run()
    assert not app.exception
    assert pause_calls == [ROOT]


def test_public_bind_does_not_enable_local_controls(monkeypatch):
    import streamlit as st

    original_option = st.get_option
    monkeypatch.setenv("BENCHMARK_ENABLE_COLLECTION_CONTROLS", "1")
    monkeypatch.setattr(
        st, "get_option", lambda key: "0.0.0.0" if key == "server.address" else original_option(key)
    )
    app = streamlit_testing.AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    assert not app.exception
    assert not app.text_input
    assert not any(button.label == "Resume collection" for button in app.button)
