import json
from pathlib import Path

import pytest

from scripts.benchmark.artifacts import _sha256
from scripts.run_m2_development import run_development


def test_development_run_is_frozen_and_never_opens_holdout(tmp_path, monkeypatch):
    work = tmp_path / 'work'
    work.mkdir()
    rows = [{'id': '1', 'text': '좋다'}, {'id': '2', 'text': '나쁘다'}]
    gold = [{'id': '1', 'label': 'positive', 'group_id': 'g1'}, {'id': '2', 'label': 'negative', 'group_id': 'g2'}]
    for kind, data in [('inputs', rows), ('gold', gold)]:
        (work / f'development.{kind}.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in data))
    manifest = {'counts': {'development': 2}, 'files': {p.name: _sha256(p) for p in work.iterdir()}}
    (work / 'manifest.json').write_text(json.dumps(manifest))
    original = Path.open
    def guard(path, *args, **kwargs):
        assert path.name not in ('selection.inputs.jsonl', 'selection.gold.jsonl', 'final.inputs.jsonl', 'final.gold.jsonl')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guard)
    report = run_development(work, tmp_path / 'out')
    assert report['metrics']['accuracy'] == 1
    assert report['independent_final_evaluation'] is False
    assert report['sampled_errors'] == {bucket: [] for bucket in 'ABCDEF'}
    with pytest.raises(ValueError, match='exists'):
        run_development(work, tmp_path / 'out')
