from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_is_read_only_and_labels_evidence():
    app = streamlit_testing.AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=30).run()
    assert not app.exception
    assert "Research Lab" in app.title[0].value
    assert "No human-rated safety findings" in app.warning[0].value
    assert not app.text_input
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
