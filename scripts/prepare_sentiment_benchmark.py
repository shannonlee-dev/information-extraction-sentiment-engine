"""Prepare a versioned external sentiment benchmark from a fixed TSV source."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.benchmark.data import allocate_groups, cross_split_pairs, deduplicate_rows, group_rows, parse_source, stable_hash, _UnionFind


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _read_exposures(path: Path) -> list[str]:
    exposures: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid exposure line {line_number}") from error
        if not isinstance(record, dict) or not isinstance(record.get("text"), str) or not record["text"].strip():
            raise ValueError(f"invalid exposure line {line_number}")
        exposures.append(record["text"])
    return exposures


def prepare(source: Path, source_manifest: Path, protocol: Path, exposures_path: Path, output: Path, seed: int) -> dict[str, Any]:
    if (output / "manifest.json").exists():
        raise ValueError("benchmark already prepared; use a new output version")
    source_manifest_data = json.loads(source_manifest.read_text(encoding="utf-8"))
    source_hash = _sha256(source)
    if source_manifest_data.get("sha256") != source_hash or source_manifest_data.get("size") != source.stat().st_size:
        raise ValueError("source manifest SHA-256 does not match raw source")
    print("Reading source and exact duplicates", file=sys.stderr, flush=True)
    rows, exclusions = parse_source(source)
    exposures = _read_exposures(exposures_path)
    representatives, duplicate_exclusions = deduplicate_rows(rows)
    exclusions.extend(duplicate_exclusions)
    groups = group_rows(representatives, exposures)
    if sum(len(group["rows"]) for group in groups) < 8000:
        raise ValueError("benchmark requires at least 8000 rows after exact duplicate filtering")
    audit_iterations = []
    for iteration in range(100):
        print(f"Allocating groups and exact holdout audit: iteration {iteration + 1}", file=sys.stderr, flush=True)
        splits = allocate_groups(groups, seed)
        leakage = cross_split_pairs({s: rows for s, rows in splits.items() if s != "reserve"}, exposures)
        audit_iterations.append({"iteration": iteration + 1, "leaks": len(leakage)})
        if not leakage:
            break
        by_id = {row["id"]: i for i, group in enumerate(groups) for row in group["rows"]}
        union = _UnionFind(len(groups))
        for left, right in leakage:
            if left in by_id and right in by_id:
                union.union(by_id[left], by_id[right])
            else:
                row_id, exposure_id = (left, right) if left in by_id else (right, left)
                group = groups[by_id[row_id]]
                group["exposed"] = True
                group["exposure_ids"] = sorted(set(group["exposure_ids"] + [exposure_id]))
        merged = {}
        for i, group in enumerate(groups):
            merged.setdefault(union.find(i), []).append(group)
        groups = [{
            "group_id": stable_hash(sorted(row["id"] for group in component for row in group["rows"])),
            "rows": sorted((row for group in component for row in group["rows"]), key=lambda row: row["source_line"]),
            "exposed": any(group["exposed"] for group in component),
            "exposure_ids": sorted({value for group in component for value in group["exposure_ids"]}),
        } for component in merged.values()]
    else:
        raise ValueError("exact audit did not converge")
    for split in ("selection", "final"):
        split_rows = splits[split]
        labels = Counter(row["label"] for row in split_rows)
        if not 1800 <= len(split_rows) <= 2200 or any(labels[label] < 0.4 * len(split_rows) for label in ("positive", "negative")):
            raise ValueError(f"{split} sample size/class balance gate failed")
    split_by_row = {row["id"]: split for split, split_rows in splits.items() for row in split_rows}
    for group in groups:
        group["split"] = split_by_row[group["rows"][0]["id"]]
    group_by_row = {row["id"]: group for group in groups for row in group["rows"]}
    raw_destination = output / "raw" / source.name
    raw_destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != raw_destination.resolve():
        shutil.copyfile(source, raw_destination)
    if source_manifest.resolve() != (output / "source.json").resolve():
        (output / "source.json").write_text(json.dumps(source_manifest_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_jsonl(output / "exclusions.jsonl", exclusions)
    _write_jsonl(output / "groups.jsonl", groups)
    shutil.copyfile(protocol, output / "protocol.md")
    shutil.copyfile(exposures_path, output / "exposures.jsonl")
    split_hashes: dict[str, dict[str, str]] = {}
    for split, split_rows in splits.items():
        if split == "reserve":
            continue
        inputs = [{"id": row["id"], "text": row["text"]} for row in split_rows]
        gold = [{
            "id": row["id"], "rating": row["rating"], "label": row["label"],
            "group_id": group_by_row[row["id"]]["group_id"], "source_line": row["source_line"],
            "text_sha256": row["text_sha256"], "text": row["text"],
        } for row in split_rows]
        input_path, gold_path = output / f"{split}.inputs.jsonl", output / f"{split}.gold.jsonl"
        _write_jsonl(input_path, inputs)
        _write_jsonl(gold_path, gold)
        split_hashes[split] = {"inputs": _sha256(input_path), "gold": _sha256(gold_path)}
    manifest = {
        "format": 1,
        "seed": seed,
        "source": {"path": str(source), "sha256": source_hash, "size": source.stat().st_size},
        "protocol_sha256": _sha256(protocol),
        "exposure_register_sha256": _sha256(exposures_path),
        "splits": {split: {
            "rows": len(splits[split]), "sha256": hashes,
            "labels": dict(Counter(row["label"] for row in splits[split])),
            "ratings": dict(Counter(row["rating"] for row in splits[split])),
            "groups": len({group_by_row[row["id"]]["group_id"] for row in splits[split]}),
        } for split, hashes in split_hashes.items()},
        "source_rows": len(rows) + len(exclusions) - len(duplicate_exclusions),
        "retained_rows": len(representatives),
        "reserve_rows": len(splits["reserve"]),
        "exclusion_reasons": dict(Counter(item["reason"] for item in exclusions)),
        "audit_iterations": audit_iterations,
        "audit_scope": "exact prefix-filtered Jaccard across selected splits and exposures; reserve uses LSH grouping",
        "max_group_rows": max(len(group["rows"]) for group in groups),
        "exposed_groups": sum(group["exposed"] for group in groups),
        "groups": len(groups),
        "exclusions": len(exclusions),
        "cross_split_pairs": leakage,
        "preparation_sha256": {str(path): _sha256(path) for path in (
            Path(__file__), Path(__file__).parent / "benchmark/data.py",
            Path("requirements-eval.lock"),
        )},
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--source-manifest", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--exposures", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", required=True, type=int)
    arguments = parser.parse_args(argv)
    try:
        manifest = prepare(arguments.source, arguments.source_manifest, arguments.protocol, arguments.exposures, arguments.output, arguments.seed)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps({"manifest": str(arguments.output / "manifest.json"), "splits": manifest["splits"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
