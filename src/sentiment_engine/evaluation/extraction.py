"""유형, 위치, 정규화 값의 정확한 일치에 기반한 추출 평가."""

from collections import Counter
from dataclasses import asdict
from typing import Any

from sentiment_engine.extraction import extract_information
from .metrics import metrics

_TYPES = ("email", "phone", "date", "money", "url")


def _item_key(case_id: str, item: dict[str, Any]) -> tuple:
    normalized = item["normalized"]
    if item["type"] == "money":
        normalized = (normalized["amount"], normalized["currency"])
    return case_id, item["type"], item["start"], item["end"], normalized


def _ordered(keys: set[tuple]) -> list[tuple]:
    def source_position(key: tuple) -> tuple:
        case_id, item_type, start, end, normalized = key
        return start, end, item_type, repr(normalized)

    return sorted(keys, key=source_position)


def evaluate_extraction(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """유형·위치·정규화 값이 모두 같아야 정답이다. 값이 다르면 FP와 FN을 하나씩 센다."""
    counts = {kind: Counter(tp=0, fp=0, fn=0) for kind in _TYPES}
    errors = []
    for case in cases:
        case_id = case["id"]
        text = case["text"]
        gold = {_item_key(case_id, item): item for item in case["expected"]}
        predicted_items = [asdict(item) for item in extract_information(text).items]
        predicted = {_item_key(case_id, item): item for item in predicted_items}
        gold_keys = set(gold)
        predicted_keys = set(predicted)
        missing = gold_keys - predicted_keys
        extra = predicted_keys - gold_keys
        for key in gold_keys & predicted_keys:
            counts[key[1]]["tp"] += 1
        for key in _ordered(missing):
            counts[key[1]]["fn"] += 1
            errors.append(
                {
                    "case_id": case_id,
                    "text": text,
                    "kind": "fn",
                    "expected": gold[key],
                    "predicted": None,
                }
            )
        for key in _ordered(extra):
            counts[key[1]]["fp"] += 1
            errors.append(
                {
                    "case_id": case_id,
                    "text": text,
                    "kind": "fp",
                    "expected": None,
                    "predicted": predicted[key],
                }
            )
    totals = {"tp": 0, "fp": 0, "fn": 0}
    per_type = {}
    for item_type in _TYPES:
        type_counts = counts[item_type]
        per_type[item_type] = metrics(**type_counts)
        for name in totals:
            totals[name] += type_counts[name]
    return {
        "per_type": per_type,
        "micro": metrics(**totals),
        "errors": errors,
    }
