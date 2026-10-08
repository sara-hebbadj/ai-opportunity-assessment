"""Agreement statistics written out by hand (no scipy/sklearn), so each step can be explained.

- Cohen's kappa: agreement between two coders beyond what chance would give.
      kappa = (p_observed - p_chance) / (1 - p_chance)
  p_chance = sum over labels of (share of items coder A gave that label) x (share coder B gave it).
- Spearman's rho: how similar two rankings are (Pearson correlation of the ranks; ties get the
  average of the ranks they span).
"""

from __future__ import annotations

from collections import Counter


def cohen_kappa(labels_a: list, labels_b: list) -> float:
    if len(labels_a) != len(labels_b) or not labels_a:
        raise ValueError("need two label lists of the same, non-zero length")
    n = len(labels_a)
    observed = sum(a == b for a, b in zip(labels_a, labels_b, strict=True)) / n
    count_a, count_b = Counter(labels_a), Counter(labels_b)
    chance = sum((count_a[label] / n) * (count_b[label] / n) for label in set(count_a) | set(count_b))
    if chance == 1.0:  # both coders used one single label for everything: kappa is undefined
        return float("nan")
    return (observed - chance) / (1 - chance)


def kappa_per_label(labels_a: list, labels_b: list, label_set: list) -> dict:
    """One-vs-rest kappa for each label: did both coders agree that this snippet is (or is not) label X?"""
    return {
        label: cohen_kappa([a == label for a in labels_a], [b == label for b in labels_b])
        for label in label_set
    }


def average_ranks(values: list[float]) -> list[float]:
    """Rank 1 = smallest value. Tied values share the average of their positions."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        shared_rank = (position + end) / 2 + 1  # average of 1-based positions position..end
        for k in range(position, end + 1):
            ranks[order[k]] = shared_rank
        position = end + 1
    return ranks


def pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    mean_x, mean_y = sum(x) / n, sum(y) / n
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y, strict=True))
    var_x = sum((a - mean_x) ** 2 for a in x)
    var_y = sum((b - mean_y) ** 2 for b in y)
    if var_x == 0 or var_y == 0:
        return float("nan")
    return cov / (var_x * var_y) ** 0.5


def spearman_rho(x: list[float], y: list[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("need two lists of the same length (at least 2)")
    return pearson(average_ranks(x), average_ranks(y))


def confusion_pairs(labels_a: list, labels_b: list) -> list[tuple[str, str, int]]:
    """Disagreements as (label from A, label from B, count), most frequent first."""
    pairs = Counter((a, b) for a, b in zip(labels_a, labels_b, strict=True) if a != b)
    return [(a, b, count) for (a, b), count in pairs.most_common()]
