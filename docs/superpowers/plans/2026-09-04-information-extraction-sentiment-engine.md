# Information Extraction Sentiment Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Build a reproducible Python package and CLI that extracts five structured information types, normalizes them, scores Korean sentiment with explicit modifier rules, and evaluates both subsystems.

**Architecture:** A small `src` package keeps result contracts, extraction, sentiment, evaluation, and CLI responsibilities separate. The extraction and sentiment analyzers are independently callable; the integrated API and CLI delegate to those same implementations, while fixed JSON datasets drive deterministic evaluation.

**Tech Stack:** Python 3.10+, standard-library `re`, `dataclasses`, `datetime`, `json`, `urllib.parse`, `argparse`, and pytest 8.x.

**Spec:** `docs/superpowers/specs/2026-09-04-information-extraction-sentiment-engine-design.md`

## Global Constraints

- Treat `docs/private/mission.md` and `docs/private/rubric.md` as the highest-authority requirements.
- Use Python 3.10 or newer and Python's built-in `re` module for every regular expression.
- Include `requirements.txt`; do not add KoNLPy, NLTK, a database, a web API, or a web UI.
- Support email, phone, date, money, and URL extraction with at least three input variants per type.
- Keep a repository-local sentiment lexicon with at least 200 unique terms and at least 30 terms marked `customer_support`.
- Implement lexicon scoring, emphasis, negation, one explicit double-negation pattern, neutral output, and the `mixed` diagnostic.
- Keep bonus work out of scope: PII masking, ML implementation, data-size experiments, aspect sentiment, sarcasm, and contextual inference.
- Every production change follows red-green-refactor TDD and ends with a focused commit.
- Do not commit `docs/private/`; it remains the user's untracked source material.

---

## File Map

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, Python floor, pytest configuration |
| `requirements.txt` | Editable project install and test dependency |
| `.gitignore` | Python build, cache, coverage, and virtual-environment artifacts |
| `src/sentiment_engine/models.py` | Stable dataclass result contracts and type aliases |
| `src/sentiment_engine/extraction.py` | Five regex families, semantic validation, normalization, deduplication |
| `src/sentiment_engine/sentiment.py` | Resource validation, tokenization, longest-match lookup, scoring rules |
| `src/sentiment_engine/evaluation.py` | Exact-match extraction metrics and sentiment classification metrics |
| `src/sentiment_engine/cli.py` | CLI parsing, API invocation, JSON and text rendering |
| `src/sentiment_engine/__init__.py` | Public API: `extract_information`, `analyze_sentiment`, `analyze` |
| `data/sentiment_lexicon.json` | At least 200 scored, sourced sentiment entries |
| `data/modifiers.json` | Negation variants and emphasis multipliers |
| `tests/fixtures/extraction_cases.json` | At least 50 extraction cases with gold spans and normalized values |
| `tests/fixtures/sentiment_cases.json` | At least 100 labeled sentiment cases |
| `tests/test_models.py` | Result contract tests |
| `tests/extraction/test_contact.py` | Email and phone tests |
| `tests/extraction/test_date_money.py` | Date and money tests |
| `tests/extraction/test_url_service.py` | URL, ordering, diagnostics, deduplication tests |
| `tests/sentiment/test_resources_tokenizer.py` | Resource schema and token matching tests |
| `tests/sentiment/test_scoring.py` | Base score and label tests |
| `tests/sentiment/test_modifiers.py` | Emphasis, negation, double-negation, scope tests |
| `tests/test_integration_cli.py` | Integrated API and subprocess CLI tests |
| `tests/test_evaluation.py` | Metric formulas and fixture validation tests |
| `main.py` | Thin executable wrapper around `sentiment_engine.cli.main` |
| `README.md` | Installation, design, evaluation, failure analysis, limitations |

## Stable Interfaces

Later tasks must use these names and signatures exactly:

- `extract_information(text: str) -> ExtractionResult`
- `analyze_sentiment(text: str, apply_modifiers: bool = True) -> SentimentResult`
- `analyze(text: str) -> AnalysisResult`
- `evaluate_extraction(cases: list[dict[str, object]]) -> dict[str, object]`
- `evaluate_sentiment(cases: list[dict[str, object]], apply_modifiers: bool = True) -> dict[str, object]`
- `load_extraction_cases(path: Path) -> list[dict[str, object]]`
- `load_sentiment_cases(path: Path) -> list[dict[str, object]]`
- `main(argv: Sequence[str] | None = None) -> int`

## Spec Coverage Map

| Spec IDs | Implemented and verified by |
|---|---|
| IE-01–IE-04 | Tasks 2–4 extraction code/tests; Task 10 regex documentation |
| SA-01–SA-03 | Tasks 5–6 resources, tokenizer, base scoring |
| SA-04–SA-07 | Task 7 modifier and label tests; Task 10 calculation examples |
| EV-01–EV-07 | Task 9 validated fixtures, metrics, error output; Task 10 measured analysis |
| DOC-01–DOC-07 | Tasks 1 and 8 runnable environment; Task 10 README |
| TEST-01 | Every task's focused regression plus Tasks 9–10 full gates |
| ENV-01 | Task 1 Python floor and dependency files |

---

### Task 1: Package Foundation and Result Contracts

