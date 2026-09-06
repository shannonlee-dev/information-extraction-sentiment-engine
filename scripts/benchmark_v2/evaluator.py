"""One-shot selection and final evaluation of frozen M2 candidates."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from scripts.benchmark.artifacts import _sha256
from scripts.benchmark.metrics import metrics, paired_intervals, wilson
from scripts.benchmark.runner import run_predictions
from scripts.benchmark_v2.data import load_split, read_jsonl, write_new_json
from scripts.benchmark_v2.release import (
    CANDIDATES, SELECTION_RULE, TARGETS, publish_selection_release, verify_release, verify_selection,
)


def choose_candidate(reports: dict) -> str:
    if not reports or set(reports) - set(CANDIDATES):
        raise ValueError("invalid selection candidates")
    eligible = [name for name, report in reports.items()
                if report["analysis_error_rate"] <= SELECTION_RULE["maximum_error_rate"]
                and all(report["per_class"][label]["recall"] >= SELECTION_RULE["minimum_recall"]
                        for label in ("positive", "negative"))]
    if not eligible:
        raise ValueError("no eligible selection candidate; attempt remains consumed")
    best_accuracy = max(reports[name]["accuracy"] for name in eligible)
    tied = [name for name in eligible
            if best_accuracy - reports[name]["accuracy"] <= SELECTION_RULE["accuracy_tolerance"] + 1e-12]
    best_f1 = max(reports[name]["macro_f1"] for name in tied)
    return next(name for name in CANDIDATES if name in tied
                and best_f1 - reports[name]["macro_f1"] <= SELECTION_RULE["macro_f1_tolerance"])


def _begin(benchmark: Path, split: str, manifest: Path, output: Path):
    attempt = benchmark / f"{split}-attempt.json"
    if attempt.exists():
        raise ValueError(f"{split} attempt already exists; use a new benchmark version")
    # Exclusive directory creation protects every worker output, not only report.json.
    output.mkdir(parents=True, exist_ok=False)
    write_new_json(attempt, {"benchmark_version": "v2", "split": split, "status": "consumed",
                             "manifest_sha256": _sha256(manifest), "output": str(output.resolve()),
                             "started_at": datetime.now(timezone.utc).isoformat()})


def _evaluate(benchmark, split, candidate, modifiers, output, gold):
    # The reused worker gets only validated id/text records, never gold paths.
    if output.exists():
        raise ValueError("prediction output already exists")
    run_predictions(benchmark / f"{split}.inputs.jsonl", candidate, output, modifiers=modifiers)
    predictions = read_jsonl(output)
    report = metrics(gold, predictions)
    correct = sum(report["confusion_matrix"][label][label] for label in ("positive", "negative"))
    report["wilson_accuracy"] = wilson(correct, report["n"])
    report["analysis_error_rate"] = report["analysis_error_count"] / report["n"]
    for reason in ("no_match", "cancellation", "other_zero"):
        report[f"{reason}_count"] = sum(row.get("neutral_reason") == reason for row in predictions)
    return report, predictions


def run_selection(benchmark: Path, selection_manifest: Path, output: Path):
    selection = verify_selection(selection_manifest, benchmark)
    _begin(benchmark, "selection", selection_manifest, output)
    _, gold = load_split(benchmark, "selection")
    reports = {}
    for name in CANDIDATES:
        if name in selection["candidates"]:
            reports[name], _ = _evaluate(benchmark, "selection", Path(selection["candidates"][name]),
                                        selection["candidate_modifiers"], output / name / "predictions.jsonl", gold)
    payload = {"benchmark_version": "v2", "split": "selection", "candidates": reports,
               "chosen": None, "selection_manifest_sha256": _sha256(selection_manifest)}
    # Preserve aggregate evidence even when all candidates fail eligibility.
    try:
        payload["chosen"] = choose_candidate(reports)
    finally:
        write_new_json(output / "report.json", payload)
    publish_selection_release(benchmark, selection_manifest, output / "report.json", output / "release.json")
    return payload


def run_final(benchmark: Path, release_manifest: Path, output: Path):
    release = verify_release(release_manifest, benchmark)
    _begin(benchmark, "final", release_manifest, output)
    _, gold = load_split(benchmark, "final")
    candidate, predictions = _evaluate(benchmark, "final", Path(release["candidate_manifest"]),
                                       release["candidate_modifiers"], output / "candidate/predictions.jsonl", gold)
    if release["baseline_manifest"] == release["candidate_manifest"]:
        baseline, baseline_predictions = candidate, predictions
    else:
        baseline, baseline_predictions = _evaluate(benchmark, "final", Path(release["baseline_manifest"]),
                                                   True, output / "baseline/predictions.jsonl", gold)
    checks = {"accuracy": candidate["accuracy"] >= TARGETS["accuracy"],
              "macro_f1": candidate["macro_f1"] >= TARGETS["macro_f1"],
              "positive_recall": candidate["per_class"]["positive"]["recall"] >= TARGETS["positive_recall"],
              "negative_recall": candidate["per_class"]["negative"]["recall"] >= TARGETS["negative_recall"],
              "analysis_error_rate": candidate["analysis_error_rate"] <= TARGETS["analysis_error_rate"]}
    payload = {"benchmark_version": "v2", "split": "final", "candidate": candidate, "baseline": baseline,
               "release_manifest_sha256": _sha256(release_manifest),
               "paired_intervals": paired_intervals(gold, baseline_predictions, predictions, seed=20260906),
               "target_checks": checks, "primary_passed": checks["accuracy"],
               "secondary_passed": all(value for name, value in checks.items() if name != "accuracy"),
               "final_exposed": True,
               "next_step": "release" if checks["accuracy"] else "use untouched reserve and benchmark v3; do not rerun"}
    write_new_json(output / "report.json", payload)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--split", choices=("selection", "final"), required=True)
    parser.add_argument("--selection-manifest", type=Path)
    parser.add_argument("--release-manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.split == "selection":
            if args.selection_manifest is None or args.release_manifest is not None:
                raise ValueError("selection requires only a frozen selection manifest")
            run_selection(args.benchmark, args.selection_manifest, args.output)
        else:
            if args.release_manifest is None or args.selection_manifest is not None:
                raise ValueError("final requires only a frozen release manifest; overrides forbidden")
            run_final(args.benchmark, args.release_manifest, args.output)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        parser.error(str(error))
    print(f"Aggregate report: {args.output / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
