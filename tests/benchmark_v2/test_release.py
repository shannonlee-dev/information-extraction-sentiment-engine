import json

import pytest

from scripts.benchmark_v2.release import freeze, verify_release


def test_direct_release_is_frozen_format_two(frozen):
    release = verify_release(frozen / "release.json", frozen)
    assert release["format"] == 2
    assert release["benchmark_version"] == "v2"
    assert release["selection_manifest"] is None
    assert release["targets"]["accuracy"] == 0.70
    assert release["baseline_manifest"] != release["candidate_manifest"]


@pytest.mark.parametrize("name", ["final.inputs.jsonl", "final.gold.jsonl", "protocol.md", "exposures.jsonl",
                                   "manifest.json", "source.json", "groups.jsonl", "exclusions.jsonl",
                                   "candidate.json", "baseline.json", "candidate/src/sentiment_engine/__init__.py",
                                   "baseline/data/modifiers.json"])
def test_frozen_file_tampering_is_rejected(frozen, name):
    path = frozen / name
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_release(frozen / "release.json", frozen)


@pytest.mark.parametrize("field,value", [("candidate_modifiers", False), ("files", {}),
                                          ("candidate_manifest", "unfrozen.json"), ("format", 1)])
def test_release_itself_cannot_be_rewritten(frozen, field, value):
    path = frozen / "release.json"
    data = json.loads(path.read_text())
    data[field] = value
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_release(path, frozen)


def test_runtime_and_evaluator_changes_rejected(frozen, monkeypatch, tmp_path):
    from scripts.benchmark_v2 import release
    original = release.environment()
    monkeypatch.setattr(release, "environment", lambda: {**original, "python": "changed"})
    with pytest.raises(ValueError, match="environment"):
        verify_release(frozen / "release.json", frozen)
    monkeypatch.undo()
    evaluator = tmp_path / "evaluator.py"
    evaluator.write_text("changed")
    monkeypatch.setattr(release, "evaluator_files", lambda: [evaluator])
    with pytest.raises(ValueError, match="file inventory"):
        verify_release(frozen / "release.json", frozen)


def test_snapshot_added_code_is_rejected(frozen):
    (frozen / "candidate/src/sentiment_engine/extra.py").write_text("injected = True")
    with pytest.raises(ValueError, match="snapshot inventory"):
        verify_release(frozen / "release.json", frozen)


def test_release_never_overwrites(frozen):
    previous = (frozen / "release.json").read_bytes()
    with pytest.raises((ValueError, FileExistsError)):
        freeze(frozen, frozen / "candidate.json", frozen / "baseline.json", frozen / "release.json",
               frozen / "protocol.md", frozen / "exposures.jsonl")
    assert (frozen / "release.json").read_bytes() == previous


def test_java_runtime_setting_change_is_rejected(frozen, monkeypatch):
    monkeypatch.setenv("JAVA_HOME", "/different/jdk")
    with pytest.raises(ValueError, match="environment"):
        verify_release(frozen / "release.json", frozen)


def test_evaluator_file_bytes_are_frozen(benchmark, tmp_path, monkeypatch):
    from scripts.benchmark_v2 import release
    helper = tmp_path / "helper.py"
    helper.write_text("original")
    original = release.evaluator_files()
    monkeypatch.setattr(release, "evaluator_files", lambda: original + [helper])
    freeze(benchmark, benchmark / "candidate.json", benchmark / "baseline.json", benchmark / "release.json",
           benchmark / "protocol.md", benchmark / "exposures.jsonl")
    helper.write_text("changed")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_release(benchmark / "release.json", benchmark)


def test_current_protocol_must_match_prepared_copy(benchmark, tmp_path):
    protocol = tmp_path / "current.md"
    protocol.write_text("different policy")
    with pytest.raises(ValueError, match="protocol/exposure hash"):
        freeze(benchmark, benchmark / "candidate.json", benchmark / "baseline.json", benchmark / "release.json",
               protocol, benchmark / "exposures.jsonl")
    assert not (benchmark / "freeze-record.json").exists()


def test_cli_freeze_selection_and_final_lifecycle(benchmark):
    from scripts.benchmark_v2.release import main as freeze_main
    from scripts.benchmark_v2.evaluator import main as evaluate_main
    root = benchmark
    assert freeze_main(["selection", "--benchmark", str(root),
                        "--candidate", f"M2-L={root / 'candidate.json'}",
                        "--baseline-manifest", str(root / "baseline.json"),
                        "--protocol", str(root / "protocol.md"), "--exposures", str(root / "exposures.jsonl"),
                        "--output", str(root / "selection.json")]) == 0
    assert evaluate_main(["--benchmark", str(root), "--split", "selection",
                          "--selection-manifest", str(root / "selection.json"), "--output", str(root / "select")]) == 0
    assert evaluate_main(["--benchmark", str(root), "--split", "final",
                          "--release-manifest", str(root / "select/release.json"), "--output", str(root / "final")]) == 0
    assert json.loads((root / "final/report.json").read_text())["primary_passed"] is True
