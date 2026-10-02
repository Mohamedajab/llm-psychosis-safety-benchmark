"""Deterministic, blinded annotation packets for Study V3.

The public packet contains only text needed to score an assistant turn.  The
private key remains outside the packet and must be held by a study member who
does not rate items.
"""

from __future__ import annotations

import hashlib
import hmac
import random
from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceAnnotationItem(BaseModel):
    """One collected turn before blinding."""

    model_config = ConfigDict(extra="forbid")

    source_item_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    scenario_family: str = Field(min_length=1)
    presentation: str = Field(min_length=1)
    context_condition: str = Field(min_length=1)
    repetition: int = Field(ge=1)
    turn: int = Field(ge=1, le=12)
    transcript: tuple[dict[str, str], ...]
    response_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("transcript")
    @classmethod
    def validate_transcript(cls, value: tuple[dict[str, str], ...]) -> tuple[dict[str, str], ...]:
        if not value:
            raise ValueError("transcript cannot be empty")
        for message in value:
            if set(message) != {"role", "content"}:
                raise ValueError("each transcript message needs only role and content")
            if message["role"] not in {"system", "user", "assistant"}:
                raise ValueError("unsupported transcript role")
            if not message["content"].strip():
                raise ValueError("transcript content cannot be blank")
        return value


class BlindedAnnotationItem(BaseModel):
    """Rater-facing item: no model or experimental labels."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "3.0.0"
    blind_item_id: str
    blind_conversation_id: str
    block_id: str
    position: int = Field(ge=1)
    turn: int = Field(ge=1, le=12)
    transcript: tuple[dict[str, str], ...]
    response_hash: str
    rubric_version: str


class BlindingKeyRow(BaseModel):
    """Private link between a blinded item and prespecified study factors."""

    model_config = ConfigDict(extra="forbid")

    blind_item_id: str
    blind_conversation_id: str
    source_item_id: str
    run_id: str
    model_id: str
    scenario_family: str
    presentation: str
    context_condition: str
    repetition: int
    turn: int
    response_hash: str


class AnnotationPacket(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: tuple[BlindedAnnotationItem, ...]
    key: tuple[BlindingKeyRow, ...]


class RatingRecord(BaseModel):
    """One immutable rater submission; absence and N/A are not conflated."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["3.0.0"] = "3.0.0"
    blind_item_id: str = Field(min_length=1)
    rater_code: str = Field(pattern=r"^rater_[a-z0-9_]+$")
    rubric_version: str = Field(min_length=1)
    rating_status: Literal["scored", "unscorable"]
    P1: int | None = Field(default=None, ge=0, le=2)
    P2: int | Literal["NA"] | None = None
    P3: int | Literal["NA"] | None = None
    P4: int | None = Field(default=None, ge=0, le=2)
    P5: int | None = Field(default=None, ge=0, le=2)
    S1: int | None = Field(default=None, ge=0, le=2)
    S2: int | None = Field(default=None, ge=0, le=2)
    S3: int | None = Field(default=None, ge=0, le=2)
    S4: int | None = Field(default=None, ge=0, le=2)
    S5: int | None = Field(default=None, ge=0, le=2)
    reason: str | None = None

    @field_validator("P2", "P3")
    @classmethod
    def validate_nullable_score(cls, value: int | str | None) -> int | str | None:
        if isinstance(value, int) and value not in {0, 1, 2}:
            raise ValueError("ordinal scores must be 0, 1, or 2")
        return value

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("reason cannot be blank")
        return value

    @field_validator("S1", "S2", "S3", "S4", "S5", mode="before")
    @classmethod
    def reject_na_for_secondary(cls, value: Any) -> Any:
        if value == "NA":
            raise ValueError("secondary axes do not permit N/A")
        return value

    def model_post_init(self, __context: Any) -> None:
        scores = [self.P1, self.P2, self.P3, self.P4, self.P5, self.S1, self.S2, self.S3, self.S4, self.S5]
        if self.rating_status == "scored" and any(value is None for value in scores):
            raise ValueError("scored records require every axis; use NA only where permitted")
        if self.rating_status == "unscorable" and any(value is not None for value in scores):
            raise ValueError("unscorable records cannot contain axis scores")
        if self.rating_status == "unscorable" and not self.reason:
            raise ValueError("unscorable records require a reason")


def _blind_id(secret: bytes, namespace: str, value: str) -> str:
    digest = hmac.new(secret, f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()
    return f"{namespace}_{digest[:20]}"


def build_annotation_packet(
    source_items: list[SourceAnnotationItem],
    *,
    secret: bytes,
    rubric_version: str,
    seed: int,
    block_size: int = 60,
) -> AnnotationPacket:
    """Blind and randomise complete conversations into rater blocks.

    Conversations are kept intact to prevent transcript fragments crossing
    blocks. Their order, and the order of blocks, are deterministic for an
    independently recorded seed. The secret must not be committed.
    """

    if len(secret) < 32:
        raise ValueError("blinding secret must contain at least 32 bytes")
    if block_size < 1:
        raise ValueError("block_size must be positive")
    source_ids = [item.source_item_id for item in source_items]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("source_item_id values must be unique")
    grouped: dict[str, list[SourceAnnotationItem]] = defaultdict(list)
    for item in source_items:
        grouped[item.run_id].append(item)
    for run_id, items in grouped.items():
        turns = sorted(item.turn for item in items)
        if turns != list(range(1, len(items) + 1)):
            raise ValueError(f"conversation {run_id} has missing or duplicate turns")
        if len(items) > block_size:
            raise ValueError(f"block_size cannot fit complete conversation {run_id}")

    run_ids = sorted(grouped)
    random.Random(seed).shuffle(run_ids)
    public: list[BlindedAnnotationItem] = []
    private: list[BlindingKeyRow] = []
    block_number = 1
    position = 0
    for run_id in run_ids:
        conversation = sorted(grouped[run_id], key=lambda item: item.turn)
        if position and position + len(conversation) > block_size:
            block_number += 1
            position = 0
        block_id = f"block_{block_number:03d}"
        blind_conversation_id = _blind_id(secret, "conversation", run_id)
        for item in conversation:
            position += 1
            blind_item_id = _blind_id(secret, "item", item.source_item_id)
            public.append(
                BlindedAnnotationItem(
                    blind_item_id=blind_item_id,
                    blind_conversation_id=blind_conversation_id,
                    block_id=block_id,
                    position=position,
                    turn=item.turn,
                    transcript=item.transcript,
                    response_hash=item.response_hash,
                    rubric_version=rubric_version,
                )
            )
            private.append(
                BlindingKeyRow(
                    blind_item_id=blind_item_id,
                    blind_conversation_id=blind_conversation_id,
                    source_item_id=item.source_item_id,
                    run_id=item.run_id,
                    model_id=item.model_id,
                    scenario_family=item.scenario_family,
                    presentation=item.presentation,
                    context_condition=item.context_condition,
                    repetition=item.repetition,
                    turn=item.turn,
                    response_hash=item.response_hash,
                )
            )
    return AnnotationPacket(items=tuple(public), key=tuple(private))


def assert_packet_blinded(packet_value: dict[str, Any]) -> None:
    """Reject protected-factor names anywhere in a rater-facing packet."""

    forbidden = {"model_id", "presentation", "scenario_family", "context_condition", "run_id"}

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            leaked = forbidden.intersection(value)
            if leaked:
                raise ValueError(f"protected fields leaked at {path}: {sorted(leaked)}")
            for key, child in value.items():
                walk(child, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")

    walk(packet_value, "packet")
