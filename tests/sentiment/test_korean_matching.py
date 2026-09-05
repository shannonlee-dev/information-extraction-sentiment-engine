"""Behavioral regressions for Korean inflections and negation attachment."""

import pytest

from sentiment_engine import analyze_sentiment


@pytest.mark.parametrize("text, label", [
    ("상담이 친절했습니다", "positive"),
    ("어제보다 좋아졌다는 말 대신 좋았다고만 하겠습니다", "positive"),
    ("이 기능을 추천합니다", "positive"),
    ("침구가 부드러웠어요", "positive"),
    ("진행이 빠르고 정확합니다", "positive"),
    ("마감이 깔끔했지만 무겁습니다", "positive"),
    ("음식이 맛있지 않았어요", "negative"),
    ("응답이 느렸습니다", "negative"),
    ("고장으로 접수했습니다", "negative"),
    ("불만족스럽다", "negative"),
    ("품질에 불만이 있습니다", "negative"),
    ("절차가 간편하고 직원이 성실합니다", "positive"),
    ("선물이 예뻤습니다", "positive"),
])
def test_inflections_keep_polarity_and_exact_source_spans(text, label):
    result = analyze_sentiment(text)
    assert result.label == label
    assert result.matches
    assert all(text[m.start:m.end] == m.raw for m in result.matches)
    assert all(a.end <= b.start for a, b in zip(result.matches, result.matches[1:]))


@pytest.mark.parametrize("text", [
    "고장난감이라는 새 단어", "문제집을 펼쳤다", "최고기온은 삼십도",
    "불만족도조사지를 출력했다", "만족도표를 인쇄했다", "추천서류를 보냈다",
    "오늘은 수요일이다", "안내문을 읽었다", "아니마를 검색했다",
])
def test_matching_does_not_treat_arbitrary_substrings_as_sentiment(text):
    assert analyze_sentiment(text).label == "neutral"


@pytest.mark.parametrize("text, contributions, counts", [
    ("나쁘지 않다 좋다", [2.0, 2.0], [1, 0]),
    ("좋다 안 나쁘다", [2.0, 2.0], [0, 1]),
    ("안 좋다 나쁘다", [-2.0, -2.0], [1, 0]),
    ("불편하지 않았지만 친절하다", [2.0, 2.0], [1, 0]),
    ("만족하지 않는 것은 아니다", [2.0], [2]),
    ("문제가 없지는 않다", [-2.0], [2]),
    ("좋지 않다 그런데 불편하다", [-2.0, -2.0], [1, 0]),
    ("해결 안 됨", [-3.0], [0]),
    ("맘에 안 들어", [-2.0], [0]),
    ("피해 없어", [1.0], [0]),
    ("문제가 해결되었다", [2.0], [0]),
])
def test_negations_attach_to_their_predicate_once(text, contributions, counts):
    result = analyze_sentiment(text)
    assert [m.contribution for m in result.matches] == contributions
    assert [m.negation_count for m in result.matches] == counts


def test_emphasis_and_negation_use_the_same_inflected_predicate():
    result = analyze_sentiment("정말 유용하지 않았습니다")
    assert result.score == -3.0
    assert result.matches[0].emphasis_multiplier == 1.5
    assert result.matches[0].negation_count == 1


def test_disabled_modifiers_keep_inflection_matching():
    result = analyze_sentiment("정말 유용하지 않았습니다", apply_modifiers=False)
    assert result.score == 2.0


def test_multiword_inflection_preserves_whitespace_and_avoids_double_counting():
    text = "문제가  \t해결되었습니다"
    result = analyze_sentiment(text)
    assert result.label == "positive"
    assert len(result.matches) == 1
    assert result.matches[0].raw == text


def test_reported_predicate_can_be_negated_by_cannot_say():
    assert analyze_sentiment("정확하다고 못 하겠습니다").label == "negative"


def test_contrast_blocks_auxiliary_chain_and_emphasis():
    assert analyze_sentiment("좋지 않지만 아니다").matches[0].negation_count == 1
    assert analyze_sentiment("정말 그렇지만 좋다").score == 2.0


def test_negation_inflected_with_clause_ending():
    assert analyze_sentiment("좋지 않은데요").label == "negative"


@pytest.mark.parametrize("text", [
    "좋지 못하다", "만족하지 못했다", "문제가 해결되지 못했습니다",
    "만족 못해요", "만족 안 해요",
])
def test_postposed_inability_and_nominal_negation_are_negative(text):
    result = analyze_sentiment(text)
    assert result.label == "negative"
    assert result.matches[0].negation_count == 1


@pytest.mark.parametrize("text", ["햇빛을 피했다", "햇빛을 피했습니다", "모자를 벗고 햇빛을 피했어요"])
def test_noun_ending_hae_is_not_conjugated_into_an_unrelated_verb(text):
    assert analyze_sentiment(text).label == "neutral"
