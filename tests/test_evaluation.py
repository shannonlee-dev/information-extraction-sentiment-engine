import json
from collections import Counter
from dataclasses import asdict

import pytest

from sentiment_engine import evaluation
from sentiment_engine.models import ExtractionItem, ExtractionResult, MoneyValue, SentimentResult


def extraction_cases():
    cases = []
    for kind in ("email", "phone", "date", "money", "url"):
        for index in range(10):
            normalized = {"amount": 100, "currency": "KRW"} if kind == "money" else "value"
            cases.append({"id": f"{kind}-{index}", "text": "value", "variant": f"form-{index % 3}",
                          "expected": [{"type": kind, "raw": "value", "normalized": normalized, "start": 0, "end": 5}]})
    return cases


def sentiment_cases():
    return [{"id": f"s-{i}", "text": "좋다" if i % 2 else "나쁘다",
             "label": "positive" if i % 2 else "negative",
             "features": ["emphasis", "single-negation", "double-negation", "mixed-polarity", "challenge"]}
            for i in range(100)]


def write_cases(tmp_path, cases):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps({"metadata": {"source": "manual"}, "cases": cases}), encoding="utf-8")
    return path


def test_loaders_preserve_order_and_return_cases_only(tmp_path):
    for loader, cases in [(evaluation.load_extraction_cases, extraction_cases()),
                          (evaluation.load_sentiment_cases, sentiment_cases())]:
        assert loader(write_cases(tmp_path, cases)) == cases


@pytest.mark.parametrize("field,value,rule", [
    ("start", True, "offset"), ("start", -1, "offset"), ("end", 6, "offset"),
    ("end", 0, "offset"), ("start", "0", "offset"), ("raw", "wrong", "raw"),
    ("type", "address", "type"), ("normalized", None, "normalized"),
    ("normalized", "", "normalized"), ("normalized", {}, "normalized"),
])
def test_extraction_loader_rejects_invalid_items(tmp_path, field, value, rule):
    cases = extraction_cases()
    cases[0]["expected"][0][field] = value
    with pytest.raises(ValueError, match=f"email-0.*{rule}"):
        evaluation.load_extraction_cases(write_cases(tmp_path, cases))


@pytest.mark.parametrize("normalized", [None, "100", {}, {"amount": True, "currency": "KRW"},
    {"amount": -1, "currency": "KRW"}, {"amount": 1.5, "currency": "KRW"},
    {"amount": 100, "currency": "EUR"}, {"amount": 100},
    {"amount": 100, "currency": "USD", "extra": 1}])
def test_extraction_loader_rejects_invalid_money(tmp_path, normalized):
    cases = extraction_cases()
    cases[30]["expected"][0]["normalized"] = normalized
    with pytest.raises(ValueError, match="money-0.*normalized"):
        evaluation.load_extraction_cases(write_cases(tmp_path, cases))


@pytest.mark.parametrize("factory,loader", [(extraction_cases, evaluation.load_extraction_cases),
                                            (sentiment_cases, evaluation.load_sentiment_cases)])
def test_loaders_reject_duplicate_ids(tmp_path, factory, loader):
    cases = factory()
    cases[1]["id"] = cases[0]["id"]
    with pytest.raises(ValueError, match=f"{cases[0]['id']}.*duplicate"):
        loader(write_cases(tmp_path, cases))


@pytest.mark.parametrize("value", [None, 1, {}, {"cases": {}}, [None]])
def test_loaders_reject_malformed_shapes(tmp_path, value):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(value))
    for loader in (evaluation.load_extraction_cases, evaluation.load_sentiment_cases):
        with pytest.raises(ValueError):
            loader(path)


@pytest.mark.parametrize("field,value", [("id", ""), ("text", None), ("text", " "),
    ("expected", None), ("expected", [None]), ("variant", ""), ("variant", [])])
def test_extraction_loader_rejects_bad_case_shapes(tmp_path, field, value):
    cases = extraction_cases()
    cases[0][field] = value
    with pytest.raises(ValueError, match=field):
        evaluation.load_extraction_cases(write_cases(tmp_path, cases))


def test_extraction_loader_requires_total_type_and_variant_counts(tmp_path):
    cases = extraction_cases()
    with pytest.raises(ValueError, match="50"):
        evaluation.load_extraction_cases(write_cases(tmp_path, cases[:-1]))
    cases[0]["expected"] = []
    with pytest.raises(ValueError, match="email.*10"):
        evaluation.load_extraction_cases(write_cases(tmp_path, cases))
    cases = extraction_cases()
    for case in cases:
        case["variant"] = "one"
    with pytest.raises(ValueError, match="email.*three"):
        evaluation.load_extraction_cases(write_cases(tmp_path, cases))


