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
    return {"per_type": {kind: metrics(**counts[kind]) for kind in _TYPES},
            "micro": metrics(**totals), "errors": errors}
