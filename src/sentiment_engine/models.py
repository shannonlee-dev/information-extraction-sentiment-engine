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
