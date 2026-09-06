"""Build the reviewed project lexicon using the locked morphology adapter.

Only lexical endings are removed. Internal particles, copulas and derivational
suffixes remain. ETM/ETN also collapse attributive/nominalized inflections; this
build-time rule is never applied to a sentence by the runtime matcher.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from sentiment_engine.korean import analyze_morphology, analyzer_fingerprint

ROOT = Path(__file__).resolve().parents[1]
_ENDINGS = {'EP', 'EF', 'EC', 'ETM', 'ETN'}


def lexical_key(tokens):
    key = [(token.morph, token.pos) for token in tokens]
    while key and (key[-1][1].startswith('J') or key[-1][1] in _ENDINGS):
        key.pop()
    return tuple(key)


def serialize(artifact: dict) -> str:
    return json.dumps(artifact, ensure_ascii=False, sort_keys=True, indent=2) + '\n'


def _reviewed(record):
    review = record.get('review')
    return (isinstance(review, dict) and isinstance(review.get('reviewer'), str)
            and bool(review['reviewer']) and isinstance(review.get('date'), str)
            and bool(review['date']) and isinstance(record.get('reason'), str)
            and bool(record['reason']))


def _key(raw):
    if (not isinstance(raw, list) or not raw or any(
        not isinstance(pair, list) or len(pair) != 2
        or any(not isinstance(part, str) or not part for part in pair) for pair in raw
    )):
        raise ValueError('invalid annotated lexical key')
    return tuple(tuple(pair) for pair in raw)


def compile_lexicon(source: Path, annotations: Path, *, minimum_entries=200, minimum_domain=30) -> dict:
    source_bytes, annotation_bytes = Path(source).read_bytes(), Path(annotations).read_bytes()
    rows, audit = json.loads(source_bytes), json.loads(annotation_bytes)
    if not isinstance(rows, list) or not isinstance(audit, dict) or audit.get('schema_version') != 1:
        raise ValueError('invalid lexicon source/annotation schema')
    reviews = audit.get('entries')
    if not isinstance(reviews, dict):
        raise ValueError('annotations require entries')
    seen, records, exclusions = set(), {}, []
    for row in rows:
        if (not isinstance(row, dict) or set(row) - {'term', 'variants', 'score', 'domain', 'source'}
                or not isinstance(row.get('term'), str) or not row['term'].strip()
                or row['term'] != row['term'].strip()
                or not isinstance(row.get('variants'), list)
                or any(not isinstance(v, str) or not v.strip() or v != v.strip() for v in row['variants'])
                or len(set(row['variants'])) != len(row['variants'])
                or row['term'] in row['variants']
                or type(row.get('score')) is not int or not -3 <= row['score'] <= 3
                or not isinstance(row.get('source'), str) or not row['source']
                or (row.get('domain') is not None and (not isinstance(row['domain'], str) or not row['domain']))):
            raise ValueError('invalid lexicon source entry')
        term = row['term']
        if term in seen:
            raise ValueError(f'duplicate lexicon term: {term}')
        seen.add(term)
        review = reviews.get(term)
        if (not isinstance(review, dict) or review.get('decision') not in {'include', 'exclude'}
                or type(review.get('atomic')) is not bool or type(review.get('priority')) is not int
                or review.get('modifier_policy') not in {'external', 'consume_internal'}
                or not _reviewed(review)):
            raise ValueError(f'missing or invalid annotation: {term}')
        surfaces = review.get('surfaces')
        if (not isinstance(surfaces, list) or any(not isinstance(s, dict) for s in surfaces)
                or len(surfaces) != len(row['variants']) + 1
                or {s.get('surface') for s in surfaces} != {term, *row['variants']}
                or any(s.get('decision') not in {'include', 'exclude'} or not s.get('reason') for s in surfaces)):
            raise ValueError(f'missing or invalid surface annotation: {term}')
        if review['decision'] == 'exclude' or row['score'] == 0:
            exclusions.append({'term': term, 'reason': 'zero score' if row['score'] == 0 else review['reason']})
            continue
        keys = set()
        for surface in surfaces:
            if surface['decision'] == 'exclude':
                exclusions.append({'term': term, 'surface': surface['surface'], 'reason': surface['reason']})
                continue
            key = lexical_key(analyze_morphology(surface['surface']))
            if key:
                keys.add(key)
            else:
                exclusions.append({'term': term, 'surface': surface['surface'], 'reason': 'empty lexical key'})
        # Explicit POS aliases are tied to an analyzed context and audited lexical prefix.
        for alias in review.get('aliases', []):
            if not isinstance(alias, dict) or not alias.get('reason') or not isinstance(alias.get('context'), str):
                raise ValueError(f'invalid contextual alias: {term}')
            key = _key(alias.get('key'))
            actual = tuple((t.morph, t.pos) for t in analyze_morphology(alias['context']))
            start = alias.get('token_start', 0)
            if type(start) is not int or start < 0:
                raise ValueError(f'invalid contextual alias token_start: {term}')
            if actual[start:start + len(key)] != key:
                raise ValueError(f'contextual alias no longer matches analyzer: {term}')
            keys.add(key)
        records[term] = dict(row, atomic=review['atomic'], priority=review['priority'], keys=keys)
    if set(reviews) != seen:
        raise ValueError('annotations contain unknown terms')

    owners = defaultdict(list)
    for term in sorted(records):
        for key in sorted(records[term]['keys']):
            owners[key].append(term)
    overrides = {}
    if not isinstance(audit.get('overrides', []), list):
        raise ValueError('invalid conflict overrides')
    for override in audit.get('overrides', []):
        if (not isinstance(override, dict) or not _reviewed(override)
                or type(override.get('score')) is not int or override['score'] not in {-3,-2,-1,1,2,3}):
            raise ValueError('invalid reviewed conflict override')
        key = _key(override.get('key'))
        if key in overrides:
            raise ValueError('duplicate conflict override')
        overrides[key] = override
    conflicts = []
    for key, terms in sorted(owners.items()):
        scores = sorted({records[term]['score'] for term in terms})
        if len(scores) <= 1:
            continue
        override = overrides.get(key)
        if override and override['score'] not in scores:
            raise ValueError('conflict override must select a source score')
        conflicts.append({'key': key, 'terms': terms, 'scores': scores,
                          'resolution': override or 'excluded'})
        for term in terms:
            if override is None or records[term]['score'] != override['score']:
                records[term]['keys'].remove(key)
                exclusions.append({'term': term, 'key': key, 'reason': 'conflicting score'})
    if set(overrides) - {key for key, terms in owners.items() if len({records[t]['score'] for t in terms}) > 1}:
        raise ValueError('override does not address an existing conflict')

    # Connected components merge transitively shared, same-score lexical identities.
    parent = {term: term for term in records}
    def find(term):
        while parent[term] != term:
            parent[term] = parent[parent[term]]
            term = parent[term]
        return term
    owner = {}
    for term, record in sorted(records.items()):
        for key in sorted(record['keys']):
            if key in owner:
                a, b = find(term), find(owner[key])
                parent[max(a, b)] = min(a, b)
            else:
                owner[key] = term
    groups = defaultdict(list)
    for term in sorted(records):
        if records[term]['keys']:
            groups[find(term)].append(records[term])
        else:
            exclusions.append({'term': term, 'reason': 'no usable lexical keys'})
    entries = []
    for group in groups.values():
        group.sort(key=lambda r: (-r['priority'], r['term']))
        canonical = group[0]
        domains = sorted({r['domain'] for r in group if r.get('domain')})
        entries.append({
            'canonical_id': 'project:' + hashlib.sha256(canonical['term'].encode()).hexdigest()[:20],
            'term': canonical['term'], 'score': canonical['score'],
            'domain': canonical.get('domain') or (domains[0] if domains else None),
            'source': canonical['source'], 'sources': sorted({r['source'] for r in group}),
            'atomic': any(r['atomic'] for r in group), 'priority': canonical['priority'],
            'keys': sorted(set().union(*(r['keys'] for r in group))),
            'merged_terms': sorted(r['term'] for r in group),
        })
    entries.sort(key=lambda r: r['canonical_id'])
    if len(entries) < minimum_entries:
        raise ValueError(f'compiled canonical entry count {len(entries)} < {minimum_entries}')
    domain_count = sum(e['domain'] == 'customer_support' and 'project' in e['sources'] for e in entries)
    if domain_count < minimum_domain:
        raise ValueError(f'compiled project domain entry count {domain_count} < {minimum_domain}')
    # JSON roundtrip presents lists consistently to callers and serializes stable bytes.
    return json.loads(json.dumps({
        'schema_version': 1,
        'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
        'annotations_sha256': hashlib.sha256(annotation_bytes).hexdigest(),
        'analyzer': analyzer_fingerprint(), 'entries': entries, 'conflicts': conflicts,
        'exclusions': sorted(exclusions, key=lambda e: json.dumps(e, ensure_ascii=False, sort_keys=True)),
    }, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'data/sentiment_lexicon.json')
    parser.add_argument('--annotations', type=Path, default=ROOT / 'data/lexicon_annotations.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/sentiment_lexicon_compiled.json')
    args = parser.parse_args()
    result = compile_lexicon(args.source, args.annotations)
    args.output.write_text(serialize(result), encoding='utf-8')
    print(f"Compiled {len(result['entries'])} canonical entries; {len(result['conflicts'])} conflicts; "
          f"{len(result['exclusions'])} exclusions")


if __name__ == '__main__':
    main()
