"""감성 사전 로딩, 제한된 활용 확장 및 가장 긴 표현 매칭."""

import json

from sentiment_engine.data import LEXICONS

from .tokenization import tokenize


def _load_lexicon() -> dict:
    entries = json.loads(
        LEXICONS.joinpath("sentiment_lexicon.json").read_text(encoding="utf-8")
    )
    lookup = {}
    for entry in entries:
        term = entry["term"]
        forms = [term]
        forms.extend(entry["variants"])
        # 사전에 없는 모든 활용을 추측하지 않고, 몇 가지 흔한 어미만 지원한다.
        if term.endswith("다"):
            stem = term[:-1]
            for ending in ("고", "지", "지만", "네요", "았다", "었다", "은", "는"):
                forms.append(stem + ending)
        if term.endswith("하다"):
            stem = term[:-2]
            for ending in ("해", "해요", "했다", "했어요", "한다", "합니다"):
                forms.append(stem + ending)
        if not term.endswith("다"):
            for particle in (
                "이",
                "가",
                "은",
                "는",
                "을",
                "를",
                "도",
                "이다",
                "입니다",
            ):
                forms.append(term + particle)
        for form in forms:
            # 긴 표현을 하나로 매칭하므로 '문제가 해결되었다'의 '문제'를 중복 가산하지 않는다.
            lookup.setdefault(tuple(tokenize(form)), entry)
    return lookup


LEXICON = _load_lexicon()
MAX_WORDS = max(len(words) for words in LEXICON)


def find_match(tokens: list[str], start: int) -> tuple[dict | None, int]:
    # 같은 위치에서는 가장 긴 등록 표현부터 검사한다. 단어 내부 부분 문자열은 매칭하지 않는다.
    end = min(len(tokens), start + MAX_WORDS)
    while end > start:
        candidate = tuple(tokens[start:end])
        entry = LEXICON.get(candidate)
        if entry:
            return entry, end
        end -= 1
    return None, start + 1
