"""Conservative, transparent cost planning for a generated manifest."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from psychosis_benchmark.schema import ManifestRow, ModelPanel


@dataclass(frozen=True)
class CostEstimate:
    model_id: str
    conversations: int
    planned_responses: int
    prompt_tokens: int
    completion_tokens: int
    prompt_cost_usd: float
    completion_cost_usd: float

    @property
    def total_cost_usd(self) -> float:
        return self.prompt_cost_usd + self.completion_cost_usd


def _conversation_token_ceiling(
    turns: int,
    prior_message_count: int,
    max_output_tokens: int,
    *,
    system_tokens: int = 700,
    user_tokens_per_turn: int = 150,
    prior_tokens_per_message: int = 150,
) -> tuple[int, int]:
    """Return a conservative ceiling under an accumulating transcript.

    The estimate assumes every earlier assistant response consumes the full completion envelope.
    Provider tokenisation can differ, so this supports budgeting rather than billing reconciliation.
    """

    context_tokens = prior_message_count * prior_tokens_per_message
    prompt_total = 0
    for turn in range(1, turns + 1):
        prompt_total += (
            system_tokens + context_tokens + turn * user_tokens_per_turn + (turn - 1) * max_output_tokens
        )
    return prompt_total, turns * max_output_tokens


def estimate_costs(
    rows: list[ManifestRow], model_panel: ModelPanel, max_output_tokens: int
) -> list[CostEstimate]:
    models = {model.model_id: model for model in model_panel.models}
    totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"conversations": 0, "responses": 0, "prompt": 0, "completion": 0}
    )
    for row in rows:
        prompt_tokens, completion_tokens = _conversation_token_ceiling(
            row.planned_turns, row.prior_message_count, max_output_tokens
        )
        item = totals[row.model_id]
        item["conversations"] += 1
        item["responses"] += row.planned_turns
        item["prompt"] += prompt_tokens
        item["completion"] += completion_tokens
    estimates: list[CostEstimate] = []
    for model_id in sorted(totals):
        model = models[model_id]
        item = totals[model_id]
        estimates.append(
            CostEstimate(
                model_id=model_id,
                conversations=item["conversations"],
                planned_responses=item["responses"],
                prompt_tokens=item["prompt"],
                completion_tokens=item["completion"],
                prompt_cost_usd=item["prompt"] / 1_000_000 * model.prompt_usd_per_million,
                completion_cost_usd=(item["completion"] / 1_000_000 * model.completion_usd_per_million),
            )
        )
    return estimates