**Files:**
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `src/sentiment_engine/__init__.py`
- Create: `src/sentiment_engine/models.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Consumes: No project code.
- Produces: `ExtractionType`, `MoneyValue`, `ExtractionItem`, `Diagnostic`, `ExtractionResult`, `SentimentMatch`, `SentimentResult`, and `AnalysisResult`.

- [x] **Step 1: Create package metadata and the failing contract tests**

Use this package configuration:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "information-extraction-sentiment-engine"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = []

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Use this `requirements.txt`:

```text
-e .
pytest>=8,<9
```

Ignore `.venv/`, `__pycache__/`, `*.py[cod]`, `.pytest_cache/`, `.coverage`, `htmlcov/`, `build/`, `dist/`, and `*.egg-info/`.

In `tests/test_models.py`, construct every result model and assert dataclass equality, nested money normalization, half-open offsets, and `asdict()` JSON-compatible output. The canonical money assertion is:

```python
from dataclasses import asdict

from sentiment_engine.models import ExtractionItem, MoneyValue


def test_money_extraction_item_serializes() -> None:
    item = ExtractionItem(
        type="money",
        raw="10,000원",
        normalized=MoneyValue(amount=10_000, currency="KRW"),
        start=4,
        end=11,
    )
    assert asdict(item)["normalized"] == {"amount": 10_000, "currency": "KRW"}
```

- [x] **Step 2: Run the contract test and confirm the expected failure**

Run: `python -m pytest tests/test_models.py -v`

Expected: collection fails with `ModuleNotFoundError` for `sentiment_engine.models`.

- [x] **Step 3: Implement the result contracts**

Use frozen, slotted dataclasses. Define these exact fields:

```python
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
```

Keep `src/sentiment_engine/__init__.py` empty until public functions exist.

- [x] **Step 4: Run the focused and aggregate tests**

Run: `python -m pytest tests/test_models.py -v`

Expected: all model tests pass.

Run: `python -m pytest`

Expected: all current tests pass.

- [x] **Step 5: Commit Task 1**

```bash
git add .gitignore pyproject.toml requirements.txt src/sentiment_engine tests/test_models.py
git commit -m "chore: establish package result contracts"
```

---

### Task 2: Email and Phone Extraction

**Files:**
- Create: `src/sentiment_engine/extraction.py`
- Create: `tests/extraction/test_contact.py`

**Interfaces:**
- Consumes: `ExtractionItem`, `Diagnostic`, `ExtractionResult` from Task 1.
- Produces: internal `_extract_emails(text)` and `_extract_phones(text)` functions returning `(items, diagnostics)` tuples.

- [x] **Step 1: Write failing table-driven tests**

Cover these exact accepted values:

```python
EMAIL_CASES = [
    ("user@domain.com", "user@domain.com"),
    ("User.Name@Sub.Domain.CO.KR", "User.Name@sub.domain.co.kr"),
    ("user+tag@example.org", "user+tag@example.org"),
]

