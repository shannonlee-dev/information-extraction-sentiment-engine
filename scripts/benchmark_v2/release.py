"""Freeze candidates and verify a single format-2 release contract."""
from __future__ import annotations

import argparse
import importlib.metadata
import os
import platform
import sys
from pathlib import Path

from scripts.benchmark.artifacts import _relative_files, _sha256, verify_manifest
from scripts.benchmark_v2.data import benchmark_files, read_json, verify_benchmark, write_new_json

ROOT = Path(__file__).resolve().parents[2]
BASELINE_SHA = "0c25c75145f308a572083702f51f3e238169bb42"
CANDIDATES = ("M2-L", "M2-LH", "M2-LHC")
TARGETS = {"accuracy": .70, "macro_f1": .68, "positive_recall": .60,
           "negative_recall": .60, "analysis_error_rate": .025}
SELECTION_RULE = {"accuracy_tolerance": .005, "macro_f1_tolerance": 1e-12,
                  "minimum_recall": .55, "maximum_error_rate": .025,
                  "simplicity_order": list(CANDIDATES)}


def environment():
    packages = {}
    for name in ("numpy", "datasketch", "scipy", "konlpy", "JPype1", "lxml", "packaging"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    jvm = None
    try:
        import jpype
        library = Path(jpype.getDefaultJVMPath()).resolve()
        jvm = {"path": str(library), "sha256": _sha256(library)}
    except (ImportError, OSError, RuntimeError):
        # Record an unavailable runtime explicitly; the engine retains its
        # existing fail-fast semantics if this environment is used to predict.
        pass
    return {"python": sys.version, "executable": sys.executable,
            "implementation": sys.implementation.name, "platform": platform.platform(), "packages": packages,
            "jvm": jvm, "java_environment": {name: os.environ.get(name) for name in
                ("JAVA_HOME", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS")}}


def evaluator_files():
    # Include all executable evaluator dependencies, including reused v1 workers.
    return sorted((ROOT / "scripts").rglob("*.py")) + sorted(
        path for path in ROOT.glob("requirements*") if path.is_file()
    ) + [ROOT / "pyproject.toml"]


def _candidate_files(path: Path):
    manifest = verify_manifest(path)["manifest"]
    root = Path(manifest["snapshot_root"]).resolve()
    expected = {item["path"] for item in manifest["files"]}
    actual = {file.relative_to(root).as_posix() for file in _relative_files(root)}
    if actual != expected or len(expected) != len(manifest["files"]):
        raise ValueError("snapshot inventory mismatch")
    return [path.resolve()] + [(root / item).resolve() for item in sorted(expected)]


def _files(payload: dict, benchmark: Path):
    manifest = verify_benchmark(benchmark)
    paths = benchmark_files(benchmark, manifest) + evaluator_files()
    paths += [Path(payload["protocol"]), Path(payload["exposure_register"])]
    candidates = payload.get("candidates", {})
    candidate_paths = list(candidates.values()) if candidates else [payload["candidate_manifest"]]
    for path in candidate_paths + [payload["baseline_manifest"]]:
        paths += _candidate_files(Path(path))
    if payload.get("selection_manifest"):
        selection = Path(payload["selection_manifest"])
        paths += [selection, Path(payload["selection_report"]), benchmark / "selection-attempt.json"]
        for path in read_json(selection)["candidates"].values():
            paths += _candidate_files(Path(path))
    return {str(path.resolve()): _sha256(path) for path in sorted(set(paths))}


def _common(benchmark, baseline, protocol, exposures):
    manifest = verify_benchmark(benchmark)
    if _sha256(protocol) != manifest["protocol_sha256"] or _sha256(exposures) != manifest["exposure_register_sha256"]:
        raise ValueError("current protocol/exposure hash mismatch")
    return {"format": 2, "benchmark_version": "v2", "baseline_sha": BASELINE_SHA,
            "benchmark": str(benchmark.resolve()), "baseline_manifest": str(baseline.resolve()),
            "candidate_modifiers": True, "selection_manifest": None, "selection_report": None,
            "selection_report_sha256": None, "protocol": str(protocol.resolve()),
            "exposure_register": str(exposures.resolve()),
            "protocol_sha256": manifest["protocol_sha256"],
            "exposure_register_sha256": manifest["exposure_register_sha256"],
            "benchmark_manifest_sha256": _sha256(benchmark / "manifest.json"),
            "environment": environment(), "targets": TARGETS, "selection_rule": SELECTION_RULE}


def _ensure_unstarted(benchmark):
    for name in ("freeze-record.json", "release-record.json", "selection-attempt.json", "final-attempt.json"):
        if (benchmark / name).exists():
            raise ValueError(f"freeze/attempt already exists: {name}")


def _seal(benchmark, path, name):
    write_new_json(benchmark / name, {"manifest": str(path.resolve()), "sha256": _sha256(path)})


def _verify_seal(benchmark, path, name):
    seal = read_json(benchmark / name)
    if seal.get("manifest") != str(path.resolve()) or seal.get("sha256") != _sha256(path):
        raise ValueError("frozen manifest hash mismatch")


def freeze(benchmark: Path, candidate: Path, baseline: Path, output: Path, protocol: Path, exposures: Path):
    """Direct single-candidate release; selection stays unopened."""
    benchmark = benchmark.resolve()
    _ensure_unstarted(benchmark)
    payload = _common(benchmark, baseline, protocol, exposures)
    payload.update(split="final", candidate_manifest=str(candidate.resolve()))
    payload["files"] = _files(payload, benchmark)
    write_new_json(output, payload)
    _seal(benchmark, output, "freeze-record.json")
    _seal(benchmark, output, "release-record.json")
    return payload


def freeze_selection(benchmark: Path, candidates: dict[str, Path], baseline: Path,
                     output: Path, protocol: Path, exposures: Path):
    benchmark = benchmark.resolve()
    _ensure_unstarted(benchmark)
    if not candidates or len(candidates) > 3 or set(candidates) - set(CANDIDATES):
        raise ValueError("selection requires one to three named M2 candidates")
    paths = {name: str(path.resolve()) for name, path in candidates.items()}
    if len(set(paths.values())) != len(paths):
        raise ValueError("duplicate candidate snapshot")
    payload = _common(benchmark, baseline, protocol, exposures)
    payload.update(split="selection", candidates=paths)
    payload["files"] = _files(payload, benchmark)
    write_new_json(output, payload)
    _seal(benchmark, output, "freeze-record.json")
    return payload


def _verify(payload, benchmark, split):
    if (payload.get("format") != 2 or payload.get("benchmark_version") != "v2"
            or payload.get("split") != split or payload.get("benchmark") != str(benchmark.resolve())):
        raise ValueError("release format/benchmark/split mismatch")
    if payload.get("environment") != environment():
        raise ValueError("release environment mismatch")
    if payload.get("targets") != TARGETS or payload.get("selection_rule") != SELECTION_RULE:
        raise ValueError("release policy mismatch")
    if payload.get("candidate_modifiers") is not True:
        raise ValueError("release modifier setting mismatch")
    frozen = payload.get("files")
    if not isinstance(frozen, dict) or not frozen:
        raise ValueError("release lacks frozen hashes")
    for filename, expected in frozen.items():
        if _sha256(Path(filename)) != expected:
            raise ValueError(f"release hash mismatch: {filename}")
    actual = _files(payload, benchmark.resolve())
    if actual != frozen:
        raise ValueError("release file inventory mismatch")
    manifest = verify_benchmark(benchmark)
    for field in ("protocol_sha256", "exposure_register_sha256"):
        if payload[field] != manifest[field]:
            raise ValueError(f"release hash mismatch: {field}")
    if payload["benchmark_manifest_sha256"] != _sha256(benchmark / "manifest.json"):
        raise ValueError("benchmark manifest hash mismatch")
    return payload


def verify_selection(path: Path, benchmark: Path):
    _verify_seal(benchmark, path, "freeze-record.json")
    payload = _verify(read_json(path), benchmark, "selection")
    if not payload.get("candidates") or set(payload["candidates"]) - set(CANDIDATES):
        raise ValueError("invalid selection candidates")
    return payload


def publish_selection_release(benchmark: Path, selection_path: Path, report_path: Path, output: Path):
    """Publish only the preregistered winner of the consumed selection attempt."""
    from scripts.benchmark_v2.evaluator import choose_candidate

    selection = verify_selection(selection_path, benchmark)
    attempt = read_json(benchmark / "selection-attempt.json")
    if (attempt["manifest_sha256"] != _sha256(selection_path)
            or Path(attempt["output"]) / "report.json" != report_path.resolve()):
        raise ValueError("selection attempt/report mismatch")
    report = read_json(report_path)
    if set(report["candidates"]) != set(selection["candidates"]):
        raise ValueError("selection report candidates mismatch")
    chosen = choose_candidate(report["candidates"])
    if report["chosen"] != chosen:
        raise ValueError("selection winner mismatch")
    payload = {key: value for key, value in selection.items() if key not in ("candidates", "files")}
    payload.update(split="final", candidate_manifest=selection["candidates"][chosen],
                   selection_manifest=str(selection_path.resolve()), selection_report=str(report_path.resolve()),
                   selection_report_sha256=_sha256(report_path))
    payload["files"] = _files(payload, benchmark)
    if (benchmark / "final-attempt.json").exists() or (benchmark / "release-record.json").exists():
        raise ValueError("release/final attempt already exists")
    write_new_json(output, payload)
    _seal(benchmark, output, "release-record.json")
    return payload


def verify_release(path: Path, benchmark: Path):
    _verify_seal(benchmark, path, "release-record.json")
    payload = _verify(read_json(path), benchmark, "final")
    if payload["selection_manifest"]:
        selection = verify_selection(Path(payload["selection_manifest"]), benchmark)
        report = read_json(Path(payload["selection_report"]))
        if payload["selection_report_sha256"] != _sha256(Path(payload["selection_report"])):
            raise ValueError("selection report hash mismatch")
        if payload["candidate_manifest"] != selection["candidates"][report["chosen"]]:
            raise ValueError("selected candidate mismatch")
    else:
        _verify_seal(benchmark, path, "freeze-record.json")
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("direct", "selection"))
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--candidate", action="append", required=True, help="NAME=SNAPSHOT_MANIFEST")
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=ROOT / "docs/evaluation/sentiment-protocol-v2.md")
    parser.add_argument("--exposures", type=Path, default=ROOT / "docs/evaluation/exposure-register-v2.jsonl")
    args = parser.parse_args(argv)
    try:
        candidates = {}
        for value in args.candidate:
            name, path = value.split("=", 1)
            if name in candidates or name not in CANDIDATES:
                raise ValueError("duplicate or unknown candidate name")
            candidates[name] = Path(path)
        if args.mode == "direct":
            if len(candidates) != 1:
                raise ValueError("direct release requires one candidate")
            freeze(args.benchmark, next(iter(candidates.values())), args.baseline_manifest,
                   args.output, args.protocol, args.exposures)
        else:
            freeze_selection(args.benchmark, candidates, args.baseline_manifest, args.output,
                             args.protocol, args.exposures)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
