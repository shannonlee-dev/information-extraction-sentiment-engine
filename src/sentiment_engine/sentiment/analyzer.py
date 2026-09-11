"""감성 표현 순회, 기여 점수 합산 및 결과 생성."""

from sentiment_engine.models import SentimentMatch, SentimentResult

from .lexicon import find_match
from .modifiers import modifier_effect
from .tokenization import tokenize


def analyze_sentiment(text: str, apply_modifiers: bool = True) -> SentimentResult:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text.strip():
        raise ValueError("text must not be blank")

    tokens = tokenize(text)
    matches = []
    index = 0
    while index < len(tokens):
        entry, end = find_match(tokens, index)
        if entry is None:
            index = end
            continue

        multiplier = 1.0
        negations = 0
        if apply_modifiers:
            multiplier, negations = modifier_effect(tokens, index, end)

        base_score = entry["score"]
        contribution = base_score * multiplier
        # 부정이 홀수 번이면 반전하고, 짝수 번이면 원래 부호를 유지한다.
        if negations % 2 == 1:
            contribution = -contribution
        matches.append(
            SentimentMatch(
                term=entry["term"],
                raw=" ".join(tokens[index:end]),
                base_score=base_score,
                emphasis_multiplier=multiplier,
                negation_count=negations,
                contribution=contribution,
            )
        )
        index = end

    score = round(sum(match.contribution for match in matches), 6)
    if score > 0:
        label = "positive"
    elif score < 0:
        label = "negative"
    else:
        label = "neutral"
    return SentimentResult(score, label, tokens, matches)
