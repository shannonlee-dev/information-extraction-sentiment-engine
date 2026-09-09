"""추출 값과 감성 점수의 반환 구조."""
from dataclasses import dataclass
from typing import Literal, TypeAlias

ExtractionType: TypeAlias = Literal["email", "phone", "date", "money", "url"]
SentimentLabel: TypeAlias = Literal["positive", "negative", "neutral"]


@dataclass
class MoneyValue:
    amount: int
    currency: Literal["KRW", "USD"]


NormalizedValue: TypeAlias = str | MoneyValue


@dataclass
class ExtractionItem:
    type: ExtractionType
    raw: str
    normalized: NormalizedValue
    start: int
    end: int


@dataclass
class Diagnostic:
    type: ExtractionType
    raw: str
    start: int
    end: int
    reason: str


@dataclass
class ExtractionResult:
    items: list[ExtractionItem]
    diagnostics: list[Diagnostic]


@dataclass
class SentimentMatch:
    term: str
    raw: str
    base_score: int
    emphasis_multiplier: float
    negation_count: int
    contribution: float


@dataclass
class SentimentResult:
    score: float
    label: SentimentLabel
    tokens: list[str]
    matches: list[SentimentMatch]
