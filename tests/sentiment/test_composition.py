"""Declared local grammar, its counterexamples, and operator ownership."""
import pytest

from sentiment_engine import analyze_sentiment
from sentiment_engine.korean import analyze_morphology
from sentiment_engine.models import SentimentEvent
from sentiment_engine.sentiment_rules import link_modifiers, score_events


def structure(text, heads):
    tokens=analyze_morphology(text)
    events=[]
    for term,score,head in heads:
        start=next(i for i,t in enumerate(tokens) if t.morph==head)
        end=start+1
        if end<len(tokens) and tokens[end].pos in {'XSV','XSA'}:
            end+=1
        events.append(SentimentEvent(term,term,score,start,end,False))
    return tokens,tuple(events)


@pytest.mark.parametrize('word,head,score', [('친절','친절',2),('불편','불편',-2),('훌륭','훌륭',3)])
@pytest.mark.parametrize('template,count,multiplier', [
    ('{}하다',0,1), ('안 {}하다',1,1), ('못 매우 {}하다',1,1.5),
    ('{}하지 않다',1,1), ('{}하지 못했다',1,1), ('{}하지 않은 것은 아니다',2,1),
    ('정말 아주 {}하다',0,2), ('{}하지 않다. 그것은 아니다',1,1),
])
def test_supported_predicate_composition(word,head,score,template,count,multiplier):
    text=template.format(word)
    tokens,events=structure(text,[(word,score,head)])
    links=link_modifiers(text,tokens,events)
    matches=score_events(text,tokens,events,links,apply_modifiers=True)
    assert matches[0].negation_count==count
    assert matches[0].emphasis_multiplier==multiplier
    assert matches[0].contribution==score*multiplier*(-1)**count
    assert all(link.event_index==0 for link in links)
    assert len({(l.modifier_start,l.modifier_end) for l in links})==len(links)


@pytest.mark.parametrize('text,counts', [
    ('불만이 없다',[1]), ('불만이 아니다',[1]), ('불만을 말할 시간이 없다',[0]),
    ('불만이지만 좋지 못하다',[0,1]), ('문제가 없지는 않다',[2]),
    ('불만. 없다',[0]), ('불만\n없다',[0]),
])
def test_nominal_negation_requires_local_grammar(text,counts):
    heads=[('문제',-2,'문제')] if text.startswith('문제') else [('불만',-2,'불만')]
    if '좋지' in text: heads.append(('좋다',2,'좋'))
    tokens,events=structure(text,heads)
    links=link_modifiers(text,tokens,events)
    matches=score_events(text,tokens,events,links,apply_modifiers=True)
    assert [m.negation_count for m in matches]==counts
    assert [(l.event_index,l.kind) for l in links if l.kind=='negation']==[
        (i,'negation') for i,n in enumerate(counts) for _ in range(n)]


@pytest.mark.parametrize('text', ['정말 그렇지만 친절하다', '정말 이 제품도 친절하다',
                                '정말\n친절하다', '안 좋다 친절하다'])
def test_modifiers_do_not_jump_over_unlicensed_structure(text):
    tokens,events=structure(text,[('친절하다',2,'친절')])
    assert link_modifiers(text,tokens,events)==()


def test_modifier_off_preserves_events_and_exact_source_spans():
    text='🙂 정말  친절하지 않은 것은 아니다'
    tokens,events=structure(text,[('친절하다',2,'친절')])
    links=link_modifiers(text,tokens,events)
    on=score_events(text,tokens,events,links,apply_modifiers=True)
    off=score_events(text,tokens,events,links,apply_modifiers=False)
    assert [(m.term,m.raw,m.base_score,m.start,m.end) for m in on]==[
        (m.term,m.raw,m.base_score,m.start,m.end) for m in off]
    assert off[0].contribution==2
    assert on[0].contribution==3
    assert all(text[m.start:m.end]==m.raw for m in on+off)
