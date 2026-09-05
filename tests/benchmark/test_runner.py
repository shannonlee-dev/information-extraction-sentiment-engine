import json

import pytest


def test_snapshot_excludes_env_and_verify_detects_one_byte_change(tmp_path):
    from scripts.benchmark.artifacts import snapshot, verify_manifest

    root = tmp_path / "repo"
    (root / "src" / "sentiment_engine").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "src" / "sentiment_engine" / "__init__.py").write_text("", encoding="utf-8")
    (root / "data" / "sentiment_lexicon.json").write_text("[]", encoding="utf-8")
    (root / "data" / "modifiers.json").write_text("{}", encoding="utf-8")
    (root / ".env").write_text("SECRET=do-not-copy", encoding="utf-8")
    (root / "main.py").write_text("print('ok')", encoding="utf-8")

    manifest_path = tmp_path / "baseline.json"
    snapshot(root, tmp_path / "baseline")

    assert verify_manifest(manifest_path)["valid"] is True
    assert not (tmp_path / "baseline" / ".env").exists()
    target = tmp_path / "baseline" / "data" / "sentiment_lexicon.json"
    target.write_text("[1]", encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        verify_manifest(manifest_path)


def test_runner_rejects_manifest_with_missing_snapshot_file(tmp_path):
    from scripts.benchmark.artifacts import verify_manifest

    path = tmp_path / "broken.json"
    path.write_text(json.dumps({"snapshot_root": str(tmp_path / "missing"), "files": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="snapshot"):
        verify_manifest(path)


def test_prediction_worker_input_contract_has_no_gold_fields():
    from scripts.benchmark.runner import validate_input_record

    assert validate_input_record({"id": "x", "text": "좋다"}) == {"id": "x", "text": "좋다"}
    with pytest.raises(ValueError, match="id/text"):
        validate_input_record({"id": "x", "text": "좋다", "label": "positive"})


def test_runner_executes_candidate_from_snapshot_only(tmp_path):
    from scripts.benchmark.artifacts import snapshot
    from scripts.benchmark.runner import run_predictions

    project_root = __import__("pathlib").Path(__file__).resolve().parents[2]
    manifest = tmp_path / "candidate.json"
    snapshot(project_root, tmp_path / "candidate")
    inputs = tmp_path / "inputs.jsonl"
    inputs.write_text('{"id":"one","text":"정말 좋다"}\n{"id":"two","text":"오늘은 수요일이다."}\n', encoding="utf-8")

    result = run_predictions(inputs, manifest, tmp_path / "predictions.jsonl", modifiers=True)

    rows = [json.loads(line) for line in (tmp_path / "predictions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert result["n"] == 2
    assert [row["id"] for row in rows] == ["one", "two"]
    assert rows[0]["predicted"] == "positive"
