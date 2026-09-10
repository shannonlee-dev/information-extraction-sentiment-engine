"""미션의 점수 계산과 사전 수량을 검증한다."""
import json

import pytest

from sentiment_engine.sentiment import analyze_sentiment
from sentiment_engine.data import LEXICONS


@pytest.mark.parametrize('text, score, label', [
    ('좋다', 2, 'positive'),
    ('나쁘다', -2, 'negative'),
    ('오늘은 수요일이다', 0, 'neutral'),
    ('정말 좋다', 3, 'positive'),
    ('안 좋다', -2, 'negative'),
    ('좋지 않다', -2, 'negative'),
    ('정말 좋지 않아요', -3, 'negative'),
    ('나쁘지 않다', 2, 'positive'),
    ('좋지 않은 것은 아니다', 2, 'positive'),
    ('불편하지 않은 것은 아니다', -2, 'negative'),
    ('불만이 없다', 2, 'positive'),
    ('안 좋다. 좋다', 0, 'neutral'),
    ('정말. 좋다', 2, 'positive'),
    ('안\n좋다', 2, 'positive'),
    ('좋다 좋다', 4, 'positive'),
    ('불친절하다', -2, 'negative'),
    ('만족도조사', 0, 'neutral'),
])
def test_scoring(text, score, label):
    result = analyze_sentiment(text)
    assert (result.score, result.label) == (score, label)


def test_modifiers_can_be_disabled_and_calculation_is_visible():
    text = '정말 좋지 않아요'
    result = analyze_sentiment(text)
    match = result.matches[0]
    assert result.tokens == ['정말', '좋지', '않아요']
    assert (match.base_score, match.emphasis_multiplier, match.negation_count) == (2, 1.5, 1)
    assert match.contribution == -3
    assert analyze_sentiment(text, apply_modifiers=False).score == 2
    assert analyze_sentiment('좋지 않은 것은 아니다').matches[0].negation_count == 2


def test_dictionary_has_required_words():
    lexicon = json.loads(LEXICONS.joinpath('sentiment_lexicon.json').read_text(encoding='utf-8'))
    assert len({entry['term'] for entry in lexicon}) >= 200
    assert sum(entry.get('domain') == 'customer_support' for entry in lexicon) >= 30
    assert all(entry['score'] in (-3, -2, -1, 1, 2, 3) for entry in lexicon)


@pytest.mark.parametrize('text', ['', ' \n'])
def test_blank_input(text):
    with pytest.raises(ValueError):
        analyze_sentiment(text)
