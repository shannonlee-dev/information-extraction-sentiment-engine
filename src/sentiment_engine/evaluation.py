"""Validated fixed datasets and exact, reproducible analyzer metrics."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sentiment_engine.extraction import extract_information
from sentiment_engine.sentiment import analyze_sentiment


_TYPES = ("email", "phone", "date", "money", "url")
_LABELS = ("positive", "negative", "neutral")
_FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
DEFAULT_EXTRACTION_CASES_PATH = _FIXTURES / "extraction_cases.json"
DEFAULT_SENTIMENT_CASES_PATH = _FIXTURES / "sentiment_cases.json"
_FEATURE_MINIMUMS = {
    "emphasis": 15,
    "single-negation": 15,
    "double-negation": 10,
    "mixed-polarity": 10,
    "challenge": 10,
}


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _load_cases(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as resource:
        data = json.load(resource)
    cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(cases, list):
        raise ValueError("dataset: cases must be a list")
    seen = set()
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"case[{index}]: case must be an object")
        case_id = case.get("id")
        if not _nonempty_string(case_id):
            raise ValueError(f"case[{index}]: id must be a nonempty string")
        if case_id in seen:
            raise ValueError(f"{case_id}: duplicate id")
        seen.add(case_id)
        if not _nonempty_string(case.get("text")):
            raise ValueError(f"{case_id}: text must be a nonempty string")
    return cases


def load_extraction_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load gold extraction cases in file order, validating spans and coverage."""
    cases = _load_cases(DEFAULT_EXTRACTION_CASES_PATH if path is None else path)
    type_counts: Counter[str] = Counter()
    variants: dict[str, set[str]] = {kind: set() for kind in _TYPES}
    for case in cases:
        case_id, text = case["id"], case["text"]
        if not _nonempty_string(case.get("variant")):
            raise ValueError(f"{case_id}: variant must be a nonempty string")
        if not isinstance(case.get("expected"), list):
            raise ValueError(f"{case_id}: expected must be a list")
        present = set()
        for item in case["expected"]:
            if not isinstance(item, dict):
                raise ValueError(f"{case_id}: expected item must be an object")
            kind = item.get("type")
            if kind not in _TYPES:
                raise ValueError(f"{case_id}: unsupported type")
            start, end = item.get("start"), item.get("end")
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
                raise ValueError(f"{case_id}: invalid offsets")
            raw = text[start:end]
            if item.get("raw") != raw:
                raise ValueError(f"{case_id}: raw does not match text span")
            item["raw"] = raw
            normalized = item.get("normalized")
            if kind == "money":
                valid = (
                    isinstance(normalized, dict)
                    and set(normalized) == {"amount", "currency"}
                    and type(normalized["amount"]) is int
                    and normalized["amount"] >= 0
                    and normalized["currency"] in ("KRW", "USD")
                )
            else:
                valid = _nonempty_string(normalized)
            if not valid:
                raise ValueError(f"{case_id}: invalid normalized value for {kind}")
            if case["variant"] != "challenge-unsupported":
                present.add(kind)
                variants[kind].add(case["variant"])
        type_counts.update(present)
    if len(cases) < 50:
        raise ValueError("dataset: requires at least 50 extraction cases")
    for kind in _TYPES:
        if type_counts[kind] < 10:
            raise ValueError(f"dataset: {kind} requires at least 10 supported cases")
        if len(variants[kind]) < 3:
            raise ValueError(f"dataset: {kind} requires at least three supported variants")
    return cases


