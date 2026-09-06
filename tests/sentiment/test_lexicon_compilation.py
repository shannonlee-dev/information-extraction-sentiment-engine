"""Compiler contracts: lexical identity, conflict safety, audit completeness."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def compiler():
    spec = importlib.util.spec_from_file_location('build_sentiment_lexicon', ROOT / 'scripts/build_sentiment_lexicon.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs(tmp_path, rows, *, exclude=()):
    source, annotations = tmp_path / 'source.json', tmp_path / 'annotations.json'
    source.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
    annotations.write_text(json.dumps({'schema_version': 1, 'entries': {
        row['term']: {'decision': 'exclude' if row['term'] in exclude else 'include',
                      'reason': 'test lexical audit', 'atomic': False,
                      'modifier_policy': 'external', 'priority': 0,
                      'review': {'reviewer': 'test', 'date': '2026-09-06'},
                      'surfaces': [{'surface': surface, 'decision': 'include', 'reason': 'lexical form'}
                                   for surface in [row['term'], *row['variants']]]}
        for row in rows}, 'overrides': []}, ensure_ascii=False), encoding='utf-8')
    return source, annotations


def row(term, score=2, variants=(), source='project', domain=None):
    return dict(term=term, score=score, variants=list(variants), source=source, domain=domain)


def compile_small(paths):
    return compiler().compile_lexicon(*paths, minimum_entries=0, minimum_domain=0)


def test_inflections_merge_and_source_order_does_not_select_canonical(tmp_path):
    rows = [row('좋다', variants=['좋아요']), row('좋아요', source='reviewed')]
    first = compile_small(inputs(tmp_path, rows))
    second = compile_small(inputs(tmp_path, list(reversed(rows))))
    assert len(first['entries']) == 1
    assert first['entries'] == second['entries']
    assert first['entries'][0]['sources'] == ['project', 'reviewed']
    assert first['entries'][0]['keys'] == [[['좋', 'VA']]]


def test_conflicting_key_is_excluded_but_independent_alias_survives(tmp_path):
    result = compile_small(inputs(tmp_path, [row('좋다', variants=['훌륭하다']), row('좋아요', -2)]))
    assert len(result['conflicts']) == 1
    assert len(result['entries']) == 1
    assert all(key != [['좋', 'VA']] for entry in result['entries'] for key in entry['keys'])
    assert result['exclusions']


def test_zero_and_reviewed_compositional_exclusions_are_reported(tmp_path):
    result = compile_small(inputs(tmp_path, [row('좋다', 0), row('문제가 해결되다')], exclude=['문제가 해결되다']))
    assert result['entries'] == []
    assert len(result['exclusions']) == 2


@pytest.mark.parametrize('change', ['boolean_score', 'duplicate_term', 'missing_annotation', 'missing_surface', 'bad_domain'])
def test_invalid_inputs_fail(tmp_path, change):
    rows = [row('좋다')]
    if change == 'boolean_score':
        rows[0]['score'] = True
    elif change == 'duplicate_term':
        rows.append(row('좋다'))
    elif change == 'bad_domain':
        rows[0]['domain'] = []
    paths = inputs(tmp_path, rows)
    if change.startswith('missing_'):
        annotations = json.loads(paths[1].read_text())
        if change == 'missing_annotation':
            annotations['entries'] = {}
        else:
            annotations['entries']['좋다']['surfaces'] = []
        paths[1].write_text(json.dumps(annotations))
    with pytest.raises(ValueError):
        compile_small(paths)


def test_minimum_counts_apply_after_merging(tmp_path):
    paths = inputs(tmp_path, [row('좋다', variants=['좋아요']), row('좋아요')])
    with pytest.raises(ValueError, match='canonical'):
        compiler().compile_lexicon(*paths, minimum_entries=2, minimum_domain=0)
    with pytest.raises(ValueError, match='domain'):
        compiler().compile_lexicon(*paths, minimum_entries=0, minimum_domain=1)


def test_lexical_key_preserves_internal_particles_and_derivation():
    from sentiment_engine.korean import analyze_morphology
    module = compiler()
    assert module.lexical_key(analyze_morphology('친절했습니다')) == (('친절', 'NNG'), ('하', 'XSV'))
    assert ('에', 'JKB') in module.lexical_key(analyze_morphology('마음에 들다'))
    assert module.lexical_key(analyze_morphology('훌륭함')) == (('훌륭', 'XR'), ('하', 'XSA'))


def test_checked_in_inventory_and_rebuild_are_reproducible():
    module = compiler()
    result = module.compile_lexicon(ROOT / 'data/sentiment_lexicon.json', ROOT / 'data/lexicon_annotations.json')
    assert len(result['entries']) >= 200
    assert sum(e['domain'] == 'customer_support' and 'project' in e['sources'] for e in result['entries']) >= 30
    assert module.serialize(result) == (ROOT / 'data/sentiment_lexicon_compiled.json').read_text(encoding='utf-8')
    assert not any(e['term'] == '문제가 해결되다' for e in result['entries'])
    assert {'친절하다', '훌륭하다'} <= {e['term'] for e in result['entries']}
