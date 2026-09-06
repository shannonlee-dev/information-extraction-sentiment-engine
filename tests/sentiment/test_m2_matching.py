import pytest

from sentiment_engine import analyze_sentiment
from sentiment_engine.korean import analyze_morphology
from sentiment_engine.sentiment import find_events


@pytest.mark.parametrize('text,label,term', [('배송빠르다','positive','빠르다'),
 ('촉감부드럽다','positive','부드럽다'),('재질거칠다','negative','거칠다'),
 ('포장꼼꼼하다','positive','꼼꼼하다'),('상태불량하다','negative','불량')])
def test_unspaced_noun_predicate_keeps_evaluative_predicate(text,label,term):
    result=analyze_sentiment(text)
    assert result.label==label
    assert any(m.term==term for m in result.matches)
    plain=analyze_sentiment(text,False)
    assert [(m.term,m.start,m.end) for m in result.matches]==[(m.term,m.start,m.end) for m in plain.matches]
    for m in result.matches:assert text[m.start:m.end]==m.raw


@pytest.mark.parametrize('text', ['문제집','추천서','불량률','무관심'])
def test_compound_nouns_do_not_gain_partial_events(text):
    tokens=analyze_morphology(text)
    # Some lexicalized full forms can be evaluative; partial leaf nouns cannot.
    events=find_events(tokens,text=text)
    assert not any(e.term in {'문제','추천하다','불량','만족'} for e in events)


def test_derivational_negative_prefix_is_not_positive_suffix():
    assert analyze_sentiment('불친절하다').label=='negative'
    assert analyze_sentiment('불만족스럽다').label=='negative'


@pytest.mark.parametrize('text,label', [
    ('좋아서', 'positive'), ('배송빠르고', 'positive'), ('맛없고', 'negative'),
    ('괜찮아요', 'positive'), ('이뻐요', 'positive'), ('배송빠르구', 'positive'),
    ('색상예쁘고', 'positive'), ('맛없구', 'negative'),
    ('제품불량입니다', 'negative'), ('물건불량이고', 'negative'),
    ('품질최악이에요', 'negative'), ('포장엉망이에요', 'negative'),
])
def test_unspaced_predicates_keep_conjugation_and_copula(text, label):
    result = analyze_sentiment(text)
    assert result.label == label
    plain = analyze_sentiment(text, False)
    assert len(result.matches) == 1
    assert [(m.term, m.start, m.end) for m in result.matches] == [
        (m.term, m.start, m.end) for m in plain.matches]
    assert all(text[m.start:m.end] == m.raw for m in result.matches)


@pytest.mark.parametrize('text', ['행복주택입니다', '불만접수입니다', '문제집이고', '추천서예요'])
def test_copula_does_not_unblock_sentiment_inside_compound_noun(text):
    assert analyze_sentiment(text).label == 'neutral'


def test_copula_does_not_unblock_a_bound_negative_prefix():
    from sentiment_engine.models import LexicalEntry, MorphToken
    tokens = (MorphToken('불', 'XPN', 0, 1, 0), MorphToken('만족', 'NNG', 1, 3, 0),
              MorphToken('이', 'VCP', 3, 4, 0), MorphToken('다', 'EF', 4, 5, 0))
    entry = LexicalEntry('positive', '만족', 2, None, ('project',), False, 0,
                         ((('만족', 'NNG'), ('이', 'VCP')),))
    assert find_events(tokens, (entry,)) == ()


@pytest.mark.parametrize('text,label', [
    ('걱정했는데', 'negative'), ('걱정하지 않아요', 'positive'),
    ('안심하고', 'positive'), ('안심하지 못했어요', 'negative'),
    ('누락되어', 'negative'), ('누락되지 않았어요', 'positive'),
    ('지연되었어요', 'negative'), ('재구매합니다', 'positive'),
    ('괜찮아', 'positive'), ('괜찮아요~', 'positive'),
    ('예뻐요~', 'positive'), ('구려요.', 'negative'), ('비려요.', 'negative'),
    ('문제네요', 'negative'), ('최악이예요', 'negative'),
])
def test_audited_existing_lexemes_keep_predicate_pos_and_inflections(text, label):
    result = analyze_sentiment(text)
    assert result.label == label
    assert len(result.matches) == 1
    assert all(text[m.start:m.end] == m.raw for m in result.matches)


@pytest.mark.parametrize('text,label', [
    ('좋내요', 'positive'), ('비리고', 'negative'), ('비리구요', 'negative'),
    ('최고네요', 'positive'), ('대만족입니다', 'positive'), ('대만족이에요', 'positive'),
    ('만족합니당', 'positive'), ('감사합니당', 'positive'), ('추천합니당', 'positive'),
    ('예뻐용', 'positive'), ('별롭니다', 'negative'), ('별롭니다.', 'negative'),
    ('별론데', 'negative'), ('불편하네', 'negative'), ('불편하네여', 'negative'),
])
def test_existing_predicates_with_audited_pos_and_colloquial_endings(text, label):
    result = analyze_sentiment(text)
    assert result.label == label
    assert len(result.matches) == 1
    plain = analyze_sentiment(text, False)
    assert [(m.term, m.start, m.end) for m in result.matches] == [
        (m.term, m.start, m.end) for m in plain.matches]
    assert all(text[m.start:m.end] == m.raw for m in result.matches)


@pytest.mark.parametrize('text', ['별', '별점', '종류별로', '색상별로', '감사원', '만족지수', '비리사건'])
def test_colloquial_aliases_do_not_promote_shared_nouns_or_suffixes(text):
    assert analyze_sentiment(text).label == 'neutral'


def test_colloquial_ending_does_not_drop_negative_lexical_prefix():
    assert not any(m.term == '만족' for m in analyze_sentiment('불만족합니당').matches)
