"""Create development/mining worksets from authenticated old reserve groups only.

Never opens old selection/final files. Their group JSON lines stay opaque bytes.
No new holdout is created. Existing evaluation infrastructure is unchanged.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from scripts.benchmark.artifacts import _sha256
from scripts.benchmark.data import stable_hash

BASELINE = '0c25c75145f308a572083702f51f3e238169bb42'
_SPLIT = re.compile(rb', "split": "(reserve|development|selection|final)"}\s*$')
_GROUP = re.compile(rb'"group_id": "([0-9a-f]{64})"')


def _write_rows(path, rows):
    with path.open('x', encoding='utf-8') as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')


def prepare_workset(old: Path, output: Path, *, mining_rows=40000, development_rows=10000, seed=20260906):
    old, output = old.resolve(), output.resolve()
    if output.exists():
        raise FileExistsError('workset output already exists')
    if min(mining_rows, development_rows) <= 0:
        raise ValueError('workset sizes must be positive')
    manifest = json.loads((old / 'manifest.json').read_bytes())
    release = json.loads((old / 'release.json').read_bytes())
    for name in ('manifest.json', 'groups.jsonl'):
        expected = release['files'].get(str(old / name))
        if not expected or _sha256(old / name) != expected:
            raise ValueError(f'old v1 frozen hash mismatch: {name}')
    source = Path(manifest['source']['path']).resolve()
    if _sha256(source) != manifest['source']['sha256']:
        raise ValueError('old source hash mismatch')
    groups, nonreserve, seen = [], set(), set()
    with (old / 'groups.jsonl').open('rb') as stream:
        for line in stream:
            split, identifier = _SPLIT.search(line), _GROUP.search(line)
            if not split or not identifier:
                raise ValueError('old groups require canonical v1 serialization')
            group_id = identifier[1].decode('ascii')
            if group_id in seen:
                raise ValueError('duplicate old group')
            seen.add(group_id)
            if split[1] != b'reserve':
                nonreserve.add(group_id)
                continue  # Do not decode non-reserve review text or labels.
            group = json.loads(line)
            if group['exposed']:
                raise ValueError('old reserve contains an exposed group')
            if stable_hash(sorted(row['id'] for row in group['rows'])) != group_id:
                raise ValueError('old reserve group identity mismatch')
            groups.append(group)
    if sum(len(g['rows']) for g in groups) != manifest['reserve_rows']:
        raise ValueError('old reserve row count mismatch')
    groups.sort(key=lambda g: stable_hash([seed, g['group_id']]))
    assigned, counts = [], {'mining': 0, 'development': 0, 'untouched': 0}
    for group in groups:
        split = ('mining' if counts['mining'] < mining_rows else
                 'development' if counts['development'] < development_rows else 'untouched')
        counts[split] += len(group['rows'])
        assigned.append((split, group))
    if not counts['untouched'] or counts['development'] < development_rows:
        raise ValueError('insufficient reserve for workset and untouched remainder')
    output.mkdir(parents=True)
    assignments = [{'group_id': g['group_id'], 'split': split, 'ids': [r['id'] for r in g['rows']]}
                   for split, g in assigned]
    _write_rows(output / 'assignments.jsonl', assignments)
    for split in ('mining', 'development'):
        rows = [(g['group_id'], row) for part, g in assigned if part == split for row in g['rows']]
        _write_rows(output / f'{split}.inputs.jsonl', ({'id': r['id'], 'text': r['text']} for _, r in rows))
        if split == 'development':
            _write_rows(output / 'development.gold.jsonl',
                        ({'id': r['id'], 'label': r['label'], 'group_id': g} for g, r in rows))
    report = {'schema_version': 1, 'phase': 'development_only', 'baseline_sha': BASELINE, 'seed': seed,
              'counts': counts, 'old_nonreserve_group_overlap': 0,
              'group_policy': 'indivisible authenticated old v1 groups; reserve grouping was LSH, not exhaustive',
              'holdout_created': False, 'old_benchmark': str(old),
              'provenance': {str(old / name): _sha256(old / name)
                             for name in ('manifest.json', 'groups.jsonl', 'release.json')},
              'source_sha256': manifest['source']['sha256'],
              'files': {p.name: _sha256(p) for p in sorted(output.iterdir())}}
    _write_rows(output / 'manifest.json', [report])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-benchmark', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare_workset(args.old_benchmark, args.output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
