import pytest

from sentiment_engine import extract_information
from sentiment_engine.extraction import _extract_urls
from sentiment_engine.models import ExtractionItem, MoneyValue


URL_CASES = [
    ("https://www.example.com", "https://www.example.com"),
    ("HTTP://Example.COM/path", "http://example.com/path"),
    (
        "https://www.example.com/path?query=value#part",
        "https://www.example.com/path?query=value#part",
    ),
]


@pytest.mark.parametrize(("raw", "normalized"), URL_CASES)
def test_extract_urls_normalizes_scheme_host_and_preserves_offsets(raw, normalized):
    text = f"visit {raw} today"

    items, diagnostics = _extract_urls(text)

    assert diagnostics == []
    assert len(items) == 1
    item = items[0]
    assert item.raw == raw
    assert item.normalized == normalized
    assert text[item.start : item.end] == raw


@pytest.mark.parametrize(
    "text",
    [
        "visit <https://www.example.com/path> today",
        "visit (https://www.example.com/path) today",
        "visit https://www.example.com/path.,!? today",
    ],
)
def test_extract_urls_excludes_unmatched_wrappers_and_terminal_punctuation(text):
    items, diagnostics = _extract_urls(text)

    assert diagnostics == []
    assert len(items) == 1
    assert items[0].raw == "https://www.example.com/path"
    assert text[items[0].start : items[0].end] == items[0].raw


def test_extract_urls_keeps_query_punctuation():
    items, diagnostics = _extract_urls("visit https://example.com/?a=one,two&b=ok.")

    assert diagnostics == []
    assert [item.raw for item in items] == ["https://example.com/?a=one,two&b=ok"]


@pytest.mark.parametrize("text", ["ftp://example.com", "https://"])
def test_extract_urls_ignores_unsupported_or_empty_candidates(text):
    items, diagnostics = _extract_urls(text)

    assert items == []
    assert diagnostics == []


def test_extract_urls_reports_a_missing_host():
    items, diagnostics = _extract_urls("visit https:///path")

    assert items == []
    assert [(diagnostic.raw, diagnostic.reason) for diagnostic in diagnostics] == [
        ("https:///path", "missing_url_host")
    ]


def test_extract_information_returns_all_types_in_text_order():
    text = (
        "https://Example.COM/a 010 1234 5678 2024-02-29 "
        "10,000원 User@Example.COM"
    )

    result = extract_information(text)

    assert [item.type for item in result.items] == ["url", "phone", "date", "money", "email"]
    assert [item.normalized for item in result.items] == [
        "https://example.com/a",
        "010-1234-5678",
        "2024-02-29",
        MoneyValue(10_000, "KRW"),
        "User@example.com",
    ]
    assert result.diagnostics == []


def test_extract_information_deduplicates_identical_candidates(monkeypatch):
    duplicate = ExtractionItem("email", "a@b.co", "a@b.co", 0, 6)
    monkeypatch.setattr(
        "sentiment_engine.extraction._extract_emails", lambda text: ([duplicate, duplicate], [])
    )

    result = extract_information("a@b.co")

    assert result.items == [duplicate]


@pytest.mark.parametrize("text", [None, 1, []])
def test_extract_information_rejects_non_string_input(text):
    with pytest.raises(TypeError):
        extract_information(text)


@pytest.mark.parametrize("text", ["", " \t\n"])
def test_extract_information_rejects_blank_input(text):
    with pytest.raises(ValueError):
        extract_information(text)