@pytest.mark.parametrize("field,value", [("label", "neutral"), ("label", []),
    ("features", "emphasis"), ("features", [None]), ("text", ""), ("id", None)])
def test_sentiment_loader_rejects_bad_cases(tmp_path, field, value):
    cases = sentiment_cases()
    cases[0][field] = value
    with pytest.raises(ValueError, match=field):
        evaluation.load_sentiment_cases(write_cases(tmp_path, cases))


def test_sentiment_loader_enforces_size_balance_and_feature_quotas(tmp_path):
    cases = sentiment_cases()
    with pytest.raises(ValueError, match="100"):
        evaluation.load_sentiment_cases(write_cases(tmp_path, cases[:-1]))
    cases[0]["label"] = "positive"
    with pytest.raises(ValueError, match="balanced"):
        evaluation.load_sentiment_cases(write_cases(tmp_path, cases))
    for feature in ("emphasis", "single-negation", "double-negation", "mixed-polarity", "challenge"):
        cases = sentiment_cases()
        for case in cases:
            case["features"].remove(feature)
        with pytest.raises(ValueError, match=feature):
            evaluation.load_sentiment_cases(write_cases(tmp_path, cases))


def gold_case(case_id, items):
    return {"id": case_id, "text": case_id, "expected": [asdict(item) for item in items]}


