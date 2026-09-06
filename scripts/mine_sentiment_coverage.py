"""Discover missing morphology from strictly unlabeled id/text input."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from scripts.benchmark.artifacts import _sha256
from scripts.benchmark.runner import validate_input_record
from sentiment_engine.korean import analyze_morphology, MorphologyError
from sentiment_engine.sentiment import find_events, _get_lexicon


def _unmatched_category(tokens, keys_by_morph):
    """Diagnostic buckets, not permission to relax lexical boundaries or POS."""
    key = tuple((token.morph, token.pos) for token in tokens)
    found = set()
    for start, (morph, _) in enumerate(key):
        for candidate in keys_by_morph.get(morph, ()):
            end = start + len(candidate)
            span = key[start:end]
            if span != candidate:
                if tuple(m for m, _ in span) == tuple(m for m, _ in candidate):
                    found.add('known_morph_different_pos')
                continue
            if end < len(key) and candidate[-1][1].startswith(('NN', 'XR')):
                following = key[end][1]
                if following in {'XSA', 'XSV'}:
                    found.add('known_key_before_derivation')
                elif following.startswith(('NN', 'XSN')):
                    found.add('known_key_before_noun_or_suffix')
            if start and key[start - 1][1].startswith(('NN', 'XR', 'XP')):
                found.add('known_key_after_noun_or_prefix')
    for category in ('known_key_before_derivation', 'known_key_before_noun_or_suffix',
                     'known_key_after_noun_or_prefix', 'known_morph_different_pos'):
        if category in found:
            return category
    return 'opaque_na' if any(pos == 'NA' for _, pos in key) else 'no_known_lexical_key'


def mine(rows, groups):
    rows = [validate_input_record(row) for row in rows]  # Validate ALL rows before analysis.
    if len({row['id'] for row in rows}) != len(rows):
        raise ValueError('mining IDs must be unique')
    if any(not isinstance(groups.get(row['id']), str) or not groups[row['id']] for row in rows):
        raise ValueError('mining requires complete group membership')
    docs, group_sets, surfaces = defaultdict(set), defaultdict(set), defaultdict(Counter)
    words, word_groups, word_keys = Counter(), defaultdict(set), {}
    categories, category_groups, category_surfaces = Counter(), defaultdict(set), defaultdict(Counter)
    keys_by_morph = defaultdict(list)
    for entry in _get_lexicon():
        for key in entry.keys:
            keys_by_morph[key[0][0]].append(key)
    errors, no_match = 0, 0
    for row in rows:
        try:
            tokens = analyze_morphology(row['text'])
            events = find_events(tokens, text=row['text'])
        except MorphologyError:
            errors += 1
            continue
        no_match += not events
        covered = {i for event in events for i in range(event.token_start, event.token_end)}
        eojeols = list(re.finditer(r'\S+', row['text']))
        for i, token in enumerate(tokens):
            if i in covered or token.pos not in {'NNG', 'NNP', 'NA', 'VA', 'VV', 'XR', 'MAG', 'IC', 'SL'}:
                continue
            key = (token.morph, token.pos)
            docs[key].add(row['id'])
            group_sets[key].add(groups[row['id']])
            surface = eojeols[token.eojeol_index].group()
            surfaces[key][surface] += 1
        for j, word in enumerate(eojeols):
            indexes = [i for i, token in enumerate(tokens) if token.eojeol_index == j]
            if not indexes or set(indexes) & covered:
                continue
            surface = word.group()
            words[surface] += 1
            word_groups[surface].add(groups[row['id']])
            word_keys[surface] = [(tokens[i].morph, tokens[i].pos) for i in indexes]
            category = _unmatched_category([tokens[i] for i in indexes], keys_by_morph)
            categories[category] += 1
            category_groups[category].add(groups[row['id']])
            category_surfaces[category][surface] += 1
    vocabulary = [{'morph': morph, 'pos': pos, 'document_frequency': len(docs[(morph, pos)]),
                   'group_frequency': len(group_sets[(morph, pos)]),
                   'surface_frequency': dict(surfaces[(morph, pos)].most_common(12))}
                  for morph, pos in docs]
    vocabulary.sort(key=lambda r: (-r['group_frequency'], -r['document_frequency'], r['morph'], r['pos']))
    eojeols = [{'surface': word, 'group_frequency': len(word_groups[word]), 'frequency': words[word],
                'key': word_keys[word]} for word in words]
    eojeols.sort(key=lambda r: (-r['group_frequency'], -r['frequency'], r['surface']))
    return {'rows': len(rows), 'analysis_errors': errors, 'no_match': no_match,
            'vocabulary': vocabulary, 'unmatched_eojeols': eojeols,
            'unmatched_categories': {
                category: {'occurrences': count, 'group_frequency': len(category_groups[category]),
                           'top_surfaces': dict(category_surfaces[category].most_common(20))}
                for category, count in categories.most_common()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--assignments', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('mining output already exists')
    rows = [json.loads(line) for line in args.inputs.read_text().splitlines()]
    assignments = [json.loads(line) for line in args.assignments.read_text().splitlines()]
    groups = {record_id: row['group_id'] for row in assignments if row['split'] == 'mining' for record_id in row['ids']}
    result = mine(rows, groups)
    result['input_sha256'] = _sha256(args.inputs)
    result['assignments_sha256'] = _sha256(args.assignments)
    with args.output.open('x', encoding='utf-8') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
    print(json.dumps({key: result[key] for key in ('rows', 'analysis_errors', 'no_match')}))


if __name__ == '__main__':
    main()
