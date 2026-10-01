from __future__ import annotations

from pathlib import Path

import pytest

from psychosis_benchmark.contexts import (
    ContextConfigurationError,
    load_context_histories,
    messages_for_condition,
    validate_context_coverage,
)
from psychosis_benchmark.design import load_study

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "study-v3"


def test_standard_history_is_concrete_and_balanced() -> None:
    study = load_study(CONFIG)
    histories = load_context_histories(CONFIG / "contexts")
    messages = messages_for_condition(study, "standard_history_24", histories)
    assert len(messages) == 24
    assert [message["role"] for message in messages] == [
        "user" if index % 2 == 0 else "assistant" for index in range(24)
    ]


def test_no_history_is_empty() -> None:
    study = load_study(CONFIG)
    histories = load_context_histories(CONFIG / "contexts")
    assert messages_for_condition(study, "no_history", histories) == ()


def test_deep_history_fails_closed_until_authored() -> None:
    study = load_study(CONFIG)
    histories = load_context_histories(CONFIG / "contexts")
    with pytest.raises(ContextConfigurationError, match="no frozen history"):
        messages_for_condition(study, "deep_history_96", histories)
    errors, warnings = validate_context_coverage(study, histories)
    assert errors == []
    assert "deep_history_96 has no authored context history" in warnings
