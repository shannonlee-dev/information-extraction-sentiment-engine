from dataclasses import asdict

from sentiment_engine.models import (
    AnalysisResult,
    Diagnostic,
    ExtractionItem,
    ExtractionResult,
    MoneyValue,
    SentimentMatch,
    SentimentResult,
)


def test_money_extraction_item_serializes() -> None:
    item = ExtractionItem(
        type="money",
        raw="10,000원",
        normalized=MoneyValue(amount=10_000, currency="KRW"),
        start=4,
        end=11,
    )
    assert asdict(item)["normalized"] == {"amount": 10_000, "currency": "KRW"}


def test_extraction_result_preserves_nested_dataclass_equality_and_offsets() -> None:
    item = ExtractionItem("email", "a@b.co", "a@b.co", 0, 6)
    diagnostic = Diagnostic("phone", "123", 7, 10, "invalid phone")
    result = ExtractionResult([item], [diagnostic])
    assert result == ExtractionResult([item], [diagnostic])
    assert result.items[0].start == 0
    assert result.items[0].end == 6


def test_sentiment_and_analysis_results_construct_and_serialize() -> None:
    match = SentimentMatch("great", "great!", 2, 1.5, 0, 3.0, 0, 6)
    sentiment = SentimentResult(3.0, "positive", False, ["great"], [match])
    analysis = AnalysisResult("great!", [], sentiment, [])
    assert analysis == AnalysisResult("great!", [], sentiment, [])
    assert asdict(analysis)["sentiment"]["matches"][0]["contribution"] == 3.0

