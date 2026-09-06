"""Measure a frozen candidate on gold-free development inputs."""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from pathlib import Path

from scripts.benchmark.runner import validate_input_record
from scripts.predict_sentiment_benchmark import _load_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-manifest', required=True, type=Path)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    records = [validate_input_record(json.loads(line)) for line in args.inputs.read_text().splitlines() if line.strip()]
    if not records:
        parser.error('inputs must not be empty')
    analyze = _load_engine(args.candidate_manifest)
    from sentiment_engine.korean import analyze_morphology_with_trace

    samples, lengths, errors = [], [], {}
    matched, invariant_checks = 0, 0
    cold = None
    for record in records:
        # The model remains initialized; avoid reusing cached prior inputs.
        analyze_morphology_with_trace.cache_clear()
        start = time.perf_counter()
        try:
            on = analyze(record['text'])
        except ValueError as error:
            errors[str(error)] = errors.get(str(error), 0) + 1
            continue
        elapsed = time.perf_counter() - start
        if cold is None:
            cold = elapsed
        else:
            samples.append(1000 * elapsed)
        lengths.append(len(record['text']))
        off = analyze(record['text'], apply_modifiers=False)
        identity = lambda result: [(m.term,m.raw,m.base_score,m.start,m.end) for m in result.matches]
        assert identity(on) == identity(off), record['id']
        assert on.score == round(sum(m.contribution for m in on.matches),6), record['id']
        assert all(record['text'][m.start:m.end] == m.raw for m in on.matches), record['id']
        invariant_checks += 1
        matched += bool(on.matches)
    samples.sort()
    percentile = lambda values,p: values[min(len(values)-1, (len(values)*p+99)//100-1)] if values else None
    payload = {
        'candidate_manifest': str(args.candidate_manifest), 'n': len(records), 'cold_seconds': cold,
        'warm_p50_ms': percentile(samples,50), 'warm_p95_ms': percentile(samples,95),
        'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform=='darwin' else 1024),
        'successful_input_codepoints': {'min':min(lengths) if lengths else None, 'max':max(lengths) if lengths else None,
                                        'p50':percentile(sorted(lengths),50),'p95':percentile(sorted(lengths),95)},
        'matched_inputs':matched, 'on_off_event_and_source_invariant_checks':invariant_checks,
        'errors':errors, 'workload':'one uncached morphology call per input; on scoring timed, off invariants checked afterward',
    }
    args.output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(payload,ensure_ascii=False))


if __name__ == '__main__':
    main()
