from dataclasses import dataclass
from typing import Literal, TypeAlias

ExtractionType: TypeAlias = Literal["email", "phone", "date", "money", "url"]
SentimentLabel: TypeAlias = Literal["positive", "negative", "neutral"]


@dataclass(frozen=True, slots=True)
class MoneyValue:
    amount: int
    currency: Literal["KRW", "USD"]


NormalizedValue: TypeAlias = str | MoneyValue


@dataclass(frozen=True, slots=True)
class ExtractionItem:
    type: ExtractionType
    raw: str
    normalized: NormalizedValue
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Diagnostic:
    type: ExtractionType
    raw: str
    start: int
    end: int
    reason: str


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    items: list[ExtractionItem]
    diagnostics: list[Diagnostic]


@dataclass(frozen=True, slots=True)
class SentimentMatch:
    term: str
    raw: str
    base_score: int
    emphasis_multiplier: float
    negation_count: int
    contribution: float
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class SentimentResult:
    score: float
    label: SentimentLabel
    mixed: bool
    tokens: list[str]
    matches: list[SentimentMatch]


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    text: str
    extractions: list[ExtractionItem]
    sentiment: SentimentResult
    diagnostics: list[Diagnostic]


@dataclass(frozen=True, slots=True)
class MorphToken:
    morph: str
    pos: str
    start: int
    end: int
    eojeol_index: int


@dataclass(frozen=True, slots=True)
class MorphologyAdjustment:
    kind: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class SentimentEvent:
    canonical_id: str
    term: str
    score: int
    token_start: int
    token_end: int
    atomic: bool


@dataclass(frozen=True, slots=True)
class ModifierLink:
    event_index: int
    modifier_start: int
    modifier_end: int
    kind: str
    rule_id: str
    multiplier: float


@dataclass(frozen=True, slots=True)
class LexicalEntry:
    canonical_id: str
    term: str
    score: int
    domain: str | None
    sources: tuple[str, ...]
    atomic: bool
    priority: int
    keys: tuple[tuple[tuple[str, str], ...], ...]
