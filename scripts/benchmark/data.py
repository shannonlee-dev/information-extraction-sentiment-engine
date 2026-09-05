"""Source parsing, duplicate auditing, and deterministic benchmark splitting."""

from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from collections import Counter
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable


RATINGS = (1, 2, 4, 5)
SPLITS = ("development", "selection", "final", "reserve")


def stable_hash(value: Any) -> str:
    """Hash an unambiguous, UTF-8 JSON representation."""
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _record_id(source_sha256: str, source_line: int) -> str:
    return f"{source_sha256}:{source_line}"


def parse_source(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse the original rating<TAB>text format without changing text."""
    raw = Path(path).read_bytes()
    source_sha256 = _sha256_bytes(raw)
    text = raw.decode("utf-8", errors="strict")
    rows: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for source_line, line in enumerate(lines, start=1):
        if line.endswith("\r"):
            line = line[:-1]
        record_id = _record_id(source_sha256, source_line)
        if "\t" not in line:
            excluded.append({"id": record_id, "source_line": source_line, "reason": "malformed_record"})
            continue
        raw_rating, body = line.split("\t", 1)
        try:
            rating = int(raw_rating.strip())
        except (TypeError, ValueError):
            excluded.append({"id": record_id, "source_line": source_line, "reason": "malformed_record"})
            continue
        if rating == 3:
            excluded.append({"id": record_id, "source_line": source_line, "reason": "excluded_rating_3"})
            continue
        if rating not in RATINGS:
            excluded.append({"id": record_id, "source_line": source_line, "reason": "malformed_record"})
            continue
        if not body.strip():
            excluded.append({"id": record_id, "source_line": source_line, "reason": "empty_text"})
            continue
        rows.append({
            "id": record_id,
            "text": body,
            "rating": rating,
            "label": "positive" if rating >= 4 else "negative",
            "source_line": source_line,
            "text_sha256": _sha256_bytes(body.encode("utf-8")),
        })
    return rows, excluded


def _duplicate_key(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    return " ".join(normalized.split())


def _shingles(text: str) -> set[str]:
    return {text[index : index + 5] for index in range(len(text) - 4)}


def _jaccard_at_least(left: set[str], right: set[str]) -> bool:
    if not left and not right:
        return True
    return 20 * len(left & right) >= 17 * len(left | right)


def _candidate_pairs(texts: list[str]) -> Iterable[tuple[int, int]]:
    """Yield likely near-duplicate pairs, using datasketch when installed."""
    eligible = [index for index, text in enumerate(texts) if len(text) >= 20]
    if len(eligible) < 2:
        return
    try:
        from datasketch import MinHash, MinHashLSH
    except ImportError:
        if len(eligible) > 1500:
            raise RuntimeError("datasketch is required for large near-duplicate audits") from None
        yield from combinations(eligible, 2)
        return
    lsh = MinHashLSH(threshold=0.85, num_perm=256, params=(32, 8))
    template = MinHash(num_perm=256, seed=20260905)
    for number, index in enumerate(eligible, 1):
        minhash = template.copy()
        minhash.update_batch([shingle.encode("utf-8") for shingle in sorted(_shingles(texts[index]))])
        for candidate in sorted(lsh.query(minhash), key=int):
            other = int(candidate)
            yield other, index
        lsh.insert(str(index), minhash)
        if number % 20000 == 0:
            print(f"near-duplicate indexing: {number}/{len(eligible)}", file=sys.stderr, flush=True)


def _exact_candidate_pairs(texts: list[str]) -> Iterable[tuple[int, int]]:
    """Lossless Jaccard prefix filter; unlike LSH, this does not sample pairs.

    In one global token order a set of m shingles needs a prefix of
    m - ceil(0.85*m) + 1. Similar sets must share a prefix token: otherwise
    the first common token occurs too late in one set to reach the required
    overlap. Length filtering and the final integer Jaccard check are exact.
    """
    shingles = {i: _shingles(text) for i, text in enumerate(texts) if len(text) >= 20}
    frequencies = Counter(s for values in shingles.values() for s in values)
    postings: dict[str, list[int]] = {}
    for index in sorted(shingles, key=lambda i: (len(shingles[i]), i)):
        values = shingles[index]
        size = len(values)
        prefix = sorted(values, key=lambda s: (frequencies[s], s))[:size - (17 * size + 19) // 20 + 1]
        candidates: set[int] = set()
        for shingle in prefix:
            candidates.update(other for other in postings.get(shingle, [])
                              if 20 * len(shingles[other]) >= 17 * size)
        for other in sorted(candidates):
            yield min(other, index), max(other, index)
        for shingle in prefix:
            postings.setdefault(shingle, []).append(index)


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def deduplicate_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep one row per exact key/polarity and exclude exact label conflicts."""
    by_key: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_key.setdefault(_duplicate_key(row["text"]), []).append(row)
    representatives: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for key in sorted(by_key):
        same_key = sorted(by_key[key], key=lambda row: (row.get("source_line", 0), row["id"]))
        labels = {row["label"] for row in same_key}
        if len(labels) > 1:
            exclusions.extend({"id": row["id"], "reason": "conflicting_exact_label", "duplicate_key": key} for row in same_key)
            continue
        representatives.append(same_key[0])
        exclusions.extend(
            {"id": row["id"], "reason": "duplicate_exact", "representative_id": same_key[0]["id"], "duplicate_key": key}
            for row in same_key[1:]
        )
    return representatives, exclusions


def group_rows(rows: list[dict[str, Any]], exposures: list[str]) -> list[dict[str, Any]]:
    """Build connected near-duplicate groups while preserving source text."""
    representatives, _ = deduplicate_rows(rows)
    nodes = list(representatives) + [
        {"id": f"exposure:{_sha256_bytes(text.encode('utf-8'))}", "text": text, "exposure": True}
        for text in exposures
    ]
    union = _UnionFind(len(nodes))
    keys: dict[str, int] = {}
    for index, node in enumerate(nodes):
        key = _duplicate_key(node["text"])
        previous = keys.get(key)
        if previous is not None:
            union.union(index, previous)
        else:
            keys[key] = index
    texts = [_duplicate_key(node["text"]) for node in nodes]
    for left, right in _candidate_pairs(texts):
        if _jaccard_at_least(_shingles(texts[left]), _shingles(texts[right])):
            union.union(left, right)
    components: dict[int, list[int]] = {}
    for index in range(len(nodes)):
        components.setdefault(union.find(index), []).append(index)
    groups: list[dict[str, Any]] = []
    for indexes in components.values():
        row_nodes = [nodes[index] for index in indexes if not nodes[index].get("exposure")]
        if not row_nodes:
            continue
        row_nodes.sort(key=lambda row: (row.get("source_line", 0), row["id"]))
        group_id = stable_hash(sorted(row["id"] for row in row_nodes))
        groups.append({
            "group_id": group_id,
            "rows": row_nodes,
            "exposed": any(nodes[index].get("exposure") for index in indexes),
            "exposure_ids": sorted(nodes[index]["id"] for index in indexes if nodes[index].get("exposure")),
        })
    return sorted(groups, key=lambda group: group["group_id"])


def _rating_vector(group: dict[str, Any]) -> Counter[int]:
    return Counter(row["rating"] for row in group["rows"])


def allocate_groups(groups: list[dict[str, Any]], seed: int) -> dict[str, list[dict[str, Any]]]:
    """Assign complete groups to deterministic development/selection/final/reserve splits."""
    total = sum(len(group["rows"]) for group in groups)
    if total < 8000:
        raise ValueError("benchmark requires at least 8000 deduplicated rows")
    targets = {"development": 4000, "selection": 2000, "final": 2000, "reserve": total - 8000}
    total_ratings = Counter(row["rating"] for group in groups for row in group["rows"])
    rating_targets = {
        split: {rating: Fraction(targets[split] * total_ratings[rating], total) for rating in RATINGS}
        for split in SPLITS
    }
    counts = {split: Counter() for split in SPLITS}
    assigned: dict[str, list[dict[str, Any]]] = {split: [] for split in SPLITS}

    def cost(split: str, group: dict[str, Any]) -> Fraction:
        vector = _rating_vector(group)
        return sum(
            (2 * (counts[split][rating] - rating_targets[split][rating]) * vector[rating]
             + vector[rating] ** 2) / max(rating_targets[split][rating], 1)
            for rating in RATINGS if vector[rating]
        )

    ordered = sorted(groups, key=lambda group: (-len(group["rows"]), stable_hash([seed, group["group_id"]])))
    ordered = [g for g in ordered if g.get("exposed")] + [g for g in ordered if not g.get("exposed")]
    for group in ordered:
        split_options = ["development"] if group.get("exposed") else list(SPLITS)
        chosen = min(split_options, key=lambda split: (cost(split, group), stable_hash([seed, group["group_id"], split])))
        assigned[chosen].append(group)
        counts[chosen].update(_rating_vector(group))
    result: dict[str, list[dict[str, Any]]] = {}
    for split, split_groups in assigned.items():
        rows = [row for group in split_groups for row in group["rows"]]
        result[split] = sorted(rows, key=lambda row: (row.get("source_line", 0), row["id"]))
    return result


def cross_split_pairs(splits: dict[str, list[dict[str, Any]]], exposures: list[str]) -> list[tuple[str, str]]:
    """Return indexed exact/near leaks across splits or holdouts touching exposure."""
    nodes = [
        {"split": split, "id": row["id"], "text": row["text"], "exposure": False}
        for split, values in splits.items()
        for row in values
    ]
    nodes.extend({
        "split": "exposure",
        "id": f"exposure:{_sha256_bytes(text.encode('utf-8'))}",
        "text": text,
        "exposure": True,
    } for text in exposures)
    pairs: set[tuple[str, str]] = set()

    def reportable(left: dict[str, Any], right: dict[str, Any]) -> bool:
        if left["exposure"] and right["exposure"]:
            return False
        if left["exposure"] or right["exposure"]:
            row = right if left["exposure"] else left
            return row["split"] != "development"
        return left["split"] != right["split"]

    exact_indexes: dict[str, list[int]] = {}
    keys: list[str] = []
    for index, node in enumerate(nodes):
        key = _duplicate_key(node["text"])
        keys.append(key)
        for other in exact_indexes.get(key, []):
            if reportable(nodes[other], node):
                pairs.add(tuple(sorted((nodes[other]["id"], node["id"]))))
        exact_indexes.setdefault(key, []).append(index)

    texts = keys
    shingles = {i: _shingles(text) for i, text in enumerate(texts) if len(text) >= 20}
    for left_index, right_index in _exact_candidate_pairs(texts):
        left, right = nodes[left_index], nodes[right_index]
        if not reportable(left, right) or keys[left_index] == keys[right_index]:
            continue
        if _jaccard_at_least(shingles[left_index], shingles[right_index]):
            pairs.add(tuple(sorted((left["id"], right["id"]))))
    return sorted(pairs)
