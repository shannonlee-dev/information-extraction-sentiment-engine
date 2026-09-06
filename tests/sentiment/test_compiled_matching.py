from sentiment_engine.models import MorphToken, LexicalEntry
from sentiment_engine.sentiment import find_events


def entry(term, key, score=2, priority=0):
    return LexicalEntry(term, term, score, None, ('project',), False, priority, (tuple(key),))


def test_longest_key_claims_one_event_and_keeps_internal_particles():
    tokens = (MorphToken('마음','NNG',0,2,0),MorphToken('에','JKB',2,3,0),MorphToken('들','VV',4,5,1))
    entries = (entry('마음', [('마음','NNG')]),entry('마음에 들다',[('마음','NNG'),('에','JKB'),('들','VV')]))
    events = find_events(tokens, entries)
    assert [(e.term,e.token_start,e.token_end) for e in events] == [('마음에 들다',0,3)]


def test_noun_compounds_and_unrelated_verb_are_not_noun_sentiment():
    lexicon=(entry('피해',[('피해','NNG')],-2),entry('문제',[('문제','NNG')],-2))
    for tokens in ((MorphToken('피하','VV',0,2,0),),
                   (MorphToken('문제','NNG',0,2,0),MorphToken('집','NNG',2,3,0))):
        assert find_events(tokens,lexicon)==()


def test_tie_is_priority_then_canonical_id_not_file_order():
    token=(MorphToken('좋','VA',0,1,0),)
    a=entry('a',[('좋','VA')]); b=entry('b',[('좋','VA')],priority=10)
    assert find_events(token,(a,b))==find_events(token,(b,a))
    assert find_events(token,(a,b))[0].canonical_id=='b'


def test_lexical_key_does_not_join_across_a_line_break():
    tokens=(MorphToken('마음','NNG',0,2,0), MorphToken('에','JKB',2,3,0),
            MorphToken('\n','BOUNDARY',3,4,0),MorphToken('들','VV',4,5,1))
    assert find_events(tokens,(entry('마음에 들다',[('마음','NNG'),('에','JKB'),('들','VV')]),))==()


def test_runtime_rejects_model_or_source_mismatch_before_loading_entries(tmp_path,monkeypatch):
    import hashlib,json
    import pytest
    from sentiment_engine import sentiment
    source=tmp_path/'source.json'; source.write_text('[]')
    annotations=tmp_path/'annotations.json'; annotations.write_text('{}')
    fingerprint={'model':'original'}
    monkeypatch.setattr(sentiment,'analyzer_fingerprint',lambda:fingerprint)
    artifact={'schema_version':1,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'annotations_sha256':hashlib.sha256(annotations.read_bytes()).hexdigest(),
              'analyzer':{'model':'different'},'entries':[]}
    compiled=tmp_path/'compiled.json'; compiled.write_text(json.dumps(artifact))
    with pytest.raises(ValueError,match='analyzer/model hash mismatch'):
        sentiment._load_compiled(compiled,source,annotations)
    source.write_text('[1]')
    with pytest.raises(ValueError,match='source_sha256 mismatch'):
        sentiment._load_compiled(compiled,source,annotations)


def test_runtime_rejects_insufficient_compiled_inventory(tmp_path,monkeypatch):
    import hashlib,json
    import pytest
    from sentiment_engine import sentiment
    source=tmp_path/'source'; source.write_text('[]')
    annotations=tmp_path/'annotations'; annotations.write_text('{}')
    monkeypatch.setattr(sentiment,'analyzer_fingerprint',lambda:{})
    artifact={'schema_version':1,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'annotations_sha256':hashlib.sha256(annotations.read_bytes()).hexdigest(),'analyzer':{},'entries':[]}
    compiled=tmp_path/'compiled'; compiled.write_text(json.dumps(artifact))
    with pytest.raises(ValueError,match='200 canonical'):
        sentiment._load_compiled(compiled,source,annotations)
