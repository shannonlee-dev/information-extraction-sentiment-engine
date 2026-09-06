import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts.benchmark.artifacts import _sha256, snapshot, verify_manifest
from scripts import run_engine_development as development


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "src/sentiment_engine").mkdir(parents=True)
    (root / "src/sentiment_engine/__init__.py").write_text("# frozen candidate\n")
    (root / "data").mkdir()
    for name in ("sentiment_lexicon.json", "modifiers.json"):
        (root / "data" / name).write_text("{}")
    (root / "data/sentiment_lexicon_compiled.json").write_text('{"analyzer": {"files": {}}}')
    (root / "requirements-runtime.lock").write_text("konlpy==0.6.0\n")
    benchmark = tmp_path / "benchmark"
    benchmark.mkdir()
    (benchmark / "protocol.md").write_text("fixed development protocol\n")
    write_jsonl(benchmark / "development.inputs.jsonl", [
        {"id": "a", "text": "fixture-positive"}, {"id": "b", "text": "fixture-negative"},
    ])
    write_jsonl(benchmark / "development.gold.jsonl", [
        {"id": "a", "label": "positive"}, {"id": "b", "label": "negative"},
    ])
    manifest = {"protocol_sha256": _sha256(benchmark / "protocol.md"), "splits": {
        "development": {"rows": 2, "sha256": {
            kind: _sha256(benchmark / f"development.{kind}.jsonl") for kind in ("inputs", "gold")
        }},
        "selection": {"sha256": {"inputs": "must-not-read"}},
        "final": {"sha256": {"gold": "must-not-read"}},
    }}
    (benchmark / "manifest.json").write_text(json.dumps(manifest))
    snapshot(root, benchmark / "baseline")
    baseline_runs = benchmark / "runs/development-baseline"
    baseline_runs.mkdir(parents=True)
    for mode in ("on", "off"):
        write_jsonl(baseline_runs / f"modifiers-{mode}.jsonl", [
            {"id": "a", "predicted": "positive"}, {"id": "b", "predicted": "positive"},
        ])
    monkeypatch.setattr(development, "_runtime_provenance", lambda candidate: {
        "analyzer": {"files": {}}, "java": {"properties_sha256": "jdk-properties"},
    })
    calls = []

    def fake_worker(inputs, candidate_manifest, output, *, modifiers):
        assert inputs.name == "development.inputs.jsonl"
        verify_manifest(candidate_manifest)
        records = [json.loads(line) for line in inputs.read_text().splitlines()]
        assert all(set(row) == {"id", "text"} for row in records)
        calls.append(modifiers)
        write_jsonl(output, [{"id": row["id"], "predicted":
                             ("positive" if row["id"] == "a" else "negative") if modifiers else "neutral"}
                            for row in records])
        return {"n": len(records), "error_counts": {}}

    monkeypatch.setattr(development, "run_predictions", fake_worker)
    return root, benchmark, tmp_path / "output", calls


def test_existing_output_is_refused_before_snapshot_or_worker(prepared, monkeypatch):
    root, benchmark, output, calls = prepared
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("untouched")
    forbidden_snapshot = Mock(side_effect=AssertionError("snapshot must not run"))
    monkeypatch.setattr(development, "snapshot", forbidden_snapshot)
    with pytest.raises(ValueError, match="already exists"):
        development.run_development(benchmark, output, root=root)
    assert marker.read_text() == "untouched"
    assert calls == []
    forbidden_snapshot.assert_not_called()


def test_development_run_never_opens_other_splits_and_freezes_handoff(prepared, monkeypatch):
    root, benchmark, output, calls = prepared
    original_open = Path.open

    def guarded_open(path, *args, **kwargs):
        if benchmark in path.parents:
            assert not any(part in {"raw", "reserve", "selection", "final"} for part in path.parts)
            assert not path.name.startswith(("selection.", "final.", "reserve."))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    development.run_development(benchmark, output, root=root)
    assert calls == [True, False]
    report = json.loads((output / "report.json").read_text())
    assert report["split"] == "development"
    assert report["independent_final_evaluation"] is False
    assert report["candidate_M"]["with_modifiers"]["accuracy"] == 1.0
    assert report["baseline"]["with_modifiers"]["accuracy"] == 0.5
    assert report["delta_from_baseline"]["with_modifiers"]["accuracy"] == 0.5
    assert "fixture-positive" not in (output / "report.json").read_text()
    handoff = json.loads((output / "candidate-manifest.json").read_text())
    assert handoff["candidate_snapshot"]["sha256"] == _sha256(output / "candidate-M.json")
    assert handoff["development"]["inputs_sha256"] == _sha256(benchmark / "development.inputs.jsonl")
    assert handoff["baseline"]["manifest_sha256"] == _sha256(benchmark / "baseline.json")
    assert handoff["baseline"]["predictions_sha256"]["on"] == _sha256(
        benchmark / "runs/development-baseline/modifiers-on.jsonl")
    (root / "src/sentiment_engine/__init__.py").write_text("# changed after freezing\n")
    assert verify_manifest(output / "candidate-M.json")["valid"]


@pytest.mark.parametrize("name", ["development.inputs.jsonl", "development.gold.jsonl", "protocol.md"])
def test_hash_mismatch_prevents_worker_call(prepared, name):
    root, benchmark, output, calls = prepared
    with (benchmark / name).open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="hash mismatch"):
        development.run_development(benchmark, output, root=root)
    assert calls == []


@pytest.mark.parametrize("ids", [("a", "a"), ("a", "other")])
def test_development_ids_are_checked_before_worker(prepared, ids):
    root, benchmark, output, calls = prepared
    gold_path = benchmark / "development.gold.jsonl"
    write_jsonl(gold_path, [{"id": value, "label": "positive"} for value in ids])
    path = benchmark / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["splits"]["development"]["sha256"]["gold"] = _sha256(gold_path)
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="IDs"):
        development.run_development(benchmark, output, root=root)
    assert calls == []


def test_changed_baseline_snapshot_is_rejected_before_worker(prepared):
    root, benchmark, output, calls = prepared
    (benchmark / "baseline/data/modifiers.json").write_text('{"changed": true}')
    with pytest.raises(ValueError, match="hash mismatch"):
        development.run_development(benchmark, output, root=root)
    assert calls == []
