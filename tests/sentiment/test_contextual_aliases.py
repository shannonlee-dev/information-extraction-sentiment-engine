import json

import pytest

from scripts.build_sentiment_lexicon import compile_lexicon
from sentiment_engine.korean import analyze_morphology


def fixture(tmp_path, start):
    source=tmp_path/'source.json'; audit=tmp_path/'audit.json'
    source.write_text(json.dumps([{'term':'늦다','variants':[],'score':-2,'domain':None,'source':'project'}]))
    audit.write_text(json.dumps({'schema_version':1,'overrides':[],'entries':{'늦다':{
        'decision':'include','atomic':False,'priority':0,'modifier_policy':'external','reason':'same lateness sense',
        'review':{'reviewer':'test','date':'2026-09-06'},
        'surfaces':[{'surface':'늦다','decision':'include','reason':'lateness adjective'}],
        'aliases':[{'context':'너무늦어서','token_start':start,'key':[['늦','VV']],
                    'reason':'same lateness predicate tagged VV after unspaced intensifier'}]}}}))
    return source,audit


def test_offset_alias_must_match_the_recorded_morphology(tmp_path):
    tokens=analyze_morphology('너무늦어서')
    assert [(t.morph,t.pos) for t in tokens]==[('너무','MAG'),('늦','VV'),('어서','EC')]
    result=compile_lexicon(*fixture(tmp_path,1),minimum_entries=0,minimum_domain=0)
    assert [['늦','VV']] in result['entries'][0]['keys']
    assert [['늦','VA']] in result['entries'][0]['keys']


@pytest.mark.parametrize('start',[-1,0,2,10,True,'1'])
def test_invalid_offset_alias_fails_closed(tmp_path,start):
    with pytest.raises(ValueError,match='alias'):
        compile_lexicon(*fixture(tmp_path,start),minimum_entries=0,minimum_domain=0)