def test_extraction_known_counts_and_per_type_zero_denominators(monkeypatch):
    a = ExtractionItem("email", "a@b.co", "a@b.co", 0, 6)
    b = ExtractionItem("phone", "01012345678", "010-1234-5678", 7, 18)
    c = ExtractionItem("date", "2024/01/15", "2024-01-15", 19, 29)
    extra = ExtractionItem("url", "https://x.co", "https://x.co", 30, 42)
    monkeypatch.setattr(evaluation, "extract_information", lambda text: ExtractionResult([a, b, extra], []))
    result = evaluation.evaluate_extraction([gold_case("case-1", [a, b, c])])
    assert result["micro"] == {"tp": 2, "fp": 1, "fn": 1, "precision": 0.666667, "recall": 0.666667, "f1": 0.666667}
    assert list(result["per_type"]) == ["email", "phone", "date", "money", "url"]
    assert result["per_type"]["email"]["f1"] == 1.0
    assert result["per_type"]["date"]["fn"] == 1
    assert result["per_type"]["url"]["fp"] == 1
    assert result["per_type"]["money"] == {"tp": 0, "fp": 0, "fn": 0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    assert [error["kind"] for error in result["errors"]] == ["fn", "fp"]


@pytest.mark.parametrize("change", [{"type": "url"}, {"start": 1}, {"end": 7}, {"normalized": "other@b.co"}])
def test_extraction_exact_match_requires_type_both_offsets_and_normalization(monkeypatch, change):
    gold = ExtractionItem("email", "a@b.co", "a@b.co", 0, 6)
    predicted = ExtractionItem(**(asdict(gold) | change))
    monkeypatch.setattr(evaluation, "extract_information", lambda text: ExtractionResult([predicted], []))
    result = evaluation.evaluate_extraction([gold_case("case-1", [gold])])
    assert (result["micro"]["tp"], result["micro"]["fp"], result["micro"]["fn"]) == (0, 1, 1)
    if "normalized" in change:
        assert [error["kind"] for error in result["errors"]] == ["fn", "fp", "normalization_mismatch"]
        assert result["errors"][-1]["expected"]["normalized"] == "a@b.co"
        assert result["errors"][-1]["predicted"]["normalized"] == "other@b.co"
    assert all(error["case_id"] == "case-1" for error in result["errors"])
    assert result == evaluation.evaluate_extraction([gold_case("case-1", [gold])])


def test_extraction_matches_are_scoped_to_case_id(monkeypatch):
    item = ExtractionItem("email", "a@b.co", "a@b.co", 0, 6)
    monkeypatch.setattr(evaluation, "extract_information", lambda text: ExtractionResult([] if text == "first" else [item], []))
    result = evaluation.evaluate_extraction([gold_case("first", [item]), gold_case("second", [])])
    assert (result["micro"]["tp"], result["micro"]["fp"], result["micro"]["fn"]) == (0, 1, 1)


def test_extraction_money_matches_by_amount_and_currency(monkeypatch):
    gold = ExtractionItem("money", "$100", MoneyValue(100, "USD"), 0, 4)
    monkeypatch.setattr(evaluation, "extract_information", lambda text: ExtractionResult([gold], []))
    assert evaluation.evaluate_extraction([gold_case("one", [gold])])["micro"]["tp"] == 1
    wrong = ExtractionItem("money", "$100", MoneyValue(100, "KRW"), 0, 4)
    monkeypatch.setattr(evaluation, "extract_information", lambda text: ExtractionResult([wrong], []))
    result = evaluation.evaluate_extraction([gold_case("one", [gold])])
    assert (result["micro"]["fp"], result["micro"]["fn"]) == (1, 1)


def test_sentiment_known_confusion_and_neutral_prediction(monkeypatch):
    predictions = ["positive", "positive", "negative", "positive", "negative", "neutral"]
    cases = [{"id": str(i), "text": str(i), "label": "positive" if i < 3 else "negative"} for i in range(6)]
    monkeypatch.setattr(evaluation, "analyze_sentiment", lambda text, apply_modifiers: SentimentResult(0.0, predictions[int(text)], False, [], []))
    result = evaluation.evaluate_sentiment(cases)
    assert result["accuracy"] == 0.5
    assert list(result["per_class"]) == ["positive", "negative", "neutral"]
    assert result["per_class"]["positive"]["precision"] == 0.666667
    assert result["per_class"]["positive"]["recall"] == 0.666667
    assert result["positive_f1"] == 0.666667
    assert result["per_class"]["negative"]["precision"] == 0.5
    assert result["per_class"]["negative"]["recall"] == 0.333333
    assert result["per_class"]["negative"]["f1"] == 0.4
    assert result["macro_f1"] == 0.533333
    assert result["per_class"]["neutral"]["f1"] == 0.0
    assert result["confusion_matrix"]["negative"] == {"positive": 1, "negative": 1, "neutral": 1}
    assert result["errors"][-1] == {"case_id": "5", "text": "5", "expected": "negative", "predicted": "neutral", "score": 0.0, "matches": []}


def test_sentiment_comparison_passes_modifiers_and_reports_numeric_deltas(monkeypatch):
    calls = []
    def analyze(text, apply_modifiers):
        calls.append(apply_modifiers)
        return SentimentResult(-1.0 if apply_modifiers else 1.0, "negative" if apply_modifiers else "positive", False, [], [])
    monkeypatch.setattr(evaluation, "analyze_sentiment", analyze)
    result = evaluation.compare_sentiment([{"id": "one", "text": "안 좋다", "label": "negative"}])
    assert calls == [False, True]
    assert result["without_modifiers"]["accuracy"] == 0.0
    assert result["with_modifiers"]["accuracy"] == 1.0
    assert result["delta"] == {"accuracy": 1.0, "macro_f1": 1.0, "positive_f1": 0.0}


def test_empty_evaluations_return_zero_metrics():
    assert evaluation.evaluate_extraction([])["micro"]["f1"] == 0.0
    result = evaluation.evaluate_sentiment([])
    assert (result["accuracy"], result["macro_f1"], result["positive_f1"]) == (0.0, 0.0, 0.0)


def test_fixed_datasets_have_required_coverage_and_honest_challenges():
    extraction = evaluation.load_extraction_cases()
    sentiment = evaluation.load_sentiment_cases()
    assert len(extraction) >= 50
    for kind in ("email", "phone", "date", "money", "url"):
        supported = [case for case in extraction if case["variant"] != "challenge-unsupported" and any(item["type"] == kind for item in case["expected"])]
        assert len(supported) >= 10
        assert len({case["variant"] for case in supported}) >= 3
    challenge_texts = {case["text"] for case in extraction if case["variant"] == "challenge-unsupported"}
    assert {"+82-10-1234-5678", "공일공-일이삼사-오육칠팔", "2024.01.15", "백만원", "USD 100", "www.example.com/path"} <= challenge_texts
    label_counts = Counter(case["label"] for case in sentiment)
    assert label_counts["positive"] == label_counts["negative"] >= 50
    sentiment_challenges = {case["text"] for case in sentiment if case["features"] == ["challenge"] and case["label"] == "negative"}
    assert {
        "참 잘도 처리했네요", "최고네요, 벌써 세 번째 고장이에요",
        "배송이 빛의 속도네요, 일주일밖에 안 걸렸어요", "웃음밖에 안 나와요",
        "칭찬할 말이 없네요", "다시 사고 싶지는 않아요", "이 정도면 괜찮다고 해야 하나요",
        "기대를 안 했는데 역시나네요", "돈이 아깝지 않을 수가 없어요", "설명과 다른데 우연이겠죠",
    } <= sentiment_challenges
    supported = [case for case in extraction if case["variant"] != "challenge-unsupported"]
    assert evaluation.evaluate_extraction(supported)["errors"] == []
    feature_counts = Counter(feature for case in sentiment for feature in case["features"])
    for feature, minimum in {"emphasis": 15, "single-negation": 15, "double-negation": 10, "mixed-polarity": 10, "challenge": 10}.items():
        assert feature_counts[feature] >= minimum
    assert len(evaluation.evaluate_extraction(extraction)["errors"]) >= 5
    assert len(evaluation.evaluate_sentiment(sentiment)["errors"]) >= 10
