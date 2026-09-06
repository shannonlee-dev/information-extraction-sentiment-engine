import json
from pathlib import Path

import pytest

from scripts.benchmark.artifacts import _sha256
from scripts.benchmark.data import stable_hash
from scripts.prepare_sentiment_workset_v2 import prepare_workset


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True))


@pytest.fixture
def old(tmp_path):
    root = tmp_path / 'v1'
    root.mkdir()
    (root / 'raw.txt').write_text('source')
    groups = []
    for i in range(12):
        rows = [{'id': f'r{i}:{j}', 'text': f'  original {i} {j}  ', 'label': 'positive', 'rating': 5,
                 'source_line': i * 2 + j} for j in range(2)]
        groups.append({'group_id': stable_hash(sorted(r['id'] for r in rows)), 'rows': rows,
                       'exposed': False, 'split': 'reserve' if i < 10 else 'final'})
    path = root / 'groups.jsonl'
    path.write_text(''.join(json.dumps(g, sort_keys=True) + '\n' for g in groups))
    write(root / 'manifest.json', {'format': 1, 'reserve_rows': 20,
                                  'source': {'path': str(root / 'raw.txt'), 'sha256': _sha256(root / 'raw.txt')}})
    write(root / 'release.json', {'files': {str((root / name).resolve()): _sha256(root / name)
                                          for name in ('groups.jsonl', 'manifest.json')}})
    return root


def test_reserve_only_group_isolation_and_unlabeled_schema(old, tmp_path, monkeypatch):
    original = Path.open
    def guard(path, *args, **kwargs):
        assert path.name not in ('selection.inputs.jsonl', 'selection.gold.jsonl', 'final.inputs.jsonl', 'final.gold.jsonl')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guard)
    result = prepare_workset(old, tmp_path / 'work', mining_rows=6, development_rows=4)
    assert result['counts'] == {'mining': 6, 'development': 4, 'untouched': 10}
    groups = [json.loads(line) for line in (tmp_path / 'work/assignments.jsonl').read_text().splitlines()]
    assert len({g['group_id'] for g in groups}) == 10
    mining = [json.loads(line) for line in (tmp_path / 'work/mining.inputs.jsonl').read_text().splitlines()]
    assert all(set(row) == {'id', 'text'} and row['text'].startswith('  original') for row in mining)
    assert not list((tmp_path / 'work').glob('final*'))
    second = prepare_workset(old, tmp_path / 'other', mining_rows=6, development_rows=4)
    assert result['files'] == second['files']


def test_rejects_tampered_old_groups(old, tmp_path):
    with (old / 'groups.jsonl').open('a') as out:
        out.write('\n')
    with pytest.raises(ValueError, match='hash'):
        prepare_workset(old, tmp_path / 'work', mining_rows=6, development_rows=4)


def test_no_overwrite(old, tmp_path):
    out = tmp_path / 'work'
    out.mkdir()
    with pytest.raises(FileExistsError):
        prepare_workset(old, out, mining_rows=6, development_rows=4)
