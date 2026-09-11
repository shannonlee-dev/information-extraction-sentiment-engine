"""기존 정답 데이터로 추출과 정규화를 확인한다."""

from dataclasses import asdict

import pytest

from sentiment_engine.extraction import extract_information
from sentiment_engine.evaluation import load_extraction_cases

CASES = load_extraction_cases()
SUPPORTED_CASES = [case for case in CASES if case["variant"] != "challenge-unsupported"]


@pytest.mark.parametrize("case", SUPPORTED_CASES, ids=lambda case: case["id"])
def test_supported_fixture(case):
    result = extract_information(case["text"])
    assert [asdict(item) for item in result.items] == case["expected"]
    for item in result.items:
        assert case["text"][item.start : item.end] == item.raw


@pytest.mark.parametrize(
    "text",
    [
        "user..name@example.com",
        "user@localhost",
        "user@example.com..invalid",
        "010-12-5678",
        "010-1234 5678",
        "9010123456789",
        "2023-02-29",
        "2024/13/01",
        "2024-02-29-30",
        "1,00원",
        "2만 1억원",
        "$10.50",
        "https:///path",
    ],
)
def test_invalid_candidates_are_not_returned(text):
    assert extract_information(text).items == []


def test_all_five_types_and_normalized_values():
    text = "User@Example.COM 01012345678 2024년 1월 15일 1억 2천만원 HTTP://Example.COM/a?q=1"
    items = [asdict(item) for item in extract_information(text).items]
    assert [item["type"] for item in items] == [
        "email",
        "phone",
        "date",
        "money",
        "url",
    ]
    assert [item["normalized"] for item in items] == [
        "User@example.com",
        "010-1234-5678",
        "2024-01-15",
        {"amount": 120000000, "currency": "KRW"},
        "http://example.com/a?q=1",
    ]


@pytest.mark.parametrize("text", ["", " \n"])
def test_blank_input(text):
    with pytest.raises(ValueError):
        extract_information(text)
