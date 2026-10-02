from __future__ import annotations

import math

import pytest

from psychosis_benchmark.statistics import (
    cluster_bootstrap_interval,
    exact_agreement,
    holm_adjust,
    paired_mean_effect,
    sign_flip_p_value,
    weighted_kappa,
)


def test_agreement_metrics_have_known_values() -> None:
    assert exact_agreement([0, 1, 2, 2], [0, 1, 1, 2]) == 0.75
    assert math.isclose(weighted_kappa([0, 1, 2, 2], [0, 1, 1, 2]), 5 / 7)
    assert weighted_kappa([1, 1], [1, 1]) == 1.0


def test_exact_sign_flip_and_paired_effect() -> None:
    differences = [1.0, 1.0, 1.0, 1.0]
    assert paired_mean_effect(differences) == 1.0
    assert sign_flip_p_value(differences, seed=5) == 0.125
    assert sign_flip_p_value([0.0, 0.0], seed=5) == 1.0


def test_cluster_bootstrap_is_seeded_and_cluster_based() -> None:
    effects = [("family-a", 1.0), ("family-a", 2.0), ("family-b", -1.0)]
    first = cluster_bootstrap_interval(effects, seed=19, simulations=1000)
    second = cluster_bootstrap_interval(effects, seed=19, simulations=1000)
    assert first == second
    assert first[0] <= paired_mean_effect(value for _, value in effects) <= first[1]


def test_holm_adjustment_is_monotone_in_rank() -> None:
    adjusted = holm_adjust({"h1": 0.01, "h2": 0.04, "h3": 0.03})
    assert adjusted == {"h1": 0.03, "h3": 0.06, "h2": 0.06}


def test_statistics_reject_invalid_inputs() -> None:
    with pytest.raises(ValueError):
        exact_agreement([], [])
    with pytest.raises(ValueError):
        holm_adjust({"bad": 1.1})