def load_sentiment_cases(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load balanced binary sentiment gold with the required feature coverage."""
    cases = _load_cases(DEFAULT_SENTIMENT_CASES_PATH if path is None else path)
    labels: Counter[str] = Counter()
    features: Counter[str] = Counter()
    for case in cases:
        case_id = case["id"]
        if case.get("label") not in ("positive", "negative"):
            raise ValueError(f"{case_id}: label must be positive or negative")
        tags = case.get("features")
        if not isinstance(tags, list) or any(not _nonempty_string(tag) for tag in tags):
            raise ValueError(f"{case_id}: features must be a list of nonempty strings")
        labels[case["label"]] += 1
        features.update(set(tags))
    if len(cases) < 100:
        raise ValueError("dataset: requires at least 100 sentiment cases")
    if labels["positive"] != labels["negative"]:
        raise ValueError("dataset: sentiment labels must be balanced")
    for feature, minimum in _FEATURE_MINIMUMS.items():
        if features[feature] < minimum:
            raise ValueError(f"dataset: {feature} requires at least {minimum} cases")
    return cases


def _scores(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _metrics(tp: int, fp: int, fn: int) -> dict[str, int | float]:
    return {"tp": tp, "fp": fp, "fn": fn,
            **{name: round(value, 6) for name, value in _scores(tp, fp, fn).items()}}


def _item_key(case_id: str, item: dict[str, Any]) -> tuple:
    normalized = item["normalized"]
    if item["type"] == "money":
        normalized = (normalized["amount"], normalized["currency"])
    return case_id, item["type"], item["start"], item["end"], normalized


def _ordered(keys: set[tuple]) -> list[tuple]:
    return sorted(keys, key=lambda key: (key[2], key[3], key[1], repr(key[4])))


def evaluate_extraction(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Score exact case/type/span/normalization matches; mismatches are FP + FN."""
    counts = {kind: Counter(tp=0, fp=0, fn=0) for kind in _TYPES}
    errors = []
    for case in cases:
        case_id, text = case["id"], case["text"]
        gold = {_item_key(case_id, item): item for item in case["expected"]}
        predicted_items = [asdict(item) for item in extract_information(text).items]
        predicted = {_item_key(case_id, item): item for item in predicted_items}
        gold_keys, predicted_keys = set(gold), set(predicted)
        missing, extra = gold_keys - predicted_keys, predicted_keys - gold_keys
        for key in gold_keys & predicted_keys:
            counts[key[1]]["tp"] += 1
        for kind, keys, items in (("fn", missing, gold), ("fp", extra, predicted)):
            for key in _ordered(keys):
                counts[key[1]][kind] += 1
                errors.append({"case_id": case_id, "text": text, "kind": kind,
                               "expected": items[key] if kind == "fn" else None,
                               "predicted": items[key] if kind == "fp" else None})
        for gold_key in _ordered(missing):
            for predicted_key in _ordered(extra):
                if gold_key[:4] == predicted_key[:4]:
                    errors.append({"case_id": case_id, "text": text, "kind": "normalization_mismatch",
                                   "expected": gold[gold_key], "predicted": predicted[predicted_key]})
    totals = {name: sum(count[name] for count in counts.values()) for name in ("tp", "fp", "fn")}
    return {"per_type": {kind: _metrics(**counts[kind]) for kind in _TYPES},
            "micro": _metrics(**totals), "errors": errors}


def evaluate_sentiment(
    cases: list[dict[str, Any]], apply_modifiers: bool = True
) -> dict[str, Any]:
    """Score predictions against gold, retaining output-only neutral mistakes."""
    confusion = {gold: {predicted: 0 for predicted in _LABELS} for gold in _LABELS}
    errors = []
    for case in cases:
        result = analyze_sentiment(case["text"], apply_modifiers=apply_modifiers)
        expected = case["label"]
        confusion[expected][result.label] += 1
        if expected != result.label:
            errors.append({"case_id": case["id"], "text": case["text"], "expected": expected,
                           "predicted": result.label, "score": result.score,
                           "matches": [asdict(match) for match in result.matches]})
    per_class = {}
    gold_f1 = []
    for label in _LABELS:
        tp = confusion[label][label]
        support = sum(confusion[label].values())
        fn = support - tp
        fp = sum(confusion[other][label] for other in _LABELS if other != label)
        per_class[label] = _metrics(tp, fp, fn)
        if support:
            gold_f1.append(_scores(tp, fp, fn)["f1"])
    correct = sum(confusion[label][label] for label in _LABELS)
    return {"accuracy": round(correct / len(cases), 6) if cases else 0.0,
            "per_class": per_class,
            "macro_f1": round(sum(gold_f1) / len(gold_f1), 6) if gold_f1 else 0.0,
            "positive_f1": per_class["positive"]["f1"],
            "confusion_matrix": confusion, "errors": errors}


def compare_sentiment(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare the same gold cases before and after modifier rules."""
    without = evaluate_sentiment(cases, apply_modifiers=False)
    with_modifiers = evaluate_sentiment(cases, apply_modifiers=True)
    return {"without_modifiers": without, "with_modifiers": with_modifiers,
            "delta": {name: round(with_modifiers[name] - without[name], 6)
                      for name in ("accuracy", "macro_f1", "positive_f1")}}
