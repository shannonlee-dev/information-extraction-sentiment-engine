"""추출과 분류 평가에서 공유하는 Precision, Recall, F1 계산."""


def scores(tp: int, fp: int, fn: int) -> dict[str, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}



def metrics(tp: int, fp: int, fn: int) -> dict[str, int | float]:
    return {"tp": tp, "fp": fp, "fn": fn,
            **{name: round(value, 6) for name, value in scores(tp, fp, fn).items()}}
