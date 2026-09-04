"""Validated sentiment resources and token-level matching primitives."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEXICON_PATH = _REPOSITORY_ROOT / "data" / "sentiment_lexicon.json"
DEFAULT_MODIFIERS_PATH = _REPOSITORY_ROOT / "data" / "modifiers.json"
_TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9]+|[.!?,;:]")
_WORD_PATTERN = re.compile(r"[가-힣A-Za-z0-9]+")
_VALID_SCORES = frozenset({-3, -2, -1, 1, 2, 3})


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

    @property
    def text(self) -> str:
        return self.raw


@dataclass(frozen=True, slots=True)
class _SentimentTokenMatch:
    entry: _LexiconEntry
    raw: str
    start: int
    end: int


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
                if surface in surfaces:
                    raise ValueError("duplicate modifier term")
                surfaces[surface] = entry
        lookups[group] = MappingProxyType(surfaces)
    return MappingProxyType(lookups)


def _tokenize(text: str) -> list[_Token]:
    """Return words and supported punctuation while retaining source offsets."""
    return [
        _Token(match.group(), match.start(), match.end(), match.group() in ".!?")
        for match in _TOKEN_PATTERN.finditer(text)
    ]


def _find_sentiment_matches(
    tokens: list[_Token], lexicon: Mapping[str, _LexiconEntry]
) -> list[_SentimentTokenMatch]:
    """Find non-overlapping sentiment entries, preferring the longest token span."""
    phrases: dict[tuple[str, ...], _LexiconEntry] = {}
    for surface, entry in lexicon.items():
        phrase = tuple(token.text for token in _tokenize(surface))
        if phrase:
            phrases[phrase] = entry
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
            matches.append(
                _SentimentTokenMatch(
                    entry, " ".join(token.text for token in span), span[0].start, span[-1].end
                )
            )
            index += length
            break
        else:
            index += 1
    return matches
