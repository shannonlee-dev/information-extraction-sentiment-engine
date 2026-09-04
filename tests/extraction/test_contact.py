import pytest

from sentiment_engine.extraction import _extract_emails, _extract_phones


EMAIL_CASES = [
    ("user@domain.com", "user@domain.com"),
    ("User.Name@Sub.Domain.CO.KR", "User.Name@sub.domain.co.kr"),
    ("user+tag@example.org", "user+tag@example.org"),
]

PHONE_CASES = [
    ("010-1234-5678", "010-1234-5678"),
    ("010 1234 5678", "010-1234-5678"),
    ("01012345678", "010-1234-5678"),
    ("02-123-4567", "02-123-4567"),
    ("031-1234-5678", "031-1234-5678"),
]


@pytest.mark.parametrize(("raw", "normalized"), EMAIL_CASES)
def test_extract_emails_normalizes_domain_and_preserves_offsets(raw, normalized):
    text = f"contact: {raw}."

    items, diagnostics = _extract_emails(text)

    assert diagnostics == []
    assert len(items) == 1
    item = items[0]
    assert item.type == "email"
    assert item.raw == raw
    assert item.normalized == normalized
    assert text[item.start : item.end] == raw


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("user@localhost", "invalid_email_domain"),
        ("user..name@example.com", "invalid_email_local"),
        ("user@example.com..invalid", "invalid_email_domain"),
        ("user@example.com.-invalid", "invalid_email_domain"),
    ],
)
def test_extract_emails_rejects_invalid_candidates(raw, reason):
    text = f"contact: {raw}."

    items, diagnostics = _extract_emails(text)

    assert items == []
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.type == "email"
    assert diagnostic.raw == raw
    assert diagnostic.reason == reason
    assert text[diagnostic.start : diagnostic.end] == raw


@pytest.mark.parametrize(("raw", "normalized"), PHONE_CASES)
def test_extract_phones_normalizes_and_preserves_offsets(raw, normalized):
    text = f"call {raw} now"

    items, diagnostics = _extract_phones(text)

    assert diagnostics == []
    assert len(items) == 1
    item = items[0]
    assert item.type == "phone"
    assert item.raw == raw
    assert item.normalized == normalized
    assert text[item.start : item.end] == raw


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ("010-12-5678", "invalid_phone_format"),
        ("070-1234-5678", "invalid_phone_prefix"),
        ("010-1234 5678", "invalid_phone_format"),
    ],
)
def test_extract_phones_rejects_invalid_candidates(raw, reason):
    text = f"call {raw} now"

    items, diagnostics = _extract_phones(text)

    assert items == []
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.type == "phone"
    assert diagnostic.raw == raw
    assert diagnostic.reason == reason
    assert text[diagnostic.start : diagnostic.end] == raw


def test_extract_phones_rejects_digits_embedded_in_a_longer_sequence():
    items, diagnostics = _extract_phones("call 9010123456789 now")

    assert items == []
    assert diagnostics == []


def test_extract_phones_prefers_two_digit_area_code_without_separator():
    items, diagnostics = _extract_phones("call 021234567 now")

    assert diagnostics == []
    assert len(items) == 1
    item = items[0]
    assert item.raw == "021234567"
    assert item.normalized == "02-123-4567"
