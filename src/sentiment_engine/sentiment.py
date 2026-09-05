"""Validated sentiment resources and token-level matching primitives."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from sentiment_engine.models import SentimentMatch, SentimentResult
from sentiment_engine.korean import word_forms


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEXICON_PATH = _REPOSITORY_ROOT / "data" / "sentiment_lexicon.json"
DEFAULT_MODIFIERS_PATH = _REPOSITORY_ROOT / "data" / "modifiers.json"
# A maximal (+) Korean/Latin/digit run forms a word token; supported punctuation
# is kept as one-character alternatives so modifier scope stops at sentence boundaries.
_TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9]+|[.!?,;:]")
# The same word character class distinguishes words from boundary punctuation.
_WORD_PATTERN = re.compile(r"[가-힣A-Za-z0-9]+")
_VALID_SCORES = frozenset({-3, -2, -1, 1, 2, 3})
_CLAUSE_CONNECTORS = frozenset({"하지만", "그러나", "그런데", "그래도", "반면", "그리고"})
# Nominalization/modal bridges license an auxiliary chain, not arbitrary distance.
_NEGATION_BRIDGE = re.compile(r"(?:것[은이는도]?|이유[가는]?|수[가는]?|할 수[가는]?)?")


@dataclass(frozen=True, slots=True)
class _LexiconEntry:
    term: str
    score: int
    domain: str | None
    source: str = "project"


@dataclass(frozen=True, slots=True)
class _ModifierEntry:
    term: str
    multiplier: float | None = None


@dataclass(frozen=True, slots=True)
class _Token:
    raw: str
    start: int
    end: int
    is_boundary: bool
    source: str | None = None

    @property
    def text(self) -> str:
        return self.raw


@dataclass(frozen=True, slots=True)
class _SentimentTokenMatch:
    entry: _LexiconEntry
    raw: str
    start: int
    end: int
    token_start: int
    token_end: int


@dataclass(frozen=True, slots=True)
class _ModifierTokenMatch:
    entry: _ModifierEntry
    token_start: int
    token_end: int


def _load_lexicon(path: Path) -> Mapping[str, _LexiconEntry]:
    """Load a validated lexicon, indexed by each canonical term and variant."""
    with Path(path).open(encoding="utf-8") as resource:
        raw_entries = json.load(resource)
    if not isinstance(raw_entries, list):
        raise ValueError("invalid sentiment lexicon")

    terms: set[str] = set()
    surfaces: dict[str, _LexiconEntry] = {}
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict) or set(raw_entry) - {
            "term", "variants", "score", "domain", "source"
        }:
            raise ValueError("invalid sentiment entry")
        term = raw_entry.get("term")
        variants = raw_entry.get("variants")
        score = raw_entry.get("score")
        source = raw_entry.get("source")
        domain = raw_entry.get("domain")
        if not isinstance(term, str) or not term or not isinstance(variants, list):
            raise ValueError("invalid sentiment entry")
        if not isinstance(source, str) or not source or (
            domain is not None and (not isinstance(domain, str) or not domain)
        ):
            raise ValueError("invalid sentiment entry")
        if not isinstance(score, int) or isinstance(score, bool) or score not in _VALID_SCORES:
            raise ValueError("invalid sentiment score")
        if any(not isinstance(variant, str) or not variant for variant in variants):
            raise ValueError("invalid sentiment entry")
        if term in terms:
            raise ValueError("duplicate sentiment term")
        terms.add(term)
        entry = _LexiconEntry(term, score, domain, source)
        for surface in (term, *variants):
            previous = surfaces.get(surface)
            if previous is not None and previous.term != term:
                raise ValueError("conflicting sentiment surface")
            surfaces[surface] = entry

    if len(terms) < 200:
        raise ValueError("sentiment lexicon requires at least 200 terms")
    if sum(entry.domain == "customer_support" for entry in {value.term: value for value in surfaces.values()}.values()) < 30:
        raise ValueError("sentiment lexicon requires at least 30 domain terms")
    return MappingProxyType(surfaces)


def _load_modifiers(path: Path) -> Mapping[str, Mapping[str, _ModifierEntry]]:
    """Load validated negation and emphasis lookup maps without mutability leaks."""
    with Path(path).open(encoding="utf-8") as resource:
        raw_modifiers = json.load(resource)
    if not isinstance(raw_modifiers, dict) or set(raw_modifiers) != {"negations", "emphasizers"}:
        raise ValueError("invalid modifiers")

    lookups: dict[str, Mapping[str, _ModifierEntry]] = {}
    seen_surfaces: set[str] = set()
    for group in ("negations", "emphasizers"):
        raw_entries = raw_modifiers[group]
        if not isinstance(raw_entries, list):
            raise ValueError("invalid modifiers")
        surfaces: dict[str, _ModifierEntry] = {}
        for raw_entry in raw_entries:
            if not isinstance(raw_entry, dict) or set(raw_entry) - {"term", "variants", "multiplier"}:
                raise ValueError("invalid modifier")
            term = raw_entry.get("term")
            variants = raw_entry.get("variants")
            if not isinstance(term, str) or not term or not isinstance(variants, list):
                raise ValueError("invalid modifier")
            if any(not isinstance(variant, str) or not variant for variant in variants):
                raise ValueError("invalid modifier")
            multiplier: float | None = None
            if group == "emphasizers":
                multiplier = raw_entry.get("multiplier")
                if (
                    not isinstance(multiplier, (int, float))
                    or isinstance(multiplier, bool)
                    or not 1.0 < multiplier <= 2.0
                ):
                    raise ValueError("invalid emphasis multiplier")
                multiplier = float(multiplier)
            elif "multiplier" in raw_entry:
                raise ValueError("invalid modifier")
            entry = _ModifierEntry(term, multiplier)
            for surface in (term, *variants):
                if surface in seen_surfaces:
                    raise ValueError("duplicate modifier term")
                surfaces[surface] = entry
                seen_surfaces.add(surface)
        lookups[group] = MappingProxyType(surfaces)
    return MappingProxyType(lookups)


def _tokenize(text: str) -> list[_Token]:
    """Return words and supported punctuation while retaining source offsets."""
    return [
        _Token(match.group(), match.start(), match.end(), match.group() in ".!?,;:", text)
        for match in _TOKEN_PATTERN.finditer(text)
    ]


def _find_sentiment_matches(
    tokens: list[_Token], lexicon: Mapping[str, _LexiconEntry]
) -> list[_SentimentTokenMatch]:
    """Find non-overlapping sentiment entries, preferring the longest token span."""
    phrases = _sentiment_phrases(tuple(lexicon.items()))
    max_length = max((len(phrase) for phrase in phrases), default=0)

    matches: list[_SentimentTokenMatch] = []
    index = 0
    while index < len(tokens):
        if not _WORD_PATTERN.fullmatch(tokens[index].text):
            index += 1
            continue
        for length in range(min(max_length, len(tokens) - index), 0, -1):
            phrase = tuple(token.text for token in tokens[index : index + length])
            entry = phrases.get(phrase)
            if entry is None:
                continue
            span = tokens[index : index + length]
            source = span[0].source
            raw = (
                source[span[0].start : span[-1].end]
                if source is not None and all(token.source is source for token in span)
                else " ".join(token.text for token in span)
            )
            matches.append(
                _SentimentTokenMatch(
                    entry,
                    raw,
                    span[0].start,
                    span[-1].end,
                    index,
                    index + length,
                )
            )
            index += length
            break
        else:
            index += 1
    return matches


@lru_cache(maxsize=8)
def _sentiment_phrases(
    items: tuple[tuple[str, _LexiconEntry], ...],
) -> Mapping[tuple[str, ...], _LexiconEntry]:
    """Compile once; exact entries override generated forms, ambiguity abstains."""
    exact = {tuple(t.text for t in _tokenize(surface)): entry for surface, entry in items}
    generated: dict[tuple[str, ...], _LexiconEntry] = {}
    ambiguous = set()
    for phrase, entry in exact.items():
        if not phrase:
            continue
        is_variant = phrase != tuple(t.text for t in _tokenize(entry.term))
        for form in word_forms(phrase[-1], conversational=is_variant):
            key = (*phrase[:-1], form)
            previous = generated.get(key)
            if previous is not None and previous.score != entry.score:
                ambiguous.add(key)
            generated.setdefault(key, entry)
    return MappingProxyType({**{k: v for k, v in generated.items() if k not in ambiguous}, **exact})


@lru_cache(maxsize=1)
def _get_lexicon() -> Mapping[str, _LexiconEntry]:
    """Load the default lexicon on first use and reuse its immutable lookup."""
    return _load_lexicon(DEFAULT_LEXICON_PATH)


@lru_cache(maxsize=1)
def _get_modifiers() -> Mapping[str, Mapping[str, _ModifierEntry]]:
    """Load the default modifiers only when modifier scoring is requested."""
    return _load_modifiers(DEFAULT_MODIFIERS_PATH)


def _find_modifier_matches(
    tokens: list[_Token], lookup: Mapping[str, _ModifierEntry]
) -> list[_ModifierTokenMatch]:
    """Find non-overlapping modifier surfaces, preferring longer phrases."""
    phrases = _modifier_phrases(tuple(lookup.items()))
    max_length = max((len(phrase) for phrase in phrases), default=0)

    matches: list[_ModifierTokenMatch] = []
    index = 0
    while index < len(tokens):
        if tokens[index].is_boundary:
            index += 1
            continue
        for length in range(min(max_length, len(tokens) - index), 0, -1):
            entry = phrases.get(tuple(token.text for token in tokens[index : index + length]))
            if entry is None:
                continue
            matches.append(_ModifierTokenMatch(entry, index, index + length))
            index += length
            break
        else:
            index += 1
    return matches


@lru_cache(maxsize=8)
def _modifier_phrases(
    items: tuple[tuple[str, _ModifierEntry], ...],
) -> Mapping[tuple[str, ...], _ModifierEntry]:
    phrases = {}
    for surface, entry in items:
        phrase = tuple(t.text for t in _tokenize(surface))
        if not phrase:
            continue
        forms = (
            word_forms(phrase[-1], conversational=surface != entry.term)
            if entry.term in {"않다", "아니다", "없다", "못"} and len(surface) > 1
            else {phrase[-1]}
        )
        for form in forms:
            phrases[(*phrase[:-1], form)] = entry
    return MappingProxyType(phrases)


def _segment_ids(tokens: list[_Token]) -> list[int]:
    """Bound modifier scope at punctuation and explicit clause transitions."""
    segment = 0
    result: list[int] = []
    for token in tokens:
        result.append(segment)
        if token.is_boundary or token.text in _CLAUSE_CONNECTORS or token.text.endswith(("지만", "는데", "은데")):
            segment += 1
    return result


def _intervening_word_count(
    tokens: list[_Token], modifier: _ModifierTokenMatch, sentiment: _SentimentTokenMatch
) -> int:
    """Count word tokens strictly between a modifier and sentiment expression."""
    if modifier.token_end <= sentiment.token_start:
        between = tokens[modifier.token_end : sentiment.token_start]
    else:
        between = tokens[sentiment.token_end : modifier.token_start]
    return sum(not token.is_boundary for token in between)


def _modifier_values(
    tokens: list[_Token],
    sentiments: list[_SentimentTokenMatch],
    modifiers: Mapping[str, Mapping[str, _ModifierEntry]],
) -> tuple[list[float], list[int]]:
    """Associate each bounded modifier with one eligible sentiment expression."""
    segment_ids = _segment_ids(tokens)
    emphasis_values: list[list[float]] = [[] for _ in sentiments]
    negation_counts = [0 for _ in sentiments]

    for emphasis in _find_modifier_matches(tokens, modifiers["emphasizers"]):
        for index, sentiment in enumerate(sentiments):
            if sentiment.token_start < emphasis.token_end:
                continue
            if segment_ids[emphasis.token_start] != segment_ids[sentiment.token_start]:
                continue
            if _intervening_word_count(tokens, emphasis, sentiment) <= 2:
                multiplier = emphasis.entry.multiplier
                if multiplier is not None:
                    emphasis_values[index].append(multiplier)
                break

    previous_negation: tuple[_ModifierTokenMatch, int] | None = None
    for negation in _find_modifier_matches(tokens, modifiers["negations"]):
        # 못 is preverbal; 못하다/못해요 are postverbal auxiliaries.
        postposed_inability = (
            negation.entry.term == "못" and tokens[negation.token_start].text != "못"
        )
        # A lexical phrase already owns its internal negation (해결 안 됨).
        if any(s.token_start < negation.token_end and negation.token_start < s.token_end for s in sentiments):
            continue
        # A linked auxiliary chain can extend through a small grammatical bridge.
        # Full-match alternatives restrict this to nominalization/modal constructions.
        if previous_negation is not None:
            previous, owner = previous_negation
            bridge = " ".join(t.text for t in tokens[previous.token_end:negation.token_start])
            if (segment_ids[previous.token_start] == segment_ids[negation.token_start]
                    and negation.entry.term in {"않다", "아니다", "없다"}
                    and _NEGATION_BRIDGE.fullmatch(bridge)
                    and not any(previous.token_end <= s.token_start < negation.token_start for s in sentiments)):
                negation_counts[owner] += 1
                previous_negation = (negation, owner)
                continue
        eligible: list[tuple[int, int, int]] = []
        for index, sentiment in enumerate(sentiments):
            if segment_ids[negation.token_start] != segment_ids[sentiment.token_start]:
                continue
            distance = _intervening_word_count(tokens, negation, sentiment)
            if distance > 2:
                continue
            follows = sentiment.token_start >= negation.token_end
            # 안/못 precede their predicate. 않다/없다 follow the expression.
            # 아니다 keeps nearest-expression fallback for bare copular fragments.
            if (negation.entry.term in {"않다", "없다"} or postposed_inability) and follows:
                continue
            if negation.entry.term in {"안", "못"} and not postposed_inability and not follows:
                # Nominal light verbs: 도움이 안 된다 / 만족 안 해요.
                after = tokens[negation.token_end:negation.token_end + 1]
                nominal = (after and (
                    (after[0].text in word_forms("되다") and sentiment.raw.endswith(("이", "가")))
                    or (after[0].text in word_forms("하다") and not sentiment.entry.term.endswith("다"))
                ))
                reported = (negation.entry.term == "못" and after
                            and after[0].text in {"하다", "해요", "하겠습니다"}
                            and sentiment.raw.endswith("다고"))
                if not (nominal or reported):
                    continue
            eligible.append((distance, 0 if follows else 1, index))
        if eligible:
            owner = min(eligible)[2]
            negation_counts[owner] += 1
            previous_negation = (negation, owner)

    multipliers: list[float] = []
    for values in emphasis_values:
        product = 1.0
        for value in values:
            product *= value
        multipliers.append(min(product, 2.0))
    return multipliers, negation_counts


def analyze_sentiment(text: str, apply_modifiers: bool = True) -> SentimentResult:
    """Analyze text using lexicon scores and bounded modifier rules."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text.strip():
        raise ValueError("text must not be empty")

    tokens = _tokenize(text)
    token_matches = _find_sentiment_matches(tokens, _get_lexicon())
    if apply_modifiers:
        multipliers, negation_counts = _modifier_values(
            tokens, token_matches, _get_modifiers()
        )
    else:
        multipliers = [1.0 for _ in token_matches]
        negation_counts = [0 for _ in token_matches]
    matches = [
        SentimentMatch(
            term=match.entry.term,
            raw=match.raw,
            base_score=match.entry.score,
            emphasis_multiplier=multipliers[index],
            negation_count=negation_counts[index],
            contribution=float(
                match.entry.score
                * multipliers[index]
                * (-1) ** negation_counts[index]
            ),
            start=match.start,
            end=match.end,
        )
        for index, match in enumerate(token_matches)
    ]
    score = round(sum(match.contribution for match in matches), 6)
    label = "positive" if score > 0 else "negative" if score < 0 else "neutral"
    mixed = (
        any(match.contribution > 0 for match in matches)
        and any(match.contribution < 0 for match in matches)
    )

    return SentimentResult(score, label, mixed, [token.raw for token in tokens], matches)
