"""Measure one audited lexicon checkpoint on M2 open development only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.benchmark.artifacts import _sha256, snapshot
from scripts.benchmark.data import stable_hash
from scripts.benchmark.metrics import metrics
from scripts.benchmark.runner import run_predictions, validate_input_record
from scripts.run_engine_development import _runtime_provenance

ROOT = Path(__file__).resolve().parents[1]


def run_development(workset: Path, output: Path, *, root: Path = ROOT):
    workset, output = workset.resolve(), output.resolve()
    if output.exists():
        raise ValueError('development output already exists')
    manifest = json.loads((workset / 'manifest.json').read_bytes())
    data = {}
    for kind in ('inputs', 'gold'):
        name = f'development.{kind}.jsonl'
        if _sha256(workset / name) != manifest['files'][name]:
            raise ValueError('development file hash mismatch')
        data[kind] = [json.loads(line) for line in (workset / name).read_text().splitlines()]
    inputs = [validate_input_record(row) for row in data['inputs']]
    gold = data['gold']
    metrics(gold, [{'id': row['id'], 'predicted': 'neutral'} for row in inputs])
    if len(inputs) != manifest['counts']['development']:
        raise ValueError('development row count mismatch')
    output.mkdir(parents=True)
    snapshot(root, output / 'candidate')
    (output / 'development.inputs.jsonl').write_bytes((workset / 'development.inputs.jsonl').read_bytes())
    runtime = _runtime_provenance(output / 'candidate')
    run_predictions(output / 'development.inputs.jsonl', output / 'candidate.json',
                    output / 'predictions.jsonl', modifiers=True)
    predictions = [json.loads(line) for line in (output / 'predictions.jsonl').read_text().splitlines()]
    result = metrics(gold, predictions)
    result['analysis_error_rate'] = result['analysis_error_count'] / result['n']
    for reason in ('no_match', 'cancellation', 'other_zero'):
        result[f'{reason}_count'] = sum(p['neutral_reason'] == reason for p in predictions)
    by_id = {p['id']: p for p in predictions}
    buckets = {bucket: [] for bucket in 'ABCDEF'}
    for row in gold:
        p = by_id[row['id']]
        predicted, label = p['predicted'], row['label']
        if predicted == label:
            continue
        bucket = ('F' if predicted == 'analysis_error' else 'E' if p['neutral_reason'] == 'cancellation'
                  else ('A' if label == 'negative' else 'B') if predicted == 'neutral'
                  else 'C' if label == 'negative' else 'D')
        buckets[bucket].append(row['id'])
    compiled = json.loads((output / 'candidate/data/sentiment_lexicon_compiled.json').read_bytes())
    report = {'candidate': 'M2-L-development-checkpoint', 'independent_final_evaluation': False,
              'metrics': result, 'canonical_entries': len(compiled['entries']),
              'customer_support_entries': sum(e['domain'] == 'customer_support' for e in compiled['entries']),
              'bucket_counts': {key: len(ids) for key, ids in buckets.items()},
              'sampled_errors': {key: sorted(ids, key=lambda i: stable_hash([20260906, key, i]))[:50]
                                 for key, ids in buckets.items()},
              'runtime': runtime, 'workset_manifest_sha256': _sha256(workset / 'manifest.json'),
              'candidate_manifest_sha256': _sha256(output / 'candidate.json'),
              'predictions_sha256': _sha256(output / 'predictions.jsonl'),
              'measurement_script_sha256': _sha256(Path(__file__))}
    with (output / 'report.json').open('x', encoding='utf-8') as out:
        json.dump(report, out, ensure_ascii=False, indent=2)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_development(args.workset, args.output)
    print(json.dumps({k: report[k] for k in ('metrics', 'canonical_entries', 'bucket_counts')}, indent=2))


if __name__ == '__main__':
    main()