PHONE_CASES = [
    ("010-1234-5678", "010-1234-5678"),
    ("010 1234 5678", "010-1234-5678"),
    ("01012345678", "010-1234-5678"),
    ("02-123-4567", "02-123-4567"),
    ("031-1234-5678", "031-1234-5678"),
]
```

Also assert rejection of `user@localhost`, `user..name@example.com`, `010-12-5678`, `070-1234-5678`, and phone digits embedded inside a longer digit sequence. Assert `start` and `end` against `text[item.start:item.end]` for every match.

- [x] **Step 2: Run tests and confirm the expected import failure**

Run: `python -m pytest tests/extraction/test_contact.py -v`

Expected: collection fails because `sentiment_engine.extraction` does not exist.

- [x] **Step 3: Implement email extraction and normalization**

Compile one verbose email candidate pattern with named `local` and `domain` groups. Its comments must explain the local-part character class, repeated dotted domain labels, terminal domain length, and lookaround boundaries. Validation must reject empty labels, consecutive dots in the local part, leading/trailing local dots, and domain labels that begin or end with `-`. Preserve the local part and lowercase only the domain.

Return diagnostics only when a regex candidate was found but semantic validation rejected it. Use reason codes `invalid_email_local` and `invalid_email_domain`.

- [x] **Step 4: Implement phone extraction and normalization**

The allowed area-code collection must contain exactly:

```python
AREA_CODES = (
    "010", "02", "031", "032", "033", "041", "042", "043", "044",
    "051", "052", "053", "054", "055", "061", "062", "063", "064",
)
```

Use a deliberately broad phone candidate prefix `0\d{1,2}` so invalid but phone-like prefixes can reach semantic validation. Then validate the captured prefix against `AREA_CODES`. Match a 3- or 4-digit exchange and a 4-digit subscriber number with either consistent `-`, consistent spaces, or no separator. Normalize using `f"{area}-{exchange}-{subscriber}"`. Reject unsupported prefixes and inconsistent separators with `invalid_phone_prefix` or `invalid_phone_format`.

- [x] **Step 5: Run contact tests and the full suite**

Run: `python -m pytest tests/extraction/test_contact.py -v`

Expected: accepted cases normalize exactly, invalid cases do not produce items, and offsets pass.

Run: `python -m pytest`

Expected: all current tests pass.

- [x] **Step 6: Commit Task 2**

```bash
git add src/sentiment_engine/extraction.py tests/extraction/test_contact.py
git commit -m "feat: extract email and phone information"
```

---

### Task 3: Date and Money Extraction

**Files:**
- Modify: `src/sentiment_engine/extraction.py`
- Create: `tests/extraction/test_date_money.py`

**Interfaces:**
- Consumes: Task 2 extraction conventions and `MoneyValue`.
- Produces: internal `_extract_dates(text)` and `_extract_money(text)` functions returning `(items, diagnostics)` tuples.

- [x] **Step 1: Write failing date tests**

Parametrize these mappings:

```python
DATE_CASES = [
    ("2024년 1월 15일", "2024-01-15"),
    ("2024/01/15", "2024-01-15"),
    ("2024-01-15", "2024-01-15"),
    ("2024년 2월 29일", "2024-02-29"),
]
```

Assert that `2023-02-29`, `2024-02-30`, `2024/13/01`, and `2024년 1월` produce no date item. Candidates with all three components but an invalid calendar date must produce `invalid_calendar_date` diagnostics.

- [x] **Step 2: Write failing money tests**

Parametrize these normalized values:

```python
MONEY_CASES = [
    ("10,000원", MoneyValue(10_000, "KRW")),
    ("12000원", MoneyValue(12_000, "KRW")),
    ("1억 2천만원", MoneyValue(120_000_000, "KRW")),
    ("3억 5천만 2만원", MoneyValue(350_020_000, "KRW")),
    ("$100", MoneyValue(100, "USD")),
]
```

Assert that `1,00원`, `2만 1억원`, `$10.50`, `100`, and `원` do not produce money items. A matched Korean-unit candidate with descending-unit violations must produce `invalid_money_unit_order`.

- [x] **Step 3: Run the focused tests and observe failures**

Run: `python -m pytest tests/extraction/test_date_money.py -v`

Expected: failures show missing date and money extraction behavior.

- [x] **Step 4: Implement date candidate matching and calendar validation**

Use named `year`, `month`, and `day` groups for the Korean, slash, and hyphen variants. Convert group values with `date(year, month, day)` and normalize with `.isoformat()`. Catch only `ValueError` from calendar construction and emit `invalid_calendar_date`.

- [x] **Step 5: Implement integer and Korean-unit money normalization**

Use these exact unit multipliers:

```python
UNIT_VALUES = {
    "억": 100_000_000,
    "천만": 10_000_000,
    "만": 10_000,
    "천": 1_000,
}
```

Parse units from largest to smallest, disallow duplicates and ascending order, and sum `coefficient * multiplier`. For a final bare number immediately before `원`, add it as single won. Remove valid thousands commas before integer conversion. Dollar values accept digits and valid thousands grouping only, without decimals. Return `MoneyValue` and use `invalid_money_number` or `invalid_money_unit_order` for rejected candidates.

- [x] **Step 6: Run focused and full tests**

Run: `python -m pytest tests/extraction/test_date_money.py -v`

Expected: all date and money tests pass.

Run: `python -m pytest`

Expected: all current tests pass.

- [x] **Step 7: Commit Task 3**

```bash
git add src/sentiment_engine/extraction.py tests/extraction/test_date_money.py
git commit -m "feat: extract normalized dates and money"
```

---

### Task 4: URL Extraction and Extraction Service

**Files:**
- Modify: `src/sentiment_engine/extraction.py`
- Modify: `src/sentiment_engine/__init__.py`
- Create: `tests/extraction/test_url_service.py`

**Interfaces:**
- Consumes: all Task 2-3 extractors.
- Produces: public `extract_information(text: str) -> ExtractionResult`.

- [x] **Step 1: Write failing URL and service tests**

Cover these URL mappings:

```python
URL_CASES = [
    ("https://www.example.com", "https://www.example.com"),
    ("HTTP://Example.COM/path", "http://example.com/path"),
    (
        "https://www.example.com/path?query=value#part",
        "https://www.example.com/path?query=value#part",
    ),
]
```

Assert that surrounding `< >`, `( )`, and terminal `.`, `,`, `!`, `?` are excluded from `raw`; query punctuation remains when it is part of a key/value pair. Reject `ftp://example.com`, `https:///path`, and `https://`. Missing-host candidates use `missing_url_host`.

For the service, use one text containing all five types and assert items are sorted by `start`. Assert identical `(type, start, end)` candidates are deduplicated. Assert non-string input raises `TypeError`, while `""` and whitespace-only text raise `ValueError`.

- [x] **Step 2: Run tests and observe the expected failures**

Run: `python -m pytest tests/extraction/test_url_service.py -v`

Expected: failures identify missing URL support and public orchestration.

- [x] **Step 3: Implement URL validation and normalization**

Match `http://` or `https://` followed by non-whitespace candidate characters. Remove only unmatched wrapper characters and terminal sentence punctuation, then validate with `urllib.parse.urlsplit`. Require scheme in `{http, https}` and a non-empty hostname. Rebuild the URL with lowercase scheme and hostname while preserving user info, explicit port, path, query, and fragment.

- [x] **Step 4: Implement the extraction orchestrator**

Validate input first. Call the five type-specific extractors, concatenate results, deduplicate by `(type, start, end)`, and sort items and diagnostics by `(start, end, type)`. Export `extract_information` from `src/sentiment_engine/__init__.py`.

Do not suppress unexpected programming errors; only candidate validation failures become diagnostics.

- [x] **Step 5: Run extraction tests and full regression**

Run: `python -m pytest tests/extraction -v`

Expected: all extraction tests pass.

Run: `python -m pytest`

Expected: all current tests pass.

- [x] **Step 6: Commit Task 4**

