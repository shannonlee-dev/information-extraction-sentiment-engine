"""Finite Korean surface expansion, not a general morphological analyzer.

Only complete generated words match. Explicit lexicon spellings take priority;
irregular conversational stems come from the lexicon's existing variants.
"""

from functools import lru_cache


# Whitelists bound expansion: an arbitrary suffix must never license a substring.
_PARTICLES = "이 가 은 는 을 를 의 에 에서 에게 도 만 으로 로 과 와 보다 에는 에도 은요 는요".split()
_ENDINGS = "다 고 지 지는 지만 지도 게 네 네요 니까 더라 더라고요 던 다고 다고만 다는 다니 군요 거든요 죠 는".split()
_PAST_ENDINGS = _ENDINGS + "어 어요 습니다 는데 던 었다".split()


def _jong(word: str) -> int:
    return (ord(word[-1]) - 0xAC00) % 28


def _with_jong(word: str, jong: int) -> str:
    return word[:-1] + chr(ord(word[-1]) - _jong(word) + jong)


@lru_cache(maxsize=4096)
def word_forms(word: str, *, conversational: bool = False) -> frozenset[str]:
    """Expand a dictionary word or a supplied conversational surface finitely."""
    forms = {word}
    if not word or not all("가" <= char <= "힣" for char in word):
        return frozenset(forms)

    if word.endswith("다") and len(word) > 1:
        stem = word[:-1]
        forms.update(stem + ending for ending in _ENDINGS)
        if _jong(stem):
            forms.update(stem + ending for ending in ("은", "을", "으면", "습니다", "는다", "는데", "은데", "은데요"))
        else:
            forms.update((_with_jong(stem, 4), _with_jong(stem, 8),
                          _with_jong(stem, 4) + "다", _with_jong(stem, 17) + "니다",
                          stem + "는", stem + "는데", stem + "면"))
        # Explicit regular contractions; other irregular stems are supplied as variants.
        if stem.endswith("하"):
            contracted = {stem[:-1] + "해", stem + "여"}
        elif stem.endswith("되"):
            contracted = {stem[:-1] + "돼", stem + "어"}
        elif _jong(stem):
            vowel = ((ord(stem[-1]) - 0xAC00) // 28) % 21
            contracted = {stem + ("아" if vowel in (0, 8) else "어")}
        else:
            contracted = set()
        for surface in contracted:
            forms.update(word_forms(surface, conversational=True))
        # Past stems (했다/않았다) still need polite past endings, not another tense.
        if _jong(stem) == 20:
            forms.update(stem + ending for ending in _PAST_ENDINGS)
    else:
        # Noun particles and copula endings, including 최고네요/고장이에요.
        forms.update(word + particle for particle in _PARTICLES)
        forms.update(word + ending for ending in
                     ("이다", "입니다", "이에요", "예요", "네요", "이네요", "이었다", "이었어요", "이지만"))
        # Only supplied conversational variants can inflect this way. A noun
        # such as 피해 must not generate the unrelated verb 피했다 (avoided).
        base = word[:-1] if word.endswith("요") else word
        if conversational and base.endswith(("아", "어", "해", "워", "돼", "려", "뻐", "빠", "라", "나", "져", "차", "퍼", "셔", "여")):
            forms.add(base + "요")
            past = _with_jong(base, 20)
            forms.update(past + ending for ending in _PAST_ENDINGS)
    return frozenset(forms)
