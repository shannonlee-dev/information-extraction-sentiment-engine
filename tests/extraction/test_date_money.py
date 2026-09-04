import pytest

from sentiment_engine.extraction import _extract_dates, _extract_money
from sentiment_engine.models import MoneyValue


DATE_CASES = [
    ("2024년 1월 15일", "2024-01-15"),
    ("2024/01/15", "2024-01-15"),
    ("2024-01-15", "2024-01-15"),
    ("2024년 2월 29일", "2024-02-29"),
]

MONEY_CASES = [
    ("10,000원", MoneyValue(10_000, "KRW")),
    ("12000원", MoneyValue(12_000, "KRW")),
    ("1억 2천만원", MoneyValue(120_000_000, "KRW")),
    ("3억 5천만 2만원", MoneyValue(350_020_000, "KRW")),
    ("$100", MoneyValue(100, "USD")),
]


@pytest.mark.parametrize(("raw", "normalized"), DATE_CASES)
def test_extract_dates_normalizes_calendar_dates_and_preserves_offsets(raw, normalized):
    text = f"date: {raw}."

    items, diagnostics = _extract_dates(text)

    assert diagnostics == []
    assert len(items) == 1
    item = items[0]
    assert item.type == "date"
    assert item.raw == raw
    assert item.normalized == normalized
    assert text[item.start : item.end] == raw


@pytest.mark.parametrize("raw", ["2023-02-29", "2024-02-30", "2024/13/01"])
def test_extract_dates_reports_invalid_calendar_candidates(raw):
    text = f"date: {raw}."

    items, diagnostics = _extract_dates(text)

    assert items == []
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.type == "date"
    assert diagnostic.raw == raw
    assert diagnostic.reason == "invalid_calendar_date"
    assert text[diagnostic.start : diagnostic.end] == raw


def test_extract_dates_ignores_incomplete_korean_date():
    items, diagnostics = _extract_dates("date: 2024년 1월")

    assert items == []
    assert diagnostics == []


@pytest.mark.parametrize("text", ["2024-02-29-30", "2024/01/15/16"])
def test_extract_dates_does_not_match_a_prefix_of_a_continued_date_sequence(text):
    items, diagnostics = _extract_dates(text)

    assert items == []
    assert diagnostics == []


@pytest.mark.parametrize(("raw", "normalized"), MONEY_CASES)
def test_extract_money_normalizes_values_and_preserves_offsets(raw, normalized):
    text = f"amount: {raw}."

    items, diagnostics = _extract_money(text)

    assert diagnostics == []
    assert len(items) == 1
    item = items[0]
    assert item.type == "money"
    assert item.raw == raw
    assert item.normalized == normalized
    assert text[item.start : item.end] == raw


@pytest.mark.parametrize(("raw", "reason"), [
    ("1,00원", "invalid_money_number"),
    ("2만 1억원", "invalid_money_unit_order"),
    ("1억 2억 원", "invalid_money_unit_order"),
    ("$10.50", "invalid_money_number"),
])
def test_extract_money_reports_invalid_candidates(raw, reason):
    text = f"amount: {raw}."

    items, diagnostics = _extract_money(text)

    assert items == []
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.type == "money"
    assert diagnostic.raw == raw
    assert diagnostic.reason == reason
    assert text[diagnostic.start : diagnostic.end] == raw


@pytest.mark.parametrize("text", ["100", "원"])
def test_extract_money_ignores_text_without_a_money_candidate(text):
    items, diagnostics = _extract_money(text)

    assert items == []
    assert diagnostics == []
