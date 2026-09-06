import pytest

from sentiment_engine import analyze_sentiment


def test_single_emphasis_multiplies_the_next_sentiment() -> None:
    result = analyze_sentiment("정말 만족")

    assert result.score == 3.0
    assert result.matches[0].emphasis_multiplier == 1.5
    assert result.matches[0].contribution == 3.0


def test_multiple_emphasis_terms_are_capped_at_two() -> None:
    result = analyze_sentiment("정말 아주 만족")

    assert result.score == 4.0
    assert result.matches[0].emphasis_multiplier == 2.0


def test_emphasis_is_claimed_only_by_the_next_sentiment() -> None:
    result = analyze_sentiment("정말 만족 좋다")

    assert [match.emphasis_multiplier for match in result.matches] == [1.5, 1.0]
    assert [match.contribution for match in result.matches] == [3.0, 2.0]


def test_emphasis_does_not_jump_over_unlicensed_nominal_phrase() -> None:
    result = analyze_sentiment("정말 이 제품도 만족")

    assert result.matches[0].emphasis_multiplier == 1.0


def test_emphasis_does_not_cross_three_intervening_word_tokens() -> None:
    result = analyze_sentiment("정말 이 제품도 오늘도 만족")

    assert result.matches[0].emphasis_multiplier == 1.0


def test_emphasis_after_sentiment_does_not_apply() -> None:
    result = analyze_sentiment("만족 정말")

    assert result.matches[0].emphasis_multiplier == 1.0


@pytest.mark.parametrize("boundary", [".", "!", "?", ",", ";", ":"])
def test_punctuation_blocks_emphasis_scope(boundary: str) -> None:
    result = analyze_sentiment(f"정말{boundary} 만족")

    assert result.matches[0].emphasis_multiplier == 1.0


def test_single_negation_flips_polarity() -> None:
    result = analyze_sentiment("좋지 않다")

    assert result.label == "negative"
    assert result.matches[0].negation_count == 1
    assert result.matches[0].contribution == -2.0


def test_double_negation_restores_polarity() -> None:
    result = analyze_sentiment("좋지 않은 것은 아니다")

    assert result.label == "positive"
    assert result.matches[0].negation_count == 2
    assert result.matches[0].contribution == 2.0


def test_negation_does_not_link_an_unrelated_copula_by_distance() -> None:
    result = analyze_sentiment("좋지 이 제품은 아니다")

    assert result.matches[0].negation_count == 0


def test_negation_does_not_cross_three_intervening_word_tokens() -> None:
    result = analyze_sentiment("좋지 이 제품은 오늘도 아니다")

    assert result.matches[0].negation_count == 0


@pytest.mark.parametrize("boundary", [".", "!", "?", ",", ";", ":"])
def test_punctuation_blocks_negation_scope(boundary: str) -> None:
    result = analyze_sentiment(f"좋지{boundary} 않다")

    assert result.label == "positive"
    assert result.matches[0].negation_count == 0


def test_nominal_negation_is_claimed_by_its_grammatical_owner() -> None:
    result = analyze_sentiment("불만이 아니다 오늘 나쁘다")

    assert [match.negation_count for match in result.matches] == [1, 0]
    assert [match.contribution for match in result.matches] == [2.0, -2.0]


def test_disconnected_copula_does_not_choose_a_nearby_predicate() -> None:
    result = analyze_sentiment("좋다 아니다 나쁘다")

    assert [match.negation_count for match in result.matches] == [0, 0]
    assert [match.contribution for match in result.matches] == [2.0, -2.0]


@pytest.mark.parametrize("text", ["좋지 않다", "좋지 않은 것은 아니다"])
def test_disabled_modifiers_preserve_the_lexicon_sum(text: str) -> None:
    result = analyze_sentiment(text, apply_modifiers=False)

    assert result.score == 2.0
    assert result.label == "positive"
    assert result.matches[0].emphasis_multiplier == 1.0
    assert result.matches[0].negation_count == 0


def test_modified_contributions_recompute_mixed() -> None:
    result = analyze_sentiment("좋다 불만이 아니다")

    assert result.score == 4.0
    assert result.label == "positive"
    assert result.mixed is False


def test_cli_modifier_variant_preserves_sentiment_source_span() -> None:
    text = "정말 좋지 않아요"
    result = analyze_sentiment(text)

    assert result.score == -3.0
    assert result.label == "negative"
    assert result.matches[0].emphasis_multiplier == 1.5
    assert result.matches[0].negation_count == 1
    assert text[result.matches[0].start : result.matches[0].end] == result.matches[0].raw
