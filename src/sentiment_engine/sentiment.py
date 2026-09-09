"""표기 사전과 가까운 수식어로 계산하는 교육용 감성 분석."""
import json
import re
from pathlib import Path

from sentiment_engine.models import SentimentMatch, SentimentResult

DATA = Path(__file__).resolve().parents[2] / 'data'
# 기존 토큰화 규칙: 한글/영문/숫자 어절과 문장부호를 분리한다.
# 줄바꿈도 남겨 두어 부정어·강조어가 다음 문장으로 넘어가지 않게 한다.
TOKEN_PATTERN = re.compile(r'[가-힣A-Za-z0-9]+|[^\w\s]|[\r\n]')


def _load_lexicon():
    entries = json.loads((DATA / 'sentiment_lexicon.json').read_text(encoding='utf-8'))
    lookup = {}
    for entry in entries:
        term = entry['term']
        forms = [term, *entry['variants']]
        # 사전에 없는 모든 활용을 추측하지 않고, 몇 가지 흔한 어미만 지원한다.
        if term.endswith('다'):
            forms += [term[:-1] + ending for ending in ('고', '지', '지만', '네요', '았다', '었다', '은', '는')]
        if term.endswith('하다'):
            forms += [term[:-2] + ending for ending in ('해', '해요', '했다', '했어요', '한다', '합니다')]
        if not term.endswith('다'):
            forms += [term + particle for particle in ('이', '가', '은', '는', '을', '를', '도', '이다', '입니다')]
        for form in forms:
            # 긴 표현을 하나로 매칭하므로 '문제가 해결되었다'의 '문제'를 중복 가산하지 않는다.
            lookup.setdefault(tuple(TOKEN_PATTERN.findall(form)), entry)
    return lookup


LEXICON = _load_lexicon()
MAX_WORDS = max(len(words) for words in LEXICON)
MODIFIERS = json.loads((DATA / 'modifiers.json').read_text(encoding='utf-8'))


def _find_match(tokens, start):
    # 같은 위치에서는 가장 긴 등록 표현부터 검사한다. 단어 내부 부분 문자열은 매칭하지 않는다.
    for end in range(min(len(tokens), start + MAX_WORDS), start, -1):
        entry = LEXICON.get(tuple(tokens[start:end]))
        if entry:
            return entry, end
    return None, start + 1


def analyze_sentiment(text: str, apply_modifiers: bool = True) -> SentimentResult:
    if not isinstance(text, str):
        raise TypeError('text must be a string')
    if not text.strip():
        raise ValueError('text must not be blank')

    tokens = TOKEN_PATTERN.findall(text)
    matches = []
    index = 0
    while index < len(tokens):
        entry, end = _find_match(tokens, index)
        if entry is None:
            index = end
            continue

        multiplier = 1.0
        negations = 0
        if apply_modifiers:
            # 감성 표현 바로 앞의 강조어/안/못에만 적용한다.
            before = index - 1
            while before >= 0:
                word = tokens[before]
                if word in MODIFIERS['emphasizers']:
                    multiplier *= MODIFIERS['emphasizers'][word]
                elif word in MODIFIERS['before_negations']:
                    negations += 1
                else:
                    break
                before -= 1

            # '좋지 않다', '불만이 없다'처럼 바로 뒤에 오는 부정어를 처리한다.
            if end < len(tokens) and tokens[end] in MODIFIERS['after_negations']:
                negations += 1
                # 대표 이중부정: '좋지 않은 것은 아니다' → 두 번 반전.
                if tokens[end] in ('않은', '않는') and tokens[end + 1:end + 3] == ['것은', '아니다']:
                    negations += 1

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
