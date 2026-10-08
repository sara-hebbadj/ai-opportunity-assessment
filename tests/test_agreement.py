"""Cohen's kappa and Spearman's rho against values worked out by hand."""

from __future__ import annotations

import math

import pytest

from opportunity_assessment.agreement import (
    average_ranks,
    cohen_kappa,
    confusion_pairs,
    kappa_per_label,
    spearman_rho,
)


def test_kappa_hand_example():
    # 10 items, agree on 8. A: 5 x "a", 5 x "b". B: 4 x "a", 6 x "b".
    a = ["a"] * 5 + ["b"] * 5
    b = ["a"] * 4 + ["b"] + ["b"] * 4 + ["a"]
    # p_observed = 8/10; p_chance = 0.5*0.5 + 0.5*0.5 = 0.5 -> kappa = (0.8-0.5)/(1-0.5) = 0.6
    assert cohen_kappa(a, b) == pytest.approx(0.6)


def test_kappa_perfect_and_chance():
    assert cohen_kappa(["x", "y", "x"], ["x", "y", "x"]) == pytest.approx(1.0)
    # Coder B always says "x": observed 0.5, chance 0.5 -> 0
    assert cohen_kappa(["x", "y", "x", "y"], ["x", "x", "x", "x"]) == pytest.approx(0.0)


def test_kappa_undefined_when_both_use_one_label():
    assert math.isnan(cohen_kappa(["x", "x"], ["x", "x"]))


def test_kappa_needs_same_length():
    with pytest.raises(ValueError):
        cohen_kappa(["a"], ["a", "b"])


def test_kappa_per_label_is_one_vs_rest():
    a = ["T1", "T1", "T2", "T3"]
    b = ["T1", "T2", "T2", "T3"]
    per = kappa_per_label(a, b, ["T1", "T2", "T3"])
    assert per["T3"] == pytest.approx(1.0)
    # T1 yes/no: A = [1,1,0,0], B = [1,0,0,0]: observed 3/4, chance 0.5*0.25 + 0.5*0.75 = 0.5 -> 0.5
    assert per["T1"] == pytest.approx(0.5)


def test_average_ranks_with_ties():
    assert average_ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]


def test_spearman_hand_examples():
    assert spearman_rho([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman_rho([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    # one swap in 4 items: d^2 = 1 + 1 = 2 -> 1 - 6*2/(4*15) = 0.8
    assert spearman_rho([1, 2, 3, 4], [1, 3, 2, 4]) == pytest.approx(0.8)


def test_confusion_pairs_most_common_first():
    pairs = confusion_pairs(["T1", "T1", "T2", "T3"], ["T3", "T3", "T2", "T1"])
    assert pairs[0] == ("T1", "T3", 2)