```bash
git add src/sentiment_engine/extraction.py src/sentiment_engine/__init__.py tests/extraction/test_url_service.py
git commit -m "feat: complete extraction service"
```

---

### Task 5: Sentiment Resources and Token Matching

**Files:**
- Create: `data/sentiment_lexicon.json`
- Create: `data/modifiers.json`
- Create: `src/sentiment_engine/sentiment.py`
- Create: `tests/sentiment/test_resources_tokenizer.py`

**Interfaces:**
- Consumes: no extraction code.
- Produces: `_load_lexicon(path)`, `_load_modifiers(path)`, `_tokenize(text)`, and `_find_sentiment_matches(tokens, lexicon)` internal helpers.

- [x] **Step 1: Write failing resource-validation tests**

Tests must assert:

- the committed lexicon has at least 200 unique `term` values;
- at least 30 entries have `domain == "customer_support"`;
- every score is an integer in `{-3, -2, -1, 1, 2, 3}`;
- every entry has non-empty `term`, list-valued `variants`, valid `source`, and optional `domain`;
- duplicates across `term` values fail with `ValueError("duplicate sentiment term")`;
- one surface form appearing as a `term` or `variant` for two different entries fails with `ValueError("conflicting sentiment surface")`;
- a zero score fails with `ValueError("invalid sentiment score")`;
- fewer than 200 terms fail with `ValueError("sentiment lexicon requires at least 200 terms")`;
- fewer than 30 customer-support terms fail with `ValueError("sentiment lexicon requires at least 30 domain terms")`;
- emphasis multipliers must be greater than `1.0` and at most `2.0`;
- duplicate modifier terms or variants fail validation.

- [x] **Step 2: Write failing tokenizer and longest-match tests**

Use `"배송이 정말 빠르다! 응대는 좋지 않다."` and assert tokens preserve Korean words plus `!` and `.` as separate sentence-boundary tokens. Construct a validated in-memory lookup containing overlapping entries `"마음"` and `"마음에 들다"`; assert the longer expression claims the span and the shorter one is not emitted for that span. Keep the resource-count tests separate so this focused lookup test does not need to fabricate 200 entries.

- [x] **Step 3: Run the focused tests and confirm failures**

Run: `python -m pytest tests/sentiment/test_resources_tokenizer.py -v`

Expected: collection fails because sentiment resources and loader code do not exist.

- [x] **Step 4: Create the committed lexicon and modifier resources**

Create a top-level JSON array of at least 200 lexicon objects with this exact schema:

```json
[
  {
    "term": "만족",
    "variants": ["만족해요", "만족했다"],
    "score": 2,
    "domain": "customer_support",
    "source": "project"
  },
  {
    "term": "실망",
    "variants": ["실망했다", "실망이에요"],
    "score": -2,
    "domain": "customer_support",
    "source": "project"
  }
]
```

The final file must not stop at these two examples. Build a balanced inventory with at least 85 general positive terms, 85 general negative terms, 15 customer-support positive terms, and 15 customer-support negative terms. Domain terms must cover delivery, response, refund, exchange, payment, product quality, waiting time, and issue resolution. Record `source: "project"` for directly selected terms; if an entry was adapted from another resource, record that resource's stable name instead.

The inventory must include these anchor mappings because later behavior tests depend on them:

| `term` | required `variants` | `score` |
|---|---|---|
| `좋다` | `좋아`, `좋아요`, `좋지만`, `좋지` | `2` |
| `훌륭하다` | `훌륭해`, `훌륭해요` | `3` |
| `친절하다` | `친절해`, `친절하고` | `2` |
| `느리다` | `느려`, `느려요` | `-2` |
| `만족` | `만족해요`, `만족했다` | `2` |
| `실망` | `실망해요`, `실망했다` | `-2` |

Create `data/modifiers.json` with at least these entries:

```json
{
  "negations": [
    {"term": "않다", "variants": ["않아", "않은", "않았어요", "않았다", "않지"]},
    {"term": "아니다", "variants": ["아니", "아니에요", "아닌", "아니었다"]},
    {"term": "못", "variants": ["못하다", "못했다", "못해요"]},
    {"term": "없다", "variants": ["없는", "없어요", "없었다"]}
  ],
  "emphasizers": [
    {"term": "매우", "variants": [], "multiplier": 1.5},
    {"term": "정말", "variants": [], "multiplier": 1.5},
    {"term": "아주", "variants": [], "multiplier": 1.5},
    {"term": "너무", "variants": [], "multiplier": 1.5},
    {"term": "굉장히", "variants": [], "multiplier": 1.7}
  ]
}
```

- [x] **Step 5: Implement strict resource loaders**

Load UTF-8 JSON, validate the exact conditions from Step 1, and return immutable lookup structures indexed by every `term` and `variant`. A shorter surface may be a token-prefix of a longer expression for longest-match behavior, but the same complete surface string cannot map to two entries. Resolve default data paths relative to the repository root using `Path(__file__).resolve().parents[2] / "data"`. Load and validate lazily on the first analyzer call rather than during module import; CLI startup validation occurs through that first call. Raise `FileNotFoundError` for missing files and `ValueError` with the tested messages for schema violations.

- [x] **Step 6: Implement tokenization and longest-match lookup**

Represent internal tokens with raw text, start, end, and an `is_boundary` flag. Tokenize with a compiled regex that emits `[가-힣A-Za-z0-9]+` word tokens and `. ! ? , ; :` punctuation tokens. Convert every lexicon term and variant through the same tokenizer. At each word token, try the greatest token length first; after a match, advance past its span so shorter overlaps cannot also match.

