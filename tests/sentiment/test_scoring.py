import pytest

from sentiment_engine import analyze_sentiment


def test_base_positive_score() -> None:
    result = analyze_sentiment("서비스가 친절하고 훌륭하다", apply_modifiers=False)

    assert result.score == 5.0
    assert result.label == "positive"
    assert result.mixed is False
    assert result.tokens == ["서비스가", "친절하고", "훌륭하다"]
    assert [
        (
            match.term,
            match.raw,
            match.base_score,
            match.emphasis_multiplier,
            match.negation_count,
            match.contribution,
        )
        for match in result.matches
    ] == [
        ("친절하다", "친절하고", 2, 1.0, 0, 2.0),
        ("훌륭하다", "훌륭하다", 3, 1.0, 0, 3.0),
    ]


def test_base_negative_score() -> None:
    result = analyze_sentiment("배송이 느리고 응대도 불친절하다", apply_modifiers=False)

    assert result.score < 0
    assert result.label == "negative"
    assert result.mixed is False


def test_base_mixed_score_exposes_diagnostic() -> None:
    result = analyze_sentiment("품질은 좋지만 배송은 느리다", apply_modifiers=False)

    assert result.mixed is True
    assert {match.contribution > 0 for match in result.matches} == {True, False}


def test_exact_zero_score_is_neutral() -> None:
    result = analyze_sentiment("품질은 좋지만 배송은 느리다", apply_modifiers=False)

    assert result.score == 0.0
    assert result.label == "neutral"


def test_no_match_is_neutral() -> None:
    result = analyze_sentiment("오늘은 수요일이다.", apply_modifiers=False)

    assert result.score == 0.0
    assert result.label == "neutral"
    assert result.mixed is False
    assert result.matches == []
    assert result.tokens == ["오늘은", "수요일이다", "."]


@pytest.mark.parametrize("text", [None, 123, ["좋다"]])
def test_non_string_input_is_rejected(text: object) -> None:
    with pytest.raises(TypeError):
        analyze_sentiment(text)  # type: ignore[arg-type]


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_empty_or_whitespace_only_input_is_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        analyze_sentiment(text)


def test_disabled_modifiers_do_not_load_modifier_data(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("modifier data was loaded")

    monkeypatch.setattr("sentiment_engine.sentiment._load_modifiers", fail_if_called)

    result = analyze_sentiment("좋다", apply_modifiers=False)

    assert result.score == 2.0


def test_enabled_modifiers_preserve_base_scoring_until_modifier_support() -> None:
    result = analyze_sentiment("매우 좋다")

    assert result.score == 2.0
    assert result.matches[0].emphasis_multiplier == 1.0
