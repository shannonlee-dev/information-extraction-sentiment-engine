"""분리된 처리 단계의 계약과 공개 API 경계를 검증한다."""
import pytest

from sentiment_engine import analyze_sentiment, analyze_text, extract_information
from sentiment_engine.sentiment.lexicon import find_match
from sentiment_engine.sentiment.modifiers import modifier_effect
from sentiment_engine.sentiment.tokenization import tokenize


@pytest.mark.parametrize('analyze', [extract_information, analyze_sentiment, analyze_text])
@pytest.mark.parametrize('text', [None, 123, [], ' \n'])
def test_public_input_validation(analyze, text):
    error = ValueError if isinstance(text, str) else TypeError
    message = 'text must not be blank' if error is ValueError else 'text must be a string'
    with pytest.raises(error, match=message):
        analyze(text)


def test_pipeline_orders_items_and_diagnostics_by_source_position():
    text = 'https://example.com/a a@b.co 2023-02-29 1,00원 010-12-5678 user@localhost'
    result = extract_information(text)
    assert [item.type for item in result.items] == ['url', 'email']
    assert [(d.type, d.reason) for d in result.diagnostics] == [
        ('date', 'invalid_calendar_date'),
        ('money', 'invalid_money_number'),
        ('phone', 'invalid_phone_format'),
        ('email', 'invalid_email_domain'),
    ]
    for records in (result.items, result.diagnostics):
        assert [r.start for r in records] == sorted(r.start for r in records)
        assert all(text[r.start:r.end] == r.raw for r in records)


def test_longest_expression_consumes_tokens_without_double_counting():
    tokens = tokenize('문제가 해결되었다')
    entry, end = find_match(tokens, 0)
    assert entry['term'] == '문제가 해결되다'
    assert end == len(tokens)
    result = analyze_sentiment('문제가 해결되었다')
    assert len(result.matches) == 1
    assert result.score == 2
    assert result.matches[0].raw == '문제가 해결되었다'


@pytest.mark.parametrize('text, expected', [
    ('정말 매우 좋지 않은 것은 아니다', (2.25, 2)),
    ('안\n좋지 않다', (1.0, 1)),
    ('정말. 좋지 않다', (1.0, 1)),
    ('정말 좋지. 않다', (1.5, 0)),
])
def test_modifier_scope_uses_token_boundaries(text, expected):
    tokens = tokenize(text)
    start = tokens.index('좋지')
    assert modifier_effect(tokens, start, start + 1) == expected


def test_unknown_expression_advances_without_partial_matching():
    assert find_match(tokenize('만족도조사'), 0) == (None, 1)