- [x] **Step 7: Run focused and full tests**

Run: `python -m pytest tests/sentiment/test_resources_tokenizer.py -v`

Expected: all resource and token tests pass, including count checks against committed JSON.

Run: `python -m pytest`

Expected: all current tests pass.

- [x] **Step 8: Commit Task 5**

```bash
git add data src/sentiment_engine/sentiment.py tests/sentiment/test_resources_tokenizer.py
git commit -m "feat: add sentiment resources and token matching"
```

---

### Task 6: Base Sentiment Scoring and Labels

**Files:**
- Modify: `src/sentiment_engine/sentiment.py`
- Modify: `src/sentiment_engine/__init__.py`
- Create: `tests/sentiment/test_scoring.py`

**Interfaces:**
- Consumes: Task 5 loaders and match spans; `SentimentMatch` and `SentimentResult` from Task 1.
- Produces: public `analyze_sentiment(text: str, apply_modifiers: bool = True) -> SentimentResult` with base scoring operational.

- [x] **Step 1: Write failing base-scoring tests**

Use lexicon terms committed in Task 5 and assert:

```python
def test_base_positive_score() -> None:
    result = analyze_sentiment("서비스가 친절하고 훌륭하다", apply_modifiers=False)
    assert result.score > 0
    assert result.label == "positive"
    assert result.mixed is False


def test_base_mixed_score_exposes_diagnostic() -> None:
    result = analyze_sentiment("품질은 좋지만 배송은 느리다", apply_modifiers=False)
    assert result.mixed is True
    assert {match.contribution > 0 for match in result.matches} == {True, False}
```

Add negative, exact-zero neutral, no-match neutral, non-string, empty-string, and whitespace-only cases. Require `TypeError` for non-string and `ValueError` for empty or whitespace-only input.

- [x] **Step 2: Run tests and confirm scoring failures**

Run: `python -m pytest tests/sentiment/test_scoring.py -v`

Expected: failures show that the public analyzer and score aggregation are absent.

- [x] **Step 3: Implement base contributions and final classification**

For every lexicon match, construct a `SentimentMatch` with multiplier `1.0`, negation count `0`, and contribution equal to its integer base score. Sum contributions, round once to six decimal places, and label by sign. Set `mixed=True` only when final per-match contributions contain at least one positive and one negative value. Return the raw token texts in `tokens`.

When `apply_modifiers=False`, never load or inspect modifier rules. When it is `True`, preserve base behavior until Task 7 adds modifier calculations. Export `analyze_sentiment` from `__init__.py`.

- [x] **Step 4: Run focused and full tests**

Run: `python -m pytest tests/sentiment/test_scoring.py -v`

Expected: base scoring, labels, mixed flag, and input errors pass.

Run: `python -m pytest`

Expected: all current tests pass.

- [x] **Step 5: Commit Task 6**

```bash
git add src/sentiment_engine/sentiment.py src/sentiment_engine/__init__.py tests/sentiment/test_scoring.py
git commit -m "feat: calculate base sentiment scores"
```

---

### Task 7: Emphasis, Negation, and Double Negation

**Files:**
- Modify: `src/sentiment_engine/sentiment.py`
- Create: `tests/sentiment/test_modifiers.py`

**Interfaces:**
- Consumes: Task 6 `analyze_sentiment` and Task 5 modifier lookups.
- Produces: complete `apply_modifiers=True` behavior with per-match multiplier and negation count.

- [x] **Step 1: Write failing emphasis tests**

Assert `"정말 만족"` yields the score for `만족` multiplied by `1.5`. Assert two emphasis expressions multiply but cap at `2.0`. Assert an emphasis expression applies only to the next sentiment match, only within two word tokens, and never across `. ! ? , ; :`.

- [x] **Step 2: Write failing negation and double-negation tests**

Assert these invariants:

```python
def test_single_negation_flips_polarity() -> None:
    result = analyze_sentiment("좋지 않다")
    assert result.label == "negative"
    assert result.matches[0].negation_count == 1


def test_double_negation_restores_polarity() -> None:
    result = analyze_sentiment("좋지 않은 것은 아니다")
    assert result.label == "positive"
    assert result.matches[0].negation_count == 2
```

Add tests proving: a negation connects only within two word tokens; punctuation blocks scope; one negation is assigned to the nearest sentiment match only; odd counts flip; even counts preserve; `apply_modifiers=False` returns the unchanged lexicon sum for the same sentences.

- [x] **Step 3: Run the modifier tests and observe failures**

Run: `python -m pytest tests/sentiment/test_modifiers.py -v`

Expected: emphasis and negation expectations fail while base scoring remains green.

- [x] **Step 4: Implement bounded modifier association**

Divide tokens into punctuation-delimited segments. For each sentiment match:

1. Find unclaimed emphasis terms before the match in the same segment with at most two intervening word tokens.
2. Multiply their values and cap the product at `2.0`.
3. Find unclaimed negation terms before or after the match in the same segment with at most two intervening word tokens.
4. Assign each modifier to the closest eligible sentiment match; break equal-distance ties toward the following sentiment expression.
5. Compute `base_score * emphasis_multiplier * (-1) ** negation_count`.

Recompute total score, label, and `mixed` from modified contributions. Preserve match ordering by source offset.

- [x] **Step 5: Run modifier, sentiment, and full tests**

