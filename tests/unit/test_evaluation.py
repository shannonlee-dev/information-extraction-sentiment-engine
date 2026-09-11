"""데이터 구성과 손으로 계산한 지표를 검증한다."""

from dataclasses import asdict

import pytest

from sentiment_engine.evaluation import (
    compare_sentiment,
    evaluate_extraction,
    evaluate_sentiment,
    load_extraction_cases,
    load_sentiment_cases,
)
from sentiment_engine.extraction import extract_information


def test_fixture_coverage_and_gold_spans():
    extraction = load_extraction_cases()
    assert len(extraction) >= 50
    assert len({case["id"] for case in extraction}) == len(extraction)
    for kind in ("email", "phone", "date", "money", "url"):
        cases = []
        for case in extraction:
            if case["variant"] == "challenge-unsupported":
                continue
            for item in case["expected"]:
                if item["type"] == kind:
                    cases.append(case)
                    break
        assert len(cases) >= 10
        assert len({case["variant"] for case in cases}) >= 3
    for case in extraction:
        for item in case["expected"]:
            assert case["text"][item["start"] : item["end"]] == item["raw"]
    sentiment = load_sentiment_cases()
    assert len(sentiment) >= 100
    assert len({case["id"] for case in sentiment}) == len(sentiment)
    for case in sentiment:
        assert case["label"] in ("positive", "negative", "neutral")


def test_extraction_counts_normalization_mismatch_as_fp_and_fn():
    text = "a@b.co c@d.co"
    gold = [asdict(item) for item in extract_information(text).items]
    gold[1]["normalized"] = "other@d.co"
    result = evaluate_extraction([{"id": "one", "text": text, "expected": gold}])
    assert result["per_type"]["email"] == {
        "tp": 1,
        "fp": 1,
        "fn": 1,
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
    }
    assert {error["kind"] for error in result["errors"]} == {"fp", "fn"}


def test_sentiment_known_confusion_including_neutral_error():
    texts = ["좋다", "좋아요", "나쁘다", "좋다", "나쁘다", "오늘은 수요일이다"]
    cases = []
    for index, text in enumerate(texts):
        if index < 3:
            label = "positive"
        else:
            label = "negative"
        cases.append({"id": str(index), "text": text, "label": label})
    result = evaluate_sentiment(cases)
    assert result["accuracy"] == 0.5
    assert result["macro_f1"] == pytest.approx(0.533333, abs=1e-6)
    assert result["confusion_matrix"]["negative"]["neutral"] == 1
    assert len(result["errors"]) == 3
    # 중립 정답이 있는 데이터에서는 중립 F1도 평균에 포함한다.
    neutral = [{"id": "n", "text": "오늘은 수요일이다", "label": "neutral"}]
    assert evaluate_sentiment(neutral)["macro_f1"] == 1


def test_empty_evaluation_has_no_division_by_zero():
    assert evaluate_extraction([])["micro"]["f1"] == 0
    assert evaluate_sentiment([])["accuracy"] == 0
    assert evaluate_sentiment([])["macro_f1"] == 0


def test_modifier_comparison_uses_same_sentences():
    cases = [{"id": "one", "text": "정말 좋지 않아요", "label": "negative"}]
    result = compare_sentiment(cases)
    assert result["without_modifiers"]["accuracy"] == 0
    assert result["with_modifiers"]["accuracy"] == 1
    assert result["delta"]["accuracy"] == 1


def test_full_fixture_evaluation():
    extraction = evaluate_extraction(load_extraction_cases())
    sentiment = compare_sentiment(load_sentiment_cases())
    assert extraction["micro"]["recall"] > 0.8
    assert sentiment["with_modifiers"]["accuracy"] >= 0.8
    assert sentiment["delta"]["accuracy"] > 0
    # 실패를 일부러 만들지는 않는다. 오류 보고 항목이 실제 오분류인지 확인한다.
    for error in sentiment["with_modifiers"]["errors"]:
        assert error["expected"] != error["predicted"]
