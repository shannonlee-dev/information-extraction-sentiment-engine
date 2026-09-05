"""Metrics and uncertainty intervals for the external sentiment benchmark."""

from __future__ import annotations

from collections import Counter, defaultdict
from math import sqrt
from typing import Any


GOLD_LABELS = ("positive", "negative")
PREDICTED_LABELS = ("positive", "negative", "neutral", "analysis_error")


def _index_predictions(gold: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not gold:
        raise ValueError("evaluation data must not be empty")
    gold_ids = [row.get("id") for row in gold]
    prediction_ids = [row.get("id") for row in predictions]
    if any(not isinstance(value, str) or not value for value in gold_ids + prediction_ids):
        raise ValueError("IDs must be nonempty strings")
    if len(set(gold_ids)) != len(gold_ids) or len(set(prediction_ids)) != len(prediction_ids):
        raise ValueError("IDs must be unique")
    if set(gold_ids) != set(prediction_ids):
        raise ValueError("prediction IDs must match gold IDs")
    by_id = {row["id"]: row for row in predictions}
    ordered: list[dict[str, Any]] = []
    for row in gold:
        label = row.get("label")
        predicted = by_id[row["id"]].get("predicted")
        if label not in GOLD_LABELS:
            raise ValueError("gold label must be positive or negative")
        if predicted not in PREDICTED_LABELS:
            raise ValueError("invalid predicted label")
        ordered.append({"gold": label, "predicted": predicted})
    return ordered


def _class_scores(tp: int, fp: int, fn: int) -> dict[str, int | float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1,
            "zero_denominator": tp + fp == 0 or tp + fn == 0}


def metrics(gold: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the 2x4 confusion matrix and binary metrics without rounding."""
    indexed = _index_predictions(gold, predictions)
    confusion = {label: {predicted: 0 for predicted in PREDICTED_LABELS} for label in GOLD_LABELS}
    for row in indexed:
        confusion[row["gold"]][row["predicted"]] += 1
    per_class: dict[str, dict[str, int | float | bool]] = {}
    for label in GOLD_LABELS:
        tp = confusion[label][label]
        fn = sum(confusion[label].values()) - tp
        fp = sum(confusion[other][label] for other in GOLD_LABELS if other != label)
        per_class[label] = _class_scores(tp, fp, fn)
    correct = sum(confusion[label][label] for label in GOLD_LABELS)
    macro_f1 = sum(per_class[label]["f1"] for label in GOLD_LABELS) / len(GOLD_LABELS)
    return {
        "n": len(indexed),
        "accuracy": correct / len(indexed),
        "macro_f1": macro_f1,
        "per_class": per_class,
        "confusion_matrix": confusion,
        "prediction_counts": {label: sum(row["predicted"] == label for row in indexed) for label in PREDICTED_LABELS},
        "neutral_count": sum(confusion[label]["neutral"] for label in GOLD_LABELS),
        "analysis_error_count": sum(confusion[label]["analysis_error"] for label in GOLD_LABELS),
    }


def wilson(correct: int, total: int) -> tuple[float, float]:
    if total <= 0 or not 0 <= correct <= total:
        raise ValueError("invalid counts")
    z = 1.959963984540054
    p = correct / total
    den = 1 + z * z / total
    center = (p + z * z / (2 * total)) / den
    half = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / den
    return max(0.0, center - half), min(1.0, center + half)


def _percentile(values: list[float], quantile: float) -> float:
    import numpy as np

    return float(np.percentile(np.asarray(values, dtype=float), quantile * 100, method="linear"))


def paired_intervals(
    gold: list[dict[str, Any]],
    a: list[dict[str, Any]],
    b: list[dict[str, Any]],
    *,
    seed: int,
    repeats: int = 2000,
) -> dict[str, Any]:
    """Compute paired cluster percentile bootstrap intervals for two predictions."""
    if repeats <= 0:
        raise ValueError("repeats must be positive")
    _index_predictions(gold, a)
    _index_predictions(gold, b)
    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(gold):
        group_id = row.get("group_id")
        if not isinstance(group_id, str) or not group_id:
            raise ValueError("gold rows require group_id")
        groups[group_id].append(index)
    if not groups:
        raise ValueError("bootstrap requires at least one group")
    try:
        import numpy as np
    except ImportError as error:
        raise RuntimeError("NumPy is required for paired bootstrap intervals") from error
    rng = np.random.Generator(np.random.PCG64(seed))
    group_ids = sorted(groups)
    by_a = {row["id"]: row for row in a}
    by_b = {row["id"]: row for row in b}
    accuracy_a: list[float] = []
    accuracy_b: list[float] = []
    f1_a: list[float] = []
    f1_b: list[float] = []
    degenerate = 0
    for _ in range(repeats):
        sampled = rng.integers(0, len(group_ids), size=len(group_ids))
        indexes = [row_index for sampled_index in sampled for row_index in groups[group_ids[int(sampled_index)]]]
        sampled_gold = [gold[index] for index in indexes]
        sampled_a = [by_a[gold[index]["id"]] for index in indexes]
        sampled_b = [by_b[gold[index]["id"]] for index in indexes]
        result_a = metrics(sampled_gold, sampled_a)
        result_b = metrics(sampled_gold, sampled_b)
        accuracy_a.append(result_a["accuracy"])
        accuracy_b.append(result_b["accuracy"])
        f1_a.append(result_a["macro_f1"])
        f1_b.append(result_b["macro_f1"])
        if any(result_a["per_class"][label]["zero_denominator"] or result_b["per_class"][label]["zero_denominator"] for label in GOLD_LABELS):
            degenerate += 1

    delta_accuracy = [right - left for left, right in zip(accuracy_a, accuracy_b)]
    delta_f1 = [right - left for left, right in zip(f1_a, f1_b)]
    return {
        "a": {"accuracy": [_percentile(accuracy_a, 0.025), _percentile(accuracy_a, 0.975)],
              "macro_f1": [_percentile(f1_a, 0.025), _percentile(f1_a, 0.975)]},
        "b": {"accuracy": [_percentile(accuracy_b, 0.025), _percentile(accuracy_b, 0.975)],
              "macro_f1": [_percentile(f1_b, 0.025), _percentile(f1_b, 0.975)]},
        "delta": {"accuracy": [_percentile(delta_accuracy, 0.025), _percentile(delta_accuracy, 0.975)],
                  "macro_f1": [_percentile(delta_f1, 0.025), _percentile(delta_f1, 0.975)]},
        "group_count": len(group_ids),
        "max_group_share": max(len(indexes) for indexes in groups.values()) / len(gold),
        "degenerate_repeats": degenerate,
        "seed": seed,
        "repeats": repeats,
    }