Run: `python -m pytest tests/sentiment/test_modifiers.py -v`

Expected: every modifier scope and parity test passes.

Run: `python -m pytest tests/sentiment -v`

Expected: all sentiment tests pass.

Run: `python -m pytest`

Expected: all current tests pass.

- [x] **Step 6: Commit Task 7**

```bash
git add src/sentiment_engine/sentiment.py tests/sentiment/test_modifiers.py
git commit -m "feat: apply sentiment modifier rules"
```

---

### Task 8: Integrated API and CLI

**Files:**
- Modify: `src/sentiment_engine/__init__.py`
- Create: `src/sentiment_engine/cli.py`
- Create: `main.py`
- Create: `tests/test_integration_cli.py`

**Interfaces:**
- Consumes: `extract_information`, `analyze_sentiment`, all result models.
- Produces: `analyze(text: str) -> AnalysisResult` and `main(argv: Sequence[str] | None = None) -> int` for analysis mode. Evaluation flags are wired in Task 9.

- [x] **Step 1: Write failing integrated API tests**

Analyze one text containing `support@company.co.kr`, `02-1234-5678`, `2024년 3월 15일`, `50,000원`, an HTTPS URL, and `정말 좋지 않다`. Assert all five normalized extraction types appear, sentiment is negative, and top-level diagnostics equal extraction diagnostics. Assert the integrated function has the same input error policy as both analyzers.

- [x] **Step 2: Write failing subprocess CLI tests**

Invoke `sys.executable main.py --text <text> --format json` and assert exit code `0`, parseable UTF-8 JSON, `ensure_ascii=False` behavior, and semantically equal normalized values. Invoke default text mode and assert section labels for extraction and sentiment. Assert these invalid invocations return nonzero and write to stderr:

```text
python main.py
python main.py --text ""
python main.py --text "문장" --evaluate all
python main.py --format xml --text "문장"
```

- [x] **Step 3: Run focused tests and confirm missing API/CLI failures**

Run: `python -m pytest tests/test_integration_cli.py -v`

Expected: failures show missing `analyze`, CLI module, and executable wrapper.

- [x] **Step 4: Implement integrated API and serialization**

`analyze` validates once, calls both public analyzers, and returns:

```python
AnalysisResult(
    text=text,
    extractions=extraction_result.items,
    sentiment=sentiment_result,
    diagnostics=extraction_result.diagnostics,
)
```

Use `dataclasses.asdict` for JSON-compatible output. Emit JSON with `ensure_ascii=False`, `indent=2`, and stable key insertion order.

The JSON top level has exactly `text`, `extractions`, `sentiment`, and `diagnostics`. Each extraction contains `type`, `raw`, `normalized`, `start`, and `end`; a money `normalized` value is an object with `amount` and `currency`. Sentiment contains `score`, `label`, `mixed`, `tokens`, and `matches`. Each diagnostic contains `type`, `raw`, `start`, `end`, and `reason`.

- [x] **Step 5: Implement analysis-mode CLI**

Use an argparse mutually exclusive group for `--text` and `--evaluate`. Define `--evaluate` choices `extraction`, `sentiment`, and `all`, and `--format` choices `text` and `json`. Until Task 9, choosing `--evaluate` must emit `evaluation support is not installed` and return `2`; do not silently accept it.

`main.py` must contain only:

