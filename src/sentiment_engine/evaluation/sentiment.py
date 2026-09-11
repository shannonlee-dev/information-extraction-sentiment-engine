"""감성 분류 혼동행렬 평가 및 수식어 적용 전후 비교."""

from dataclasses import asdict
from typing import Any

from sentiment_engine.sentiment import analyze_sentiment
from .metrics import metrics, scores

_LABELS = ("positive", "negative", "neutral")


def evaluate_sentiment(
    cases: list[dict[str, Any]], apply_modifiers: bool = True
) -> dict[str, Any]:
    """혼동행렬에서 Accuracy와 F1을 구한다. Macro F1은 정답에 등장한 클래스의 평균이다."""
    confusion = {}
    for expected_label in _LABELS:
        confusion[expected_label] = dict.fromkeys(_LABELS, 0)
    errors = []
    for case in cases:
        result = analyze_sentiment(case["text"], apply_modifiers=apply_modifiers)
        expected = case["label"]
        confusion[expected][result.label] += 1
        if expected != result.label:
            errors.append(
                {
                    "case_id": case["id"],
                    "text": case["text"],
                    "expected": expected,
                    "predicted": result.label,
                    "score": result.score,
                    "matches": [asdict(match) for match in result.matches],
                }
            )
    per_class = {}
    gold_f1 = []
    for label in _LABELS:
        tp = confusion[label][label]
        support = sum(confusion[label].values())
        fn = support - tp
        fp = 0
        for other_label in _LABELS:
            if other_label != label:
                fp += confusion[other_label][label]
        per_class[label] = metrics(tp, fp, fn)
        if support:
            gold_f1.append(scores(tp, fp, fn)["f1"])
    correct = sum(confusion[label][label] for label in _LABELS)
    accuracy = 0.0
    if cases:
        accuracy = round(correct / len(cases), 6)
    macro_f1 = 0.0
    if gold_f1:
        macro_f1 = round(sum(gold_f1) / len(gold_f1), 6)
    return {
        "accuracy": accuracy,
        "per_class": per_class,
        "macro_f1": macro_f1,
        "confusion_matrix": confusion,
        "errors": errors,
    }


def compare_sentiment(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """같은 문장에 수식어 처리를 끄고 켠 결과를 비교한다."""
    without = evaluate_sentiment(cases, apply_modifiers=False)
    with_modifiers = evaluate_sentiment(cases, apply_modifiers=True)
    delta = {}
    for name in ("accuracy", "macro_f1"):
        difference = with_modifiers[name] - without[name]
        delta[name] = round(difference, 6)
    return {
        "without_modifiers": without,
        "with_modifiers": with_modifiers,
        "delta": delta,
    }
