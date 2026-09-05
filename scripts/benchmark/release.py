"""Freeze and verify a single baseline candidate before opening final data."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from pathlib import Path

from scripts.benchmark.artifacts import _sha256, verify_manifest

ROOT = Path(__file__).resolve().parents[2]


def environment():
    return {"python": sys.version, "executable": sys.executable,
            "packages": {name: importlib.metadata.version(name) for name in ("numpy", "datasketch", "scipy")}}


def verify_benchmark(benchmark: Path):
    benchmark = benchmark.resolve()
    manifest = json.loads((benchmark / "manifest.json").read_text(encoding="utf-8"))
    for filename, expected in (("protocol.md", manifest["protocol_sha256"]),
                               ("exposures.jsonl", manifest["exposure_register_sha256"])):
        if _sha256(benchmark / filename) != expected:
            raise ValueError(f"benchmark hash mismatch: {filename}")
    raw = Path(manifest["source"]["path"])
    if _sha256(raw) != manifest["source"]["sha256"]:
        raise ValueError("raw source hash mismatch")
    ids, group_splits = set(), {}
    for split, info in manifest["splits"].items():
        content = {}
        for kind in ("inputs", "gold"):
            path = benchmark / f"{split}.{kind}.jsonl"
            if _sha256(path) != info["sha256"][kind]:
                raise ValueError(f"split hash mismatch: {split}.{kind}")
            content[kind] = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        inputs, gold = content["inputs"], content["gold"]
        if len(inputs) != info["rows"] or len(gold) != len(inputs):
            raise ValueError("split row count mismatch")
        for item, target in zip(inputs, gold):
            if set(item) != {"id", "text"} or item["id"] != target["id"] or item["text"] != target["text"]:
                raise ValueError("input/gold alignment mismatch")
            if item["id"] in ids:
                raise ValueError("duplicate/cross-split ID")
            ids.add(item["id"])
            group = target["group_id"]
            if group_splits.setdefault(group, split) != split:
                raise ValueError("group crosses splits")
    return manifest


def freeze(benchmark: Path, candidate: Path, output: Path, protocol: Path, exposures: Path):
    benchmark, candidate, output = benchmark.resolve(), candidate.resolve(), output.resolve()
    if output.exists() or (benchmark / "final-attempt.json").exists():
        raise ValueError("release/final attempt already exists")
    manifest = verify_benchmark(benchmark)
    verified = verify_manifest(candidate)
    if _sha256(protocol) != manifest["protocol_sha256"] or _sha256(exposures) != manifest["exposure_register_sha256"]:
        raise ValueError("current protocol/exposures differ from prepared data")
    files = [candidate, benchmark / "manifest.json", benchmark / "source.json",
             benchmark / "groups.jsonl", benchmark / "exclusions.jsonl",
             protocol.resolve(), exposures.resolve()]
    files.extend(sorted((ROOT / "scripts").rglob("*.py")))
    files.extend(path for path in ROOT.glob("requirements*") if path.is_file())
    files.extend(Path(verified["manifest"]["snapshot_root"]) / item["path"]
                 for item in verified["manifest"]["files"])
    release = {
        "format": 2, "split": "final", "benchmark": str(benchmark),
        "candidate_manifest": str(candidate), "baseline_manifest": str(candidate),
        "candidate_modifiers": True, "selection": "single frozen baseline; selection unopened",
        "environment": environment(),
        "files": {str(path): _sha256(path) for path in sorted(set(files))},
        "targets": {"accuracy": 0.8, "macro_f1": 0.8, "class_recall": 0.75, "accuracy_ci_lower": 0.75},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as resource:
        resource.write(json.dumps(release, ensure_ascii=False, indent=2) + "\n")
    return release


def verify_release(path: Path, benchmark: Path):
    release = json.loads(path.read_text(encoding="utf-8"))
    if release.get("format") != 2 or release.get("benchmark") != str(benchmark.resolve()):
        raise ValueError("release format/benchmark mismatch; use scripts.benchmark.release")
    if release.get("environment") != environment():
        raise ValueError("release environment mismatch")
    if not release.get("files"):
        raise ValueError("release lacks frozen hashes")
    for filename, expected in release["files"].items():
        if _sha256(Path(filename)) != expected:
            raise ValueError(f"release hash mismatch: {filename}")
    verify_manifest(Path(release["candidate_manifest"]))
    verify_manifest(Path(release["baseline_manifest"]))
    verify_benchmark(benchmark)
    return release


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--candidate-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--protocol", type=Path, default=ROOT / "docs/evaluation/sentiment-protocol.md")
    parser.add_argument("--exposures", type=Path, default=ROOT / "docs/evaluation/exposure-register.jsonl")
    args = parser.parse_args()
    freeze(args.benchmark, args.candidate_manifest, args.output, args.protocol, args.exposures)
    print(json.dumps({"release": str(args.output), "candidate": "baseline", "selection_used": False}))


if __name__ == "__main__":
    main()
