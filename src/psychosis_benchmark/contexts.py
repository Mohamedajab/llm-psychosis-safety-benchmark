"""Versioned conversation histories for context-depth conditions."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from psychosis_benchmark.schema import StudyBundle


class ContextConfigurationError(ValueError):
    """A declared context condition has no valid message history."""


class ContextMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ContextHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str = Field(pattern=r"^[a-z][a-z0-9_]+$")
    version: str
    review_status: Literal["pending_review", "reviewed", "frozen"]
    purpose: str = Field(min_length=1)
    messages: tuple[ContextMessage, ...]

    @field_validator("messages")
    @classmethod
    def require_complete_exchanges(cls, messages: tuple[ContextMessage, ...]) -> tuple[ContextMessage, ...]:
        if not messages or len(messages) % 2:
            raise ValueError("context histories require complete user/assistant exchanges")
        expected = ["user" if index % 2 == 0 else "assistant" for index in range(len(messages))]
        if [message.role for message in messages] != expected:
            raise ValueError("context roles must alternate user then assistant")
        return messages

    @model_validator(mode="after")
    def avoid_research_cues(self) -> ContextHistory:
        prohibited = {
            "psychosis",
            "delusion",
            "rubric",
            "benchmark",
            "belief confirmation",
            "safety score",
        }
        text = " ".join(message.content.casefold() for message in self.messages)
        present = sorted(term for term in prohibited if term in text)
        if present:
            raise ValueError(f"context history contains research cues: {present}")
        return self


def load_context_histories(directory: str | Path) -> dict[str, ContextHistory]:
    root = Path(directory)
    histories: dict[str, ContextHistory] = {}
    for path in sorted(root.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            history = ContextHistory.model_validate(yaml.safe_load(handle))
        if history.context_id in histories:
            raise ContextConfigurationError(f"duplicate context ID: {history.context_id}")
        histories[history.context_id] = history
    return histories


def messages_for_condition(
    study: StudyBundle,
    condition: str,
    histories: dict[str, ContextHistory],
) -> tuple[dict[str, str], ...]:
    try:
        declared = study.design.contexts[condition]
    except KeyError as error:
        raise ContextConfigurationError(f"unknown context condition: {condition}") from error
    if declared.prior_message_count == 0:
        return ()
    try:
        history = histories[condition]
    except KeyError as error:
        raise ContextConfigurationError(
            f"{condition} declares {declared.prior_message_count} messages but has no frozen history"
        ) from error
    if len(history.messages) != declared.prior_message_count:
        raise ContextConfigurationError(
            f"{condition} declares {declared.prior_message_count} messages but history contains "
            f"{len(history.messages)}"
        )
    return tuple(message.model_dump() for message in history.messages)


def validate_context_coverage(
    study: StudyBundle,
    histories: dict[str, ContextHistory],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for condition, declared in study.design.contexts.items():
        if declared.prior_message_count == 0:
            continue
        history = histories.get(condition)
        if history is None:
            warnings.append(f"{condition} has no authored context history")
            continue
        if len(history.messages) != declared.prior_message_count:
            errors.append(f"{condition} message count does not match design.yaml")
        if history.review_status != "frozen":
            warnings.append(f"{condition} context history is not frozen")
    return errors, warnings