```python
from sentiment_engine.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 6: Run focused and full tests**

Run: `python -m pytest tests/test_integration_cli.py -v`

Expected: integrated API and analysis CLI tests pass.

Run: `python -m pytest`

Expected: all current tests pass.

- [x] **Step 7: Commit Task 8**

```bash
git add main.py src/sentiment_engine tests/test_integration_cli.py
git commit -m "feat: expose integrated API and CLI"
```

---

### Task 9: Evaluation Fixtures, Metrics, and Evaluation CLI

**Files:**
- Create: `src/sentiment_engine/evaluation.py`
- Modify: `src/sentiment_engine/cli.py`
- Create: `tests/fixtures/extraction_cases.json`
- Create: `tests/fixtures/sentiment_cases.json`
- Create: `tests/test_evaluation.py`
- Modify: `tests/test_integration_cli.py`

**Interfaces:**
- Consumes: public extraction and sentiment analyzers.
- Produces: `load_extraction_cases`, `load_sentiment_cases`, `evaluate_extraction`, `evaluate_sentiment`, and operational `--evaluate` modes.

- [x] **Step 1: Define and test fixture schemas**

Use this extraction case shape:

```json
{
  "id": "email-001",
  "text": "문의: user@domain.com",
  "variant": "plain",
  "expected": [
    {
      "type": "email",
      "raw": "user@domain.com",
      "normalized": "user@domain.com",
      "start": 4,
      "end": 19
    }
  ]
}
```

Use this sentiment case shape:

```json
{
  "id": "sentiment-001",
  "text": "응대가 정말 친절해서 만족했다",
  "label": "positive",
  "features": ["emphasis"]
}
```

Tests must reject duplicate IDs, invalid offsets, text/span mismatches, unsupported types or labels, fewer than 50 extraction cases, fewer than 10 cases containing each extraction type, fewer than three forms per extraction type as declared by a top-level `variant` field, and fewer than 100 sentiment cases.

- [x] **Step 2: Create complete fixed evaluation datasets**

Create at least 50 extraction cases. For each of the five types, include at least 10 positive cases spanning at least three declared variants; multi-entity and negative cases may increase the total. Include invalid calendar dates, unsupported phone prefixes, malformed domains, unmarked numbers, URL punctuation, multiple items, and mixed-type sentences.

Include at least these six gold-labeled challenge cases outside the supported syntax so the required failure analysis uses real evaluator FNs: `+82-10-1234-5678`, `공일공-일이삼사-오육칠팔`, `2024.01.15`, `백만원`, `USD 100`, and `www.example.com/path`. Give each its natural normalized value and set `variant` to `challenge-unsupported`; do not expand production scope merely to erase these documented limitations.

Create at least 100 sentiment cases with balanced positive and negative labels. Include at least 15 emphasis cases, 15 single-negation cases, 10 explicit double-negation cases, 10 mixed-polarity cases, and 10 challenge expressions that exercise sarcasm, implied dissatisfaction, or context dependence. Use manually assigned gold labels and tag challenge entries with `features: ["challenge"]`. The challenge set must include these negative examples: `참 잘도 처리했네요`, `최고네요, 벌써 세 번째 고장이에요`, `배송이 빛의 속도네요, 일주일밖에 안 걸렸어요`, `웃음밖에 안 나와요`, `칭찬할 말이 없네요`, `다시 사고 싶지는 않아요`, `이 정도면 괜찮다고 해야 하나요`, `기대를 안 했는데 역시나네요`, `돈이 아깝지 않을 수가 없어요`, and `설명과 다른데 우연이겠죠`. Store dataset provenance in a sibling top-level `metadata` object if using an object wrapper; loaders must return only `cases`.

- [x] **Step 3: Write failing metric unit tests**

For extraction, monkeypatch analyzer outputs to create known `TP=2`, `FP=1`, `FN=1` and assert Precision, Recall, and F1 are each `2/3`. Assert exact matching requires case ID, type, start, end, and normalized value. Verify per-type metrics and micro totals, including zero-denominator output `0.0`.

For sentiment, use a known binary confusion matrix and assert Accuracy, class Precision/Recall/F1, macro F1, and positive-class F1. Assert a `neutral` prediction against binary gold is incorrect. Assert `apply_modifiers` is passed unchanged to `analyze_sentiment`.

- [x] **Step 4: Run evaluation tests and confirm failures**

Run: `python -m pytest tests/test_evaluation.py -v`

Expected: collection or assertions fail because evaluation functions do not exist.

- [x] **Step 5: Implement validated fixture loaders**

Load UTF-8 JSON and enforce every schema and count requirement from Step 1. Recompute `raw` using `text[start:end]` instead of trusting fixture text. Return cases in file order. Raise `ValueError` containing the case ID and violated rule.

- [x] **Step 6: Implement extraction metrics**

Convert gold and predicted items to hashable keys. Money normalized values use `(amount, currency)`; other types use their normalized string. Compute each type and micro totals with:

```python
precision = tp / (tp + fp) if tp + fp else 0.0
recall = tp / (tp + fn) if tp + fn else 0.0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
```

Return raw counts and rounded six-decimal metrics. The top level has `per_type`, `micro`, and `errors`. `per_type` has stable keys `email`, `phone`, `date`, `money`, and `url`; every per-type value and `micro` has `tp`, `fp`, `fn`, `precision`, `recall`, and `f1`. Include ordered `errors` entries for every FP, FN, and normalization mismatch so README analysis can reproduce examples.

- [x] **Step 7: Implement sentiment metrics and rule comparison**

Build a confusion matrix in stable class order `positive`, `negative`, `neutral`. Calculate Accuracy, per-gold-class metrics, macro F1, and positive F1, using `0.0` whenever a metric denominator is zero. Include all three labels in `per_class`, but average `macro_f1` over labels present in gold data so an output-only neutral class does not change binary macro F1. The metric object has `accuracy`, `per_class`, `macro_f1`, `positive_f1`, and `errors`. Return misclassified case IDs with text, expected label, predicted label, score, and matches.

Add a comparison helper that runs the same cases with `apply_modifiers=False` and `True` and returns both metric objects plus numeric deltas.

- [x] **Step 8: Wire evaluation CLI and test all modes**

Resolve default fixtures relative to the repository root. `--evaluate extraction` prints extraction metrics, `sentiment` prints before/after metrics, and `all` prints both. Honor `--format json` for every mode. Configuration or fixture errors go to stderr and return `2`; successful evaluation returns `0`.

Run: `python -m pytest tests/test_evaluation.py tests/test_integration_cli.py -v`

Expected: loader, formula, comparison, and all CLI evaluation tests pass.

- [x] **Step 9: Run complete tests and both evaluations**

Run: `python -m pytest`

Expected: all tests pass.

Run: `python main.py --evaluate all --format json`

Expected: exit `0`; output contains extraction `per_type` and `micro`, plus sentiment `without_modifiers`, `with_modifiers`, and `delta`. The current supported-rule evaluation must expose at least five extraction errors and ten sentiment errors for Task 10 analysis; if it exposes fewer, add more labeled challenge inputs without weakening correct supported-case assertions or implementing excluded bonus behavior.

- [x] **Step 10: Commit Task 9**

```bash
git add src/sentiment_engine/evaluation.py src/sentiment_engine/cli.py tests/fixtures tests/test_evaluation.py tests/test_integration_cli.py
git commit -m "feat: evaluate extraction and sentiment performance"
```

---

### Task 10: README Report and Final Verification

**Files:**
- Create: `README.md`
- Modify: source, data, or tests only if final verification exposes a spec violation

**Interfaces:**
- Consumes: all runnable commands and generated evaluation output.
- Produces: the final repository report required by the mission and rubric.

- [x] **Step 1: Capture fresh reproducible evidence**

Run:

```bash
python -m pytest
python main.py --evaluate extraction --format json
python main.py --evaluate sentiment --format json
python main.py --text "문의: support@company.co.kr, 전화 02-1234-5678, 일시 2024년 3월 15일, 참가비 50,000원. 정말 좋지 않아요." --format json
```

Save no transient output files. Use the terminal results as the source for README values and examples.

- [x] **Step 2: Write installation, architecture, and rule documentation**

README must contain these sections in order:

1. 프로젝트 개요
2. 설치 및 실행 방법
3. 프로젝트 구조와 모듈 책임
4. 데이터 구성과 감성 사전 출처
5. 정규표현식 구조와 정규화 규칙
6. 감성 점수·부정어·강조어·이중부정
7. 평가 방법과 결과
8. 실패 사례 분석
9. 규칙 기반 시스템의 장점과 한계
10. 유지보수 문제와 개선 방향
11. 규칙 기반 방식과 머신러닝 방식 비교

Explain named groups, character classes, quantifiers, and lookarounds for every extraction family. Include the exact sentiment formula, scope distance `2`, emphasis cap `2.0`, odd/even negation policy, neutral threshold, and `mixed` semantics. Cite external lexicon inspiration and license if any non-project source appears in the JSON.

- [x] **Step 3: Insert actual evaluation results and analyzed errors**

Copy the fresh metrics from Step 1 into tables. Explain Precision as false-positive sensitivity and Recall as missed-entity sensitivity. Compare modifier-disabled and modifier-enabled Accuracy/F1.

Select at least five real extraction errors from evaluator output and classify each as FP, FN, or normalization failure. Select at least ten real sentiment misclassifications and classify causes among tokenization, missing lexicon entry, negation scope, emphasis scope, mixed sentiment, context, or sarcasm. For every case, include input, expected output, actual output, cause, and a concrete improvement with its precision/recall or maintenance trade-off.

- [x] **Step 4: Document maintainability and rules-versus-ML analysis**

Explain pattern overlap, lexicon polarity conflicts, empirical scope tuning, and inflection maintenance. Compare rule-based and ML methods by suitable conditions, strengths, weaknesses, and representative use cases. Keep the ML section analytical only; do not implement a model.

- [x] **Step 5: Run the spec-coverage gate**

Check every row in the spec's Section 17 traceability table against a file, test, evaluator result, or README section. Verify these numeric gates directly:

```bash
python -c "import json; d=json.load(open('data/sentiment_lexicon.json', encoding='utf-8')); assert len({x['term'] for x in d}) >= 200; assert sum(x.get('domain') == 'customer_support' for x in d) >= 30"
python -c "import json; d=json.load(open('tests/fixtures/extraction_cases.json', encoding='utf-8')); cases=d['cases'] if isinstance(d, dict) else d; assert len(cases) >= 50"
python -c "import json; d=json.load(open('tests/fixtures/sentiment_cases.json', encoding='utf-8')); cases=d['cases'] if isinstance(d, dict) else d; assert len(cases) >= 100"
```

If a gate fails, fix the responsible task's production code, fixture, or documentation with a failing regression test first, then rerun the full gate.

- [x] **Step 6: Run final verification**

Run: `python -m pytest`

Expected: all tests pass with zero failures.

Run: `python main.py --evaluate all --format json`

Expected: exit `0` with all required extraction and sentiment metric groups.

Run: `git diff --check`

Expected: no whitespace errors.

- [x] **Step 7: Commit Task 10**

```bash
git add README.md
git commit -m "docs: report evaluation and rule analysis"
```

If Step 5 required code or test corrections, stage those exact files with README and describe the corrections in the commit message instead of hiding them under a documentation-only message.

---

## Completion Gate

The implementation is complete only when all Task 1-10 checkboxes are checked, every focused red-green cycle was observed, the full test suite passes, both evaluators run from a clean checkout, README contains actual measured results and required failure analyses, and `git status --short` contains only the intentionally untracked `docs/private/` directory.


## Completion record — 2026-09-05

- Tasks 1–10 implemented; Task 9 and Task 10 reviews approved. Whole-project review found no critical or important issues.
- Final review corrections align the design's `variants` field with the approved list contract and remove an extra test-file EOF blank line.
- Fresh Python 3.12.3 virtualenv installed `requirements.txt` from a `git archive` snapshot independently of the working checkout. All 194 tests passed.
- Both evaluators, deterministic repeated JSON, text output, five-type API/CLI equality, invalid CLI exit code 2, resource and fixture quotas, Python 3.10 syntax parsing, and compileall passed.
- Extraction: TP 57, FP 0, FN 6; precision 1.000000, recall 0.904762, F1 0.950000. Sentiment accuracy 0.430000 → 0.440000; macro F1 0.588357 → 0.602477. README documents the actual six extraction failures and ten sentiment errors.
- Historical Task 9 RED-phase logs were not preserved when the prior session stopped; its completed implementation, green tests, metrics, and independent review were verified on resume. This record does not reconstruct missing historical evidence.
- Work remains on the previously authorized local `main`; no remote push. `docs/private/` remains intentionally untracked and untouched.
