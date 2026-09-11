"""추출과 분류 평가에서 공유하는 Precision, Recall, F1 계산."""


def scores(tp: int, fp: int, fn: int) -> dict[str, float]:
    predicted_count = tp + fp
    expected_count = tp + fn
    precision = 0.0
    if predicted_count:
        precision = tp / predicted_count
    recall = 0.0
    if expected_count:
        recall = tp / expected_count
    f1 = 0.0
    precision_and_recall = precision + recall
    if precision_and_recall:
        f1 = 2 * precision * recall / precision_and_recall
    return {"precision": precision, "recall": recall, "f1": f1}


def metrics(tp: int, fp: int, fn: int) -> dict[str, int | float]:
    result = {"tp": tp, "fp": fp, "fn": fn}
    for name, value in scores(tp, fp, fn).items():
        result[name] = round(value, 6)
    return result
