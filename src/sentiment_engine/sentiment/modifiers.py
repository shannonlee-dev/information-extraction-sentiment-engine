"""인접 강조어와 부정어에 따른 배율 및 반전 횟수 계산."""
import json

from sentiment_engine.data import LEXICONS

MODIFIERS = json.loads(LEXICONS.joinpath("modifiers.json").read_text(encoding="utf-8"))


def modifier_effect(tokens: list[str], start: int, end: int) -> tuple[float, int]:
    multiplier = 1.0
    negations = 0
    # 감성 표현 바로 앞의 강조어/안/못에만 적용한다.
    before = start - 1
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

    return multiplier, negations
