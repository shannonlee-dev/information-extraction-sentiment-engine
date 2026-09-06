"""Hash verification and gold-separated input loading for prepared v2 data."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.benchmark.artifacts import _sha256
from scripts.benchmark.runner import validate_input_record


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_new_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as resource:
        resource.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def benchmark_files(benchmark: Path, manifest: dict) -> list[Path]:
    return [benchmark / name for name in (
        "manifest.json", "protocol.md", "exposures.jsonl", "source.json", "groups.jsonl", "exclusions.jsonl"
    )] + [Path(manifest["source"]["path"])] + [
        benchmark / f"{split}.{kind}.jsonl"
        for split in manifest["splits"] for kind in ("inputs", "gold")
    ]


def verify_benchmark(benchmark: Path) -> dict:
    """Verify sealed bytes without decoding unopened holdout text or labels."""
    benchmark = benchmark.resolve()
    manifest = read_json(benchmark / "manifest.json")
    if manifest.get("format") != 2 or manifest.get("benchmark_version") != "v2":
        raise ValueError("benchmark requires format 2 / version v2")
    splits = manifest.get("splits")
    if not isinstance(splits, dict) or not {"selection", "final"}.issubset(splits):
        raise ValueError("benchmark requires selection/final splits")
    if set(splits) - {"development", "selection", "final", "reserve"}:
        raise ValueError("invalid benchmark split")
    for filename, field in (("protocol.md", "protocol_sha256"), ("exposures.jsonl", "exposure_register_sha256")):
        if _sha256(benchmark / filename) != manifest[field]:
            raise ValueError(f"benchmark hash mismatch: {filename}")
    source = Path(manifest["source"]["path"])
    if not source.is_absolute() or _sha256(source) != manifest["source"]["sha256"]:
        raise ValueError("source hash mismatch or nonabsolute path")
    for split, info in splits.items():
        if type(info.get("rows")) is not int or info["rows"] <= 0:
            raise ValueError("split row count must be positive")
        for kind in ("inputs", "gold"):
            if _sha256(benchmark / f"{split}.{kind}.jsonl") != info["sha256"][kind]:
                raise ValueError(f"split hash mismatch: {split}.{kind}")
    for path in benchmark_files(benchmark, manifest):
        if not path.is_file():
            raise ValueError(f"missing benchmark provenance: {path.name}")
    return manifest


def load_split(benchmark: Path, split: str):
    manifest = verify_benchmark(benchmark)
    if split not in manifest["splits"]:
        raise ValueError("unknown split")
    inputs = read_jsonl(benchmark / f"{split}.inputs.jsonl")
    gold = read_jsonl(benchmark / f"{split}.gold.jsonl")
    if len(inputs) != manifest["splits"][split]["rows"] or len(gold) != len(inputs):
        raise ValueError("split row count mismatch")
    inputs = [validate_input_record(row) for row in inputs]
    if len({row["id"] for row in inputs}) != len(inputs):
        raise ValueError("input IDs must be unique")
    for item, target in zip(inputs, gold):
        if not isinstance(target, dict) or target.get("id") != item["id"]:
            raise ValueError("input/gold alignment mismatch")
        if set(target) not in ({"id", "label", "group_id"}, {"id", "text", "label", "group_id"}):
            raise ValueError("invalid gold schema")
        if "text" in target and target["text"] != item["text"]:
            raise ValueError("input/gold source alignment mismatch")
        if target["label"] not in ("positive", "negative"):
            raise ValueError("invalid gold label")
        if not isinstance(target["group_id"], str) or not target["group_id"]:
            raise ValueError("gold requires nonempty group_id")
    return inputs, gold
