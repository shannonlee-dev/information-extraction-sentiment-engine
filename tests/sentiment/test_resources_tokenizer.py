import json
from pathlib import Path
from types import MappingProxyType

import pytest

from sentiment_engine.sentiment import (
    _LexiconEntry,
    _find_sentiment_matches,
    _load_lexicon,
    _load_modifiers,
    _tokenize,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LEXICON_PATH = REPOSITORY_ROOT / "data" / "sentiment_lexicon.json"
MODIFIERS_PATH = REPOSITORY_ROOT / "data" / "modifiers.json"


def _valid_entries(count: int = 200, customer_support_count: int = 30) -> list[dict[str, object]]:
    return [
        {
            "term": f"term{index}",
            "variants": [f"variant{index}"],
            "score": 1,
            "domain": "customer_support" if index < customer_support_count else None,
            "source": "project",
        }
        for index in range(count)
    ]


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


def _valid_modifiers() -> dict[str, object]:
    return {
        "negations": [{"term": "않다", "variants": ["않아"]}],
        "emphasizers": [{"term": "매우", "variants": [], "multiplier": 1.5}],
    }


def test_committed_lexicon_has_required_inventory_and_schema() -> None:
    """Removing required coverage or a valid score/schema from resources is rejected."""
    entries = json.loads(LEXICON_PATH.read_text(encoding="utf-8"))

    assert len({entry["term"] for entry in entries}) >= 200
    assert sum(entry.get("domain") == "customer_support" for entry in entries) >= 30
    assert all(
        isinstance(entry["score"], int) and entry["score"] in {-3, -2, -1, 1, 2, 3}
        for entry in entries
    )
    assert all(
        isinstance(entry["term"], str)
        and entry["term"]
        and isinstance(entry["variants"], list)
        and isinstance(entry["source"], str)
        and entry["source"]
        and ("domain" not in entry or entry["domain"] is None or isinstance(entry["domain"], str))
        for entry in entries
    )


def test_lexicon_rejects_duplicate_term_before_inventory_count(tmp_path: Path) -> None:
    """A second canonical term must not silently overwrite the first entry."""
    entries = _valid_entries()
    entries[1]["term"] = entries[0]["term"]

    with pytest.raises(ValueError, match="duplicate sentiment term"):
        _load_lexicon(_write_json(tmp_path / "lexicon.json", entries))


def test_lexicon_rejects_conflicting_variant_surface(tmp_path: Path) -> None:
    """A surface form cannot resolve to two different sentiment entries."""
    entries = _valid_entries()
    entries[1]["variants"] = [entries[0]["variants"][0]]

    with pytest.raises(ValueError, match="conflicting sentiment surface"):
        _load_lexicon(_write_json(tmp_path / "lexicon.json", entries))


def test_lexicon_rejects_zero_score(tmp_path: Path) -> None:
    """Neutral scores would make a sentiment entry meaningless."""
    entries = _valid_entries()
    entries[0]["score"] = 0

    with pytest.raises(ValueError, match="invalid sentiment score"):
        _load_lexicon(_write_json(tmp_path / "lexicon.json", entries))


def test_lexicon_rejects_insufficient_inventory(tmp_path: Path) -> None:
    """A small lexicon does not meet the project coverage floor."""
    with pytest.raises(ValueError, match="sentiment lexicon requires at least 200 terms"):
        _load_lexicon(_write_json(tmp_path / "lexicon.json", _valid_entries(199)))


def test_lexicon_rejects_insufficient_customer_support_inventory(tmp_path: Path) -> None:
    """Domain coverage has its own independent minimum."""
    with pytest.raises(ValueError, match="sentiment lexicon requires at least 30 domain terms"):
        _load_lexicon(_write_json(tmp_path / "lexicon.json", _valid_entries(customer_support_count=29)))


@pytest.mark.parametrize("multiplier", [1.0, 2.1])
def test_modifiers_reject_out_of_range_emphasis_multiplier(
    tmp_path: Path, multiplier: float
) -> None:
    """Emphasis factors must amplify without exceeding the capped range."""
    modifiers = _valid_modifiers()
    modifiers["emphasizers"][0]["multiplier"] = multiplier

    with pytest.raises(ValueError, match="invalid emphasis multiplier"):
        _load_modifiers(_write_json(tmp_path / "modifiers.json", modifiers))


@pytest.mark.parametrize(
    ("group", "field"), [("negations", "term"), ("emphasizers", "variants")]
)
def test_modifiers_reject_duplicate_terms_and_variants(
    tmp_path: Path, group: str, field: str
) -> None:
    """Duplicate modifier surfaces must not make modifier lookup ambiguous."""
    modifiers = _valid_modifiers()
    if field == "term":
        modifiers[group].append({"term": "않다", "variants": []})
    else:
        modifiers[group].append({"term": "아주", "variants": ["매우"], "multiplier": 1.5})

    with pytest.raises(ValueError, match="duplicate modifier term"):
        _load_modifiers(_write_json(tmp_path / "modifiers.json", modifiers))


def test_committed_modifiers_load_with_valid_emphasis_ranges() -> None:
    """The shipped modifier resource satisfies loader validation."""
    modifiers = _load_modifiers(MODIFIERS_PATH)

    assert modifiers["emphasizers"]["매우"].multiplier == 1.5


def test_tokenize_keeps_korean_words_and_sentence_boundaries() -> None:
    """Dropping Korean words or boundary punctuation would lose sentiment context."""
    tokens = _tokenize("배송이 정말 빠르다! 응대는 좋지 않다.")

    assert [token.text for token in tokens] == [
        "배송이", "정말", "빠르다", "!", "응대는", "좋지", "않다", "."
    ]
    assert [token.raw for token in tokens] == [
        "배송이", "정말", "빠르다", "!", "응대는", "좋지", "않다", "."
    ]
    assert [token.is_boundary for token in tokens] == [False, False, False, True, False, False, False, True]


def test_longest_sentiment_expression_claims_overlapping_span() -> None:
    """Emitting the shorter prefix as well would double-count a phrase sentiment."""
    lexicon = MappingProxyType(
        {
            "마음": _LexiconEntry("마음", 1, None),
            "마음에 들다": _LexiconEntry("마음에 들다", 3, None),
        }
    )

    matches = _find_sentiment_matches(_tokenize("이 디자인은 마음에 들다."), lexicon)

    assert [(match.entry.term, match.raw) for match in matches] == [("마음에 들다", "마음에 들다")]
