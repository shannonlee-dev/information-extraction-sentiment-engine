import json
from pathlib import Path

import pytest

from scripts.benchmark.artifacts import _sha256, snapshot
from scripts.benchmark.release import freeze, verify_release, verify_benchmark
from scripts.evaluate_sentiment_benchmark import main


def benchmark_fixture(tmp_path):
    root = tmp_path / "benchmark"
    root.mkdir()
    (root / "raw.tsv").write_text("5\talpha\n1\tbeta\n", encoding="utf-8")
    for name in ("protocol.md", "exposures.jsonl", "groups.jsonl", "exclusions.jsonl"):
        (root / name).write_text("")
    (root / "source.json").write_text("{}")
    data = {"format": 1, "source": {"path": str(root / "raw.tsv"), "sha256": _sha256(root / "raw.tsv")},
            "protocol_sha256": _sha256(root / "protocol.md"),
            "exposure_register_sha256": _sha256(root / "exposures.jsonl"), "splits": {}}
    for split in ("development", "selection", "final"):
        inputs = [{"id": f"{split}:1", "text": "alpha"}, {"id": f"{split}:2", "text": "beta"}]
        gold = [{**item, "label": label, "group_id": item["id"]} for item, label in zip(inputs, ("positive", "negative"))]
        hashes = {}
        for kind, rows in (("inputs", inputs), ("gold", gold)):
            path = root / f"{split}.{kind}.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            hashes[kind] = _sha256(path)
        data["splits"][split] = {"rows": 2, "sha256": hashes}
    (root / "manifest.json").write_text(json.dumps(data))
    snapshot(Path(__file__).resolve().parents[2], root / "baseline")
    freeze(root, root / "baseline.json", root / "release.json", root / "protocol.md", root / "exposures.jsonl")
    return root


def test_release_detects_tampered_split(tmp_path):
    root = benchmark_fixture(tmp_path)
    verify_release(root / "release.json", root)
    with (root / "final.inputs.jsonl").open("a") as out:
        out.write("\n")
    with pytest.raises(ValueError, match="split hash"):
        verify_release(root / "release.json", root)


def test_final_requires_release_and_can_only_run_once(tmp_path):
    root = benchmark_fixture(tmp_path)
    output = root / "run"
    args = ["--benchmark", str(root), "--split", "final", "--output", str(output)]
    with pytest.raises(SystemExit):
        main(args + ["--candidate-manifest", str(root / "baseline.json")])
    assert not (root / "final-attempt.json").exists()
    assert main(args + ["--release-manifest", str(root / "release.json")]) == 0
    report = json.loads((output / "report.json").read_text())
    assert report["candidate"]["n"] == 2
    assert report["paired_intervals"]["delta"]["accuracy"] == [0, 0]
    assert "without_modifiers" in report
    with pytest.raises(SystemExit):
        main(["--benchmark", str(root), "--split", "final", "--output", str(root / "retry"),
              "--release-manifest", str(root / "release.json")])


def test_benchmark_checks_row_count_even_with_correct_hash(tmp_path):
    root = benchmark_fixture(tmp_path)
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["splits"]["final"]["rows"] = 3
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="row count"):
        verify_benchmark(root)
