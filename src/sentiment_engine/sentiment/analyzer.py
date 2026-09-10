"""감성 표현 순회, 기여 점수 합산 및 결과 생성."""
from sentiment_engine.models import SentimentMatch, SentimentResult

from .lexicon import find_match
from .modifiers import modifier_effect
from .tokenization import tokenize


def analyze_sentiment(text: str, apply_modifiers: bool = True) -> SentimentResult:
    if not isinstance(text, str):
        raise TypeError('text must be a string')
    if not text.strip():
        raise ValueError('text must not be blank')

    tokens = tokenize(text)
    matches = []
    index = 0
    while index < len(tokens):
        entry, end = find_match(tokens, index)
        if entry is None:
            index = end
            continue

        multiplier, negations = modifier_effect(tokens, index, end) if apply_modifiers else (1.0, 0)

        base_score = entry['score']
        contribution = base_score * multiplier * (-1) ** negations
        matches.append(SentimentMatch(
            term=entry['term'], raw=' '.join(tokens[index:end]), base_score=base_score,
            emphasis_multiplier=multiplier, negation_count=negations,
            contribution=contribution,
        ))
        index = end

    score = round(sum(match.contribution for match in matches), 6)
    label = 'positive' if score > 0 else 'negative' if score < 0 else 'neutral'
    return SentimentResult(score, label, tokens, matches)
