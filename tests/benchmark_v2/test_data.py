import json

import pytest

from scripts.benchmark.artifacts import _sha256
from scripts.benchmark_v2.data import load_split, verify_benchmark


def test_split_preserves_source_and_gold_is_separate(benchmark):
    verify_benchmark(benchmark)
    inputs, gold = load_split(benchmark, "selection")
    assert inputs[0] == {"id": "selection:0", "text": "selection good"}
    assert "text" not in gold[0]


@pytest.mark.parametrize("mutation,error", [("label", "id/text"), ("count", "row count"),
                                             ("id", "alignment"), ("duplicate", "unique"),
                                             ("label_value", "label")])
def test_split_validation_even_with_updated_hash(benchmark, mutation, error):
    kind = "gold" if mutation in ("id", "label_value") else "inputs"
    path = benchmark / f"selection.{kind}.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if mutation == "label":
        rows[0]["label"] = "positive"
    elif mutation == "count":
        rows.pop()
    elif mutation == "id":
        rows[0]["id"] = "wrong"
    elif mutation == "duplicate":
        rows[1]["id"] = rows[0]["id"]
    else:
        rows[0]["label"] = "neutral"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    manifest_path = benchmark / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["splits"]["selection"]["sha256"][kind] = _sha256(path)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=error):
        load_split(benchmark, "selection")


def test_split_hash_mismatch(benchmark):
    (benchmark / "final.inputs.jsonl").write_text("tampered")
    with pytest.raises(ValueError, match="split hash"):
        verify_benchmark(benchmark)
