"""Evaluate a frozen candidate on one prepared benchmark split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.benchmark.metrics import metrics, paired_intervals, wilson
from scripts.benchmark.runner import run_predictions


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _evaluate_one(benchmark: Path, split: str, manifest: Path, modifiers: bool, output: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    inputs = benchmark / f"{split}.inputs.jsonl"
    gold = _read_jsonl(benchmark / f"{split}.gold.jsonl")
    prediction_path = output / ("modifiers-on.jsonl" if modifiers else "modifiers-off.jsonl")
    run_predictions(inputs, manifest, prediction_path, modifiers=modifiers)
    predictions = _read_jsonl(prediction_path)
    report = metrics(gold, predictions)
    correct = sum(row["gold"] == row["predicted"] for row in ({"gold": g["label"], "predicted": p["predicted"]} for g, p in zip(gold, predictions)))
    report["wilson_accuracy"] = wilson(correct, len(gold))
    return report, predictions


def _manifest_paths(path: Path) -> list[Path]:
    data = json.loads(path.read_text(encoding="utf-8"))
    values = data.get("candidates")
    if not isinstance(values, list) or not values:
        raise ValueError("selection manifest requires nonempty candidates")
    paths = [Path(value["manifest"] if isinstance(value, dict) else value) for value in values]
    return [path if path.is_absolute() else path.resolve() for path in paths]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", required=True, type=Path)
    parser.add_argument("--split", choices=("development", "selection", "final"), required=True)
    parser.add_argument("--candidate-manifest", type=Path)
    parser.add_argument("--selection-manifest", type=Path)
    parser.add_argument("--release-manifest", type=Path)
    parser.add_argument("--modifiers", choices=("on", "off", "both"))
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        if arguments.release_manifest is not None:
            if arguments.split != "final" or arguments.candidate_manifest is not None or arguments.selection_manifest is not None or arguments.modifiers is not None:
                raise ValueError("release evaluation rejects candidate/modifier overrides")
            release = json.loads(arguments.release_manifest.read_text(encoding="utf-8"))
            candidate = Path(release["candidate_manifest"])
            modifiers = bool(release["candidate_modifiers"])
            report, predictions = _evaluate_one(arguments.benchmark, "final", candidate, modifiers, arguments.output / "candidate")
            payload = {"candidate": report, "release": release}
            baseline_value = release.get("baseline_manifest")
            if baseline_value and Path(baseline_value).resolve() != candidate.resolve():
                baseline = Path(baseline_value)
                baseline_report, baseline_predictions = _evaluate_one(
                    arguments.benchmark, "final", baseline, True, arguments.output / "baseline"
                )
                gold = _read_jsonl(arguments.benchmark / "final.gold.jsonl")
                candidate_rows = _read_jsonl(arguments.output / "candidate" / ("modifiers-on.jsonl" if modifiers else "modifiers-off.jsonl"))
                baseline_rows = _read_jsonl(arguments.output / "baseline" / "modifiers-on.jsonl")
                payload["baseline"] = baseline_report
                payload["paired_intervals"] = paired_intervals(gold, baseline_rows, candidate_rows, seed=20260906)
        elif arguments.selection_manifest is not None:
            if arguments.candidate_manifest is not None:
                raise ValueError("selection and candidate manifests are mutually exclusive")
            selection_data = json.loads(arguments.selection_manifest.read_text(encoding="utf-8"))
            candidates = _manifest_paths(arguments.selection_manifest)
            setting = arguments.modifiers or "on"
            if setting == "both":
                raise ValueError("selection accepts one modifier setting")
            reports = {str(path): _evaluate_one(arguments.benchmark, arguments.split, path, setting == "on", arguments.output / path.stem)[0] for path in candidates}
            if len(candidates) > 3:
                raise ValueError("selection accepts at most three candidates")
            baseline = selection_data.get("baseline_manifest", str(candidates[0]))
            baseline_path = Path(baseline)
            if not baseline_path.is_absolute():
                baseline_path = baseline_path.resolve()
            best_path = max(candidates, key=lambda path: reports[str(path)]["macro_f1"])
            best_score = reports[str(best_path)]["macro_f1"]
            eligible = [path for path in candidates if best_score - reports[str(path)]["macro_f1"] <= 0.005]
            chosen = baseline_path if baseline_path in eligible else eligible[0]
            release = {
                "format": 1,
                "split": "final",
                "candidate_manifest": str(chosen),
                "candidate_modifiers": setting == "on",
                "baseline_manifest": str(baseline_path),
                "selection_manifest": str(arguments.selection_manifest.resolve()),
                "selection_scores": reports,
                "tie_break": "baseline first within 0.005 Macro F1; otherwise registration order",
            }
            release_path = arguments.benchmark / "release.json"
            release_path.write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            payload = {"candidates": reports, "release": release}
        else:
            if arguments.candidate_manifest is None:
                raise ValueError("candidate manifest is required")
            setting = arguments.modifiers or "both"
            reports: dict[str, Any] = {}
            if setting in ("off", "both"):
                reports["without_modifiers"], _ = _evaluate_one(arguments.benchmark, arguments.split, arguments.candidate_manifest, False, arguments.output)
            if setting in ("on", "both"):
                reports["with_modifiers"], _ = _evaluate_one(arguments.benchmark, arguments.split, arguments.candidate_manifest, True, arguments.output)
            payload = reports
        arguments.output.mkdir(parents=True, exist_ok=True)
        (arguments.output / "report.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError, ValueError, KeyError, json.JSONDecodeError, RuntimeError) as error:
        parser.error(str(error))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
