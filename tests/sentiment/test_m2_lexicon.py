import pytest

from sentiment_engine import analyze_sentiment


@pytest.mark.parametrize('text,label', [('이뻐요','positive'),('조아요','positive'),('굿굿','positive'),
 ('강추','positive'),('재구매','positive'),('별루네요','negative'),('비추천','negative'),
 ('맛없어요','negative'),('귀찮아요','negative'),('부러졌어요','negative'),('불량품','negative'),
 ('어이없어요','negative'),('맘에들어요','positive'),('좋아서','positive')])
def test_audited_colloquial_inflection_and_domain_lexemes(text,label):
    result=analyze_sentiment(text)
    assert result.label==label
    plain=analyze_sentiment(text,apply_modifiers=False)
    assert [(m.term,m.start,m.end) for m in result.matches]==[(m.term,m.start,m.end) for m in plain.matches]
    for match in result.matches:
        assert text[match.start:match.end]==match.raw


@pytest.mark.parametrize('text', ['제품 구매','환불 접수','교환 신청','배송 안내','크다','작다','길다','짧다','얇다','두껍다','연필 공책'])
def test_description_and_transaction_are_not_standalone_sentiment(text):
    assert analyze_sentiment(text).label=='neutral'


@pytest.mark.parametrize('text,label', [('안돼요','negative'),('안 되네요','negative'),('잘돼요','positive'),
 ('그저 그래요','negative'),('어처구니가 없다','negative'),('안심','positive'),('비추입니다','negative'),
 ('짜증남','negative'),('아쉬움','negative'),('찝찝해요','negative'),('마음에 들어용','positive')])
def test_audited_failure_idioms_and_nominal_realizations(text,label):
    assert analyze_sentiment(text).label==label


@pytest.mark.parametrize('text', ['그냥','그렇다','하자','하다','비추는 빛','추하다'])
def test_aliases_do_not_promote_ambiguous_fragments(text):
    # 추하다 is a genuinely negative adjective, but never a positive 강추 alias.
    result=analyze_sentiment(text)
    assert not any(m.term in {'하자','강추','그저 그렇다','그냥 그렇다','비추'} for m in result.matches)


@pytest.mark.parametrize('text,label', [('잘못되었어요','negative'),('약해요','negative'),('심하네요','negative'),
 ('비추합니다','negative'),('고장남','negative'),('불량이예요','negative'),('실망이예요','negative'),
 ('헐렁해요','negative'),('엉망진창','negative'),('불호','negative'),('먹통입니다','negative'),
 ('뒤틀렸어요','negative'),('사기입니다','negative'),('쓰레기입니다','negative'),
 ('아쉽네요ㅠ','negative'),('안되','negative'),('비추요','negative')])
def test_negative_mining_audit_batch3(text,label):
    result=analyze_sentiment(text)
    assert result.label==label
    plain=analyze_sentiment(text,False)
    assert [(m.term,m.start,m.end) for m in result.matches]==[(m.term,m.start,m.end) for m in plain.matches]
    assert all(text[m.start:m.end]==m.raw for m in result.matches)


@pytest.mark.parametrize('text,label', [('그럭저럭','neutral'),('쏘쏘','neutral'),('쓰레기통','neutral'),
 ('쓰레기 봉투','neutral'),('사기가 높다','neutral'),('빛을 비추다','neutral'),('아이를 안다','neutral'),
 ('헐렁하고 편하다','positive'),('약한 향이 좋다','positive'),('잘못이 없다','positive')])
def test_negative_alias_polysemy_and_counterexamples(text,label):
    assert analyze_sentiment(text).label==label
