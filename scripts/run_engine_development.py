"""Freeze candidate M and compare development predictions with the saved baseline.

This command reads only development inputs/gold and saved development predictions.
Its report is development evidence, with no independent final-evaluation claim.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from scripts.benchmark.artifacts import _sha256, snapshot, verify_manifest
from scripts.benchmark.metrics import metrics
from scripts.benchmark.runner import run_predictions, validate_input_record


ROOT = Path(__file__).resolve().parents[1]
MODES = (("on", "with_modifiers", True), ("off", "without_modifiers", False))


def _jsonl(content: bytes) -> list[dict]:
    return [json.loads(line) for line in content.decode("utf-8").splitlines() if line.strip()]


def _checked_bytes(path: Path, expected: str) -> bytes:
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError(f"hash mismatch: {path.name}")
    return content


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _runtime_provenance(candidate: Path) -> dict:
    import jpype
    from sentiment_engine.korean import analyzer_fingerprint

    analyzer = analyzer_fingerprint()
    compiled = json.loads((candidate / "data/sentiment_lexicon_compiled.json").read_text(encoding="utf-8"))
    if compiled.get("analyzer") != analyzer:
        raise ValueError("compiled lexicon analyzer/model hash mismatch")
    java_home = os.environ.get("JAVA_HOME")
    if not java_home:
        raise ValueError("JDK 17 requires JAVA_HOME")
    home = Path(java_home).resolve()
    java = subprocess.run(
        [str(home / "bin/java"), "-XshowSettings:properties", "-version"],
        capture_output=True, text=True, check=True, timeout=30,
    )
    properties = {key.strip(): value.strip() for line in java.stderr.splitlines() if " = " in line
                  for key, value in [line.split(" = ", 1)]}
    if properties.get("java.specification.version") != "17":
        raise ValueError("development runtime requires JDK 17")
    return {
        "python": {"executable": sys.executable, "version": sys.version},
        "packages": {name: importlib.metadata.version(name)
                     for name in ("konlpy", "JPype1", "numpy", "lxml", "packaging")},
        "analyzer": analyzer,
        "java": {"home": str(home), "properties": properties,
                 "properties_output": java.stderr,
                 "properties_sha256": hashlib.sha256(java.stderr.encode("utf-8")).hexdigest(),
                 "release_sha256": _sha256(home / "release"),
                 "libjvm_sha256": _sha256(Path(jpype.getDefaultJVMPath()))},
    }


def run_development(benchmark: Path, output: Path, *, root: Path = ROOT) -> dict:
    benchmark, output, root = Path(benchmark).resolve(), Path(output).resolve(), Path(root).resolve()
    if output.exists():
        raise ValueError("output already exists; choose a new directory")

    # Do not use verify_benchmark: it reads raw and held-out splits as well.
    manifest_path = benchmark / "manifest.json"
    benchmark_bytes = manifest_path.read_bytes()
    manifest = json.loads(benchmark_bytes)
    try:
        development = manifest["splits"]["development"]
        hashes = development["sha256"]
        input_bytes = _checked_bytes(benchmark / "development.inputs.jsonl", hashes["inputs"])
        gold_bytes = _checked_bytes(benchmark / "development.gold.jsonl", hashes["gold"])
        protocol_bytes = _checked_bytes(benchmark / "protocol.md", manifest["protocol_sha256"])
    except (KeyError, TypeError) as error:
        raise ValueError("invalid development benchmark manifest") from error
    inputs = [validate_input_record(row) for row in _jsonl(input_bytes)]
    gold = _jsonl(gold_bytes)
    # The existing metric validator rejects duplicate/missing IDs and bad labels.
    metrics(gold, [{"id": row["id"], "predicted": "neutral"} for row in inputs])
    if len(inputs) != development.get("rows"):
        raise ValueError("development row count differs from manifest")

    baseline_manifest = benchmark / "baseline.json"
    verify_manifest(baseline_manifest)
    baseline_bytes = baseline_manifest.read_bytes()
    baseline_predictions, baseline_metrics = {}, {}
    for mode, label, _ in MODES:
        path = benchmark / "runs/development-baseline" / f"modifiers-{mode}.jsonl"
        baseline_predictions[mode] = path.read_bytes()
        baseline_metrics[label] = metrics(gold, _jsonl(baseline_predictions[mode]))

    output.mkdir(parents=True, exist_ok=False)
    candidate = output / "candidate-M"
    snapshot(root, candidate)
    candidate_manifest = output / "candidate-M.json"
    verified = verify_manifest(candidate_manifest)["manifest"]
    files = {item["path"]: item["sha256"] for item in verified["files"]}
    required = {"data/sentiment_lexicon_compiled.json", "requirements-runtime.lock"}
    if not required.issubset(files):
        raise ValueError("candidate M requires compiled lexicon and requirements-runtime.lock")
    runtime = _runtime_provenance(candidate)

    # Evaluate the already verified bytes even if source files later change.
    frozen_inputs = output / "development.inputs.jsonl"
    frozen_inputs.write_bytes(input_bytes)
    (output / "benchmark-manifest.json").write_bytes(benchmark_bytes)
    (output / "baseline-manifest.json").write_bytes(baseline_bytes)
    (output / "protocol.md").write_bytes(protocol_bytes)
    saved_baseline = output / "baseline-predictions"
    saved_baseline.mkdir()
    baseline_hashes = {}
    for mode, content in baseline_predictions.items():
        path = saved_baseline / f"modifiers-{mode}.jsonl"
        path.write_bytes(content)
        baseline_hashes[mode] = _sha256(path)

    candidate_reports, prediction_hashes, runs = {}, {}, {}
    for mode, label, modifiers in MODES:
        prediction_path = output / f"modifiers-{mode}.jsonl"
        start = time.perf_counter()
        result = run_predictions(frozen_inputs, candidate_manifest, prediction_path, modifiers=modifiers)
        runs[label] = {"elapsed_seconds": time.perf_counter() - start,
                       "n": result["n"], "error_counts": result["error_counts"]}
        candidate_reports[label] = metrics(gold, _jsonl(prediction_path.read_bytes()))
        prediction_hashes[mode] = _sha256(prediction_path)

    # Only aggregates enter the report; no gold rows or review text are emitted.
    report = {
        "schema_version": 1, "split": "development", "candidate": "M",
        "independent_final_evaluation": False,
        "limitation": "Development comparison only; previously exposed v1 final is not an independent evaluation.",
        "candidate_M": candidate_reports, "baseline": baseline_metrics,
        "delta_from_baseline": {
            label: {metric: candidate_reports[label][metric] - baseline_metrics[label][metric]
                    for metric in ("accuracy", "macro_f1")}
            for _, label, _ in MODES
        },
        "runs": runs,
    }
    _write_json(output / "report.json", report)
    handoff = {
        "schema_version": 1, "candidate": "M", "status": "development_complete",
        "split": "development", "independent_final_evaluation": False,
        "candidate_snapshot": {"manifest": "candidate-M.json", "sha256": _sha256(candidate_manifest)},
        "source_files_sha256": files,
        "compiled_sha256": files["data/sentiment_lexicon_compiled.json"],
        "runtime_lock_sha256": files["requirements-runtime.lock"],
        "runtime": runtime,
        "protocol_sha256": manifest["protocol_sha256"],
        "development": {"benchmark": str(benchmark), "rows": len(inputs),
                        "manifest_sha256": hashlib.sha256(benchmark_bytes).hexdigest(),
                        "inputs_sha256": hashes["inputs"], "gold_sha256": hashes["gold"]},
        "baseline": {"manifest": str(baseline_manifest),
                     "manifest_sha256": hashlib.sha256(baseline_bytes).hexdigest(),
                     "predictions_sha256": baseline_hashes,
                     "prediction_provenance": "Existing development predictions; hashes captured for this run, baseline not reevaluated."},
        "predictions_sha256": prediction_hashes,
        "report_sha256": _sha256(output / "report.json"),
        "tooling_sha256": {str(path.relative_to(ROOT)): _sha256(path) for path in (
            Path(__file__).resolve(), ROOT / "scripts/benchmark/artifacts.py",
            ROOT / "scripts/benchmark/runner.py", ROOT / "scripts/benchmark/metrics.py",
            ROOT / "scripts/predict_sentiment_benchmark.py",
        )},
    }
    plan = root / "docs/sentiment-redesign-plan.md"
    if plan.is_file():
        handoff["redesign_plan_sha256"] = _sha256(plan)
    _write_json(output / "candidate-manifest.json", handoff)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=ROOT / "artifacts/benchmark/v1")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        run_development(args.benchmark, args.output, root=args.root)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    print(json.dumps({"split": "development", "report": str(args.output / "report.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
