"""Compiled lexical events and the unchanged public sentiment API."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from sentiment_engine.korean import analyze_morphology, analyzer_fingerprint
from sentiment_engine.models import LexicalEntry, MorphToken, SentimentEvent, SentimentResult

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEXICON_PATH = _REPOSITORY_ROOT / 'data/sentiment_lexicon.json'
DEFAULT_ANNOTATIONS_PATH = _REPOSITORY_ROOT / 'data/lexicon_annotations.json'
DEFAULT_COMPILED_PATH = _REPOSITORY_ROOT / 'data/sentiment_lexicon_compiled.json'
DEFAULT_MODIFIERS_PATH = _REPOSITORY_ROOT / 'data/modifiers.json'
_TOKEN_PATTERN = re.compile(r"[가-힣A-Za-z0-9]+|[.!?,;:]")

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



@lru_cache(maxsize=1)
def _get_modifiers():
    return _load_modifiers(DEFAULT_MODIFIERS_PATH)


def _load_compiled(path: Path, source_path: Path = DEFAULT_LEXICON_PATH,
                   annotations_path: Path = DEFAULT_ANNOTATIONS_PATH) -> tuple[LexicalEntry, ...]:
    artifact = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(artifact, dict) or artifact.get('schema_version') != 1:
        raise ValueError('invalid compiled lexicon schema')
    for field, source in (('source_sha256', source_path), ('annotations_sha256', annotations_path)):
        if artifact.get(field) != hashlib.sha256(Path(source).read_bytes()).hexdigest():
            raise ValueError(f'compiled lexicon {field} mismatch; rebuild the lexicon')
    if artifact.get('analyzer') != analyzer_fingerprint():
        raise ValueError('compiled lexicon analyzer/model hash mismatch; rebuild with the locked runtime')
    if not isinstance(artifact.get('entries'), list):
        raise ValueError('compiled lexicon entries must be a list')
    entries, ids, keys = [], set(), set()
    for row in artifact.get('entries', []):
        if (not isinstance(row,dict) or not isinstance(row.get('canonical_id'),str)
                or not row['canonical_id'] or row['canonical_id'] in ids
                or not isinstance(row.get('term'),str) or not row['term']
                or type(row.get('score')) is not int or row['score'] not in {-3,-2,-1,1,2,3}
                or type(row.get('atomic')) is not bool or type(row.get('priority')) is not int
                or not isinstance(row.get('sources'),list) or not row['sources']
                or any(not isinstance(s,str) or not s for s in row['sources'])
                or (row.get('domain') is not None and not isinstance(row['domain'],str))):
            raise ValueError('invalid compiled lexical entry')
        entry_keys=[]
        if not isinstance(row.get('keys'),list) or not row['keys']:
            raise ValueError('compiled lexical entry requires keys')
        for key in row['keys']:
            if not isinstance(key,list) or not key or any(
                    not isinstance(pair,list) or len(pair)!=2 or any(not isinstance(x,str) or not x for x in pair)
                    for pair in key):
                raise ValueError('invalid compiled lexical key')
            immutable=tuple(tuple(pair) for pair in key)
            if immutable in keys:
                raise ValueError('duplicate compiled lexical key')
            keys.add(immutable)
            entry_keys.append(immutable)
        ids.add(row['canonical_id'])
        entries.append(LexicalEntry(row['canonical_id'],row['term'],row['score'],row.get('domain'),
                                    tuple(row['sources']),row['atomic'],row['priority'],tuple(entry_keys)))
    if len(entries)<200:
        raise ValueError('compiled lexicon requires at least 200 canonical entries')
    if sum(e.domain=='customer_support' and 'project' in e.sources for e in entries)<30:
        raise ValueError('compiled lexicon requires at least 30 project domain entries')
    return tuple(entries)


@lru_cache(maxsize=1)
def _get_lexicon() -> tuple[LexicalEntry,...]:
    return _load_compiled(DEFAULT_COMPILED_PATH)


@lru_cache(maxsize=4)
def _index(entries: tuple[LexicalEntry,...]):
    index={}
    for entry in entries:
        for key in entry.keys:
            index.setdefault(key[0],[]).append((key,entry))
    return {first: tuple(sorted(rows,key=lambda row:(-len(row[0]),-row[1].priority,row[1].canonical_id)))
            for first,rows in index.items()}


def find_events(tokens: tuple[MorphToken,...], entries: tuple[LexicalEntry,...] | None = None,
                *, text: str | None = None) -> tuple[SentimentEvent,...]:
    """Leftmost, longest lexical keys; no deletion of intervening morphology."""
    index=_index(_get_lexicon() if entries is None else entries)
    events=[]
    i=0
    while i<len(tokens):
        first=tokens[i]
        for key,entry in index.get((first.morph,first.pos),()):
            end=i+len(key)
            span=tokens[i:end]
            if tuple((t.morph,t.pos) for t in span)!=key:
                continue
            if text is not None and any(c in text[first.start:span[-1].end] for c in '\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029'):
                continue
            if i and tokens[i-1].eojeol_index==first.eojeol_index and (
                    tokens[i-1].pos.startswith(('NN','XR','XP'))):
                # Missing whitespace can join a noun to an independent
                # predicate (including an audited noun + copula key).
                # Retain the predicate's original morphology and
                # offsets, but still reject noun fragments and bound prefixes.
                if not (tokens[i-1].pos.startswith('NN') and span[-1].pos in {'VA','VV','XSA','XSV','VCP'}):
                    continue
            last=span[-1]
            if end<len(tokens) and tokens[end].eojeol_index==last.eojeol_index:
                following=tokens[end].pos
                if last.pos.startswith(('NN','XR')) and following.startswith(('NN','XSN','XSA','XSV')):
                    continue
            events.append(SentimentEvent(entry.canonical_id,entry.term,entry.score,i,end,entry.atomic))
            i=end
            break
        else:
            i+=1
    return tuple(events)


def analyze_sentiment(text: str, apply_modifiers: bool = True) -> SentimentResult:
    if not isinstance(text,str):
        raise TypeError('text must be a string')
    if not text.strip():
        raise ValueError('text must not be empty')
    from sentiment_engine.sentiment_rules import link_modifiers, score_events

    morphology=analyze_morphology(text)
    events=find_events(morphology,text=text)
    links=link_modifiers(text,morphology,events) if apply_modifiers else ()
    matches=score_events(text,morphology,events,links,apply_modifiers=apply_modifiers)
    score=round(sum(m.contribution for m in matches),6)
    label='positive' if score>0 else 'negative' if score<0 else 'neutral'
    mixed=any(m.contribution>0 for m in matches) and any(m.contribution<0 for m in matches)
    return SentimentResult(score,label,mixed,[t.raw for t in _tokenize(text)],matches)
