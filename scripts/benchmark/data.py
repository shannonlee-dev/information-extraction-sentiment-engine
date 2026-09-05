"""Source parsing, duplicate auditing, and deterministic benchmark splitting."""

from __future__ import annotations

import hashlib
import json
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
    hashes: dict[int, Any] = {}
    for index in eligible:
        minhash = MinHash(num_perm=256, seed=20260905)
        for shingle in sorted(_shingles(texts[index])):
            minhash.update(shingle.encode("utf-8"))
        lsh.insert(str(index), minhash)
        hashes[index] = minhash
    yielded: set[tuple[int, int]] = set()
    for index in eligible:
        for candidate in lsh.query(hashes[index]):
            other = int(candidate)
            pair = tuple(sorted((index, other)))
            if pair[0] != pair[1] and pair not in yielded:
                yielded.add(pair)
                yield pair


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
    texts = [node["text"] for node in nodes]
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
        before = sum((Fraction(counts[split][rating]) - rating_targets[split][rating]) ** 2 for rating in RATINGS)
        after = sum((Fraction(counts[split][rating] + vector[rating]) - rating_targets[split][rating]) ** 2 for rating in RATINGS)
        return after - before

    ordered = sorted(groups, key=lambda group: (-len(group["rows"]), stable_hash([seed, group["group_id"]])))
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
    """Return exact/near duplicate IDs crossing split boundaries or touching exposure."""
    rows = [(split, row["id"], row["text"]) for split, values in splits.items() for row in values]
    pairs: set[tuple[str, str]] = set()
    for left, right in combinations(rows, 2):
        if left[0] == right[0]:
            continue
        same = _duplicate_key(left[2]) == _duplicate_key(right[2])
        near = len(left[2]) >= 20 and len(right[2]) >= 20 and _jaccard_at_least(_shingles(left[2]), _shingles(right[2]))
        if same or near:
            pairs.add(tuple(sorted((left[1], right[1]))))
    for split, row_id, text in rows:
        for exposure in exposures:
            if _duplicate_key(text) == _duplicate_key(exposure) or (
                len(text) >= 20 and len(exposure) >= 20 and _jaccard_at_least(_shingles(text), _shingles(exposure))
            ):
                pairs.add(tuple(sorted((row_id, f"exposure:{_sha256_bytes(exposure.encode('utf-8'))}"))))
    return sorted(pairs)
