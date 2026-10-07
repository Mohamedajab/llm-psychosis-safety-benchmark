"""Dependency-light, auditable statistics for agreement and matched sensitivity analyses."""

from __future__ import annotations

import itertools
import math
import random
from collections import defaultdict
from collections.abc import Iterable


def exact_agreement(left: Iterable[int], right: Iterable[int]) -> float:
    pairs = list(zip(left, right, strict=True))
    if not pairs:
        raise ValueError("at least one rating pair is required")
    return sum(a == b for a, b in pairs) / len(pairs)


def weighted_kappa(
    left: Iterable[int], right: Iterable[int], categories: tuple[int, ...] = (0, 1, 2)
) -> float | None:
    """Linearly weighted Cohen kappa for prespecified ordinal categories."""

    pairs = list(zip(left, right, strict=True))
    if not pairs:
        raise ValueError("at least one rating pair is required")
    if len(categories) < 2 or len(set(categories)) != len(categories):
        raise ValueError("categories must contain at least two unique values")
    index = {value: position for position, value in enumerate(categories)}
    if any(a not in index or b not in index for a, b in pairs):
        raise ValueError("rating outside the declared categories")
    denominator = len(categories) - 1

    def agreement_weight(a: int, b: int) -> float:
        return 1 - abs(index[a] - index[b]) / denominator

    observed = sum(agreement_weight(a, b) for a, b in pairs) / len(pairs)
    left_counts = {category: 0 for category in categories}
    right_counts = {category: 0 for category in categories}
    for a, b in pairs:
        left_counts[a] += 1
        right_counts[b] += 1
    expected = sum(
        agreement_weight(a, b) * (left_counts[a] / len(pairs)) * (right_counts[b] / len(pairs))
        for a in categories
        for b in categories
    )
    if math.isclose(expected, 1.0):
        return None
    return (observed - expected) / (1 - expected)


def paired_mean_effect(differences: Iterable[float]) -> float:
    values = list(differences)
    if not values:
        raise ValueError("at least one paired difference is required")
    return sum(values) / len(values)


def sign_flip_p_value(differences: Iterable[float], *, seed: int, simulations: int = 100_000) -> float:
    """Two-sided paired randomisation test with exact enumeration when feasible."""

    values = [float(value) for value in differences if not math.isclose(float(value), 0.0)]
    if not values:
        return 1.0
    observed = abs(sum(values) / len(values))
    if len(values) <= 20:
        means = (
            abs(sum(value * sign for value, sign in zip(values, signs, strict=True)) / len(values))
            for signs in itertools.product((-1, 1), repeat=len(values))
        )
        extreme = sum(value >= observed - 1e-15 for value in means)
        return extreme / (2 ** len(values))
    if simulations < 999:
        raise ValueError("Monte Carlo sign-flip tests require at least 999 simulations")
    generator = random.Random(seed)
    extreme = 0
    for _ in range(simulations):
        simulated = abs(sum(value * generator.choice((-1, 1)) for value in values) / len(values))
        extreme += simulated >= observed - 1e-15
    return (extreme + 1) / (simulations + 1)


def cluster_bootstrap_interval(
    effects: Iterable[tuple[str, float]],
    *,
    seed: int,
    simulations: int = 10_000,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Percentile interval resampling prespecified independent clusters."""

    if simulations < 999:
        raise ValueError("cluster bootstrap requires at least 999 simulations")
    if not 0 < confidence < 1:
        raise ValueError("confidence must lie between zero and one")
    grouped: dict[str, list[float]] = defaultdict(list)
    for cluster_id, effect in effects:
        grouped[cluster_id].append(float(effect))
    if len(grouped) < 2:
        raise ValueError("at least two clusters are required")
    clusters = sorted(grouped)
    generator = random.Random(seed)
    estimates: list[float] = []
    for _ in range(simulations):
        sampled = [generator.choice(clusters) for _ in clusters]
        values = [value for cluster in sampled for value in grouped[cluster]]
        estimates.append(sum(values) / len(values))
    estimates.sort()
    tail = (1 - confidence) / 2
    lower_index = max(0, math.floor(tail * (simulations - 1)))
    upper_index = min(simulations - 1, math.ceil((1 - tail) * (simulations - 1)))
    return estimates[lower_index], estimates[upper_index]


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Holm adjusted p-values, preserving monotonicity and named hypotheses."""

    if any(not 0 <= value <= 1 for value in p_values.values()):
        raise ValueError("p-values must lie between zero and one")
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    total = len(ordered)
    running = 0.0
    adjusted: dict[str, float] = {}
    for rank, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (total - rank) * value))
        adjusted[name] = running
    return adjusted


def crossed_bootstrap_interval(
    effects: Iterable[tuple[str, str, float]],
    *,
    seed: int,
    simulations: int = 10_000,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Resample model and family IDs independently; retain their crossed cells.

    Cells are averaged before resampling so missing/repeated rows cannot silently
    change model-family weights. This is the pigeonhole bootstrap, not a
    guarantee of calibrated small-sample coverage or representative sampling.
    """

    if simulations < 999 or not 0 < confidence < 1:
        raise ValueError("require at least 999 simulations and confidence between zero and one")
    cells: dict[tuple[str, str], list[float]] = defaultdict(list)
    for model_id, family_id, effect in effects:
        if not math.isfinite(effect):
            raise ValueError("effects must be finite")
        cells[(model_id, family_id)].append(effect)
    models = sorted({key[0] for key in cells})
    families = sorted({key[1] for key in cells})
    if len(models) < 2 or len(families) < 2:
        raise ValueError("require at least two models and two scenario families")
    if set(cells) != set(itertools.product(models, families)):
        raise ValueError("crossed bootstrap requires a complete model-family grid")
    means = {key: sum(values) / len(values) for key, values in cells.items()}
    generator = random.Random(seed)
    estimates = []
    for _ in range(simulations):
        sampled_models = generator.choices(models, k=len(models))
        sampled_families = generator.choices(families, k=len(families))
        estimates.append(
            sum(means[(model, family)] for model in sampled_models for family in sampled_families)
            / (len(models) * len(families))
        )
    estimates.sort()
    tail = (1 - confidence) / 2
    return (
        estimates[math.floor(tail * (simulations - 1))],
        estimates[math.ceil((1 - tail) * (simulations - 1))],
    )
