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
        per_class[label] = metrics(tp, fp, fn)
        if support:
            gold_f1.append(scores(tp, fp, fn)["f1"])
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
