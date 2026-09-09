"""고정 정답 데이터로 추출 및 감성 분석을 평가한다."""

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


def load_extraction_cases():
    return json.loads(DEFAULT_EXTRACTION_CASES_PATH.read_text(encoding="utf-8"))["cases"]


def load_sentiment_cases():
    return json.loads(DEFAULT_SENTIMENT_CASES_PATH.read_text(encoding="utf-8"))["cases"]


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
    """유형·위치·정규화 값이 모두 같아야 정답이다. 값이 다르면 FP와 FN을 하나씩 센다."""
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
    totals = {name: sum(count[name] for count in counts.values()) for name in ("tp", "fp", "fn")}
    return {"per_type": {kind: _metrics(**counts[kind]) for kind in _TYPES},
            "micro": _metrics(**totals), "errors": errors}


def evaluate_sentiment(
    cases: list[dict[str, Any]], apply_modifiers: bool = True
) -> dict[str, Any]:
    """혼동행렬에서 Accuracy와 F1을 구한다. Macro F1은 정답에 등장한 클래스의 평균이다."""
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
            "confusion_matrix": confusion, "errors": errors}


def compare_sentiment(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """같은 문장에 수식어 처리를 끄고 켠 결과를 비교한다."""
    without = evaluate_sentiment(cases, apply_modifiers=False)
    with_modifiers = evaluate_sentiment(cases, apply_modifiers=True)
    return {"without_modifiers": without, "with_modifiers": with_modifiers,
            "delta": {name: round(with_modifiers[name] - without[name], 6)
                      for name in ("accuracy", "macro_f1")}}
