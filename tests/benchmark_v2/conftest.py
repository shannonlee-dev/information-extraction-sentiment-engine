import json
from pathlib import Path

import pytest

from scripts.benchmark.artifacts import _sha256, snapshot


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def benchmark(tmp_path):
    root = tmp_path / "benchmark"
    root.mkdir()
    for name in ("raw.tsv", "protocol.md", "exposures.jsonl", "groups.jsonl", "exclusions.jsonl"):
        (root / name).write_text("", encoding="utf-8")
    write_json(root / "source.json", {})
    manifest = {
        "format": 2, "benchmark_version": "v2",
        "source": {"path": str(root / "raw.tsv"), "sha256": _sha256(root / "raw.tsv")},
        "protocol_sha256": _sha256(root / "protocol.md"),
        "exposure_register_sha256": _sha256(root / "exposures.jsonl"), "splits": {},
    }
    for split in ("selection", "final"):
        inputs = [{"id": f"{split}:{i}", "text": f"{split} {'good' if i == 0 else 'bad'}"} for i in range(2)]
        gold = [{"id": row["id"], "label": label, "group_id": row["id"]}
                for row, label in zip(inputs, ("positive", "negative"))]
        hashes = {}
        for kind, rows in (("inputs", inputs), ("gold", gold)):
            path = root / f"{split}.{kind}.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            hashes[kind] = _sha256(path)
        manifest["splits"][split] = {"rows": 2, "sha256": hashes}
    write_json(root / "manifest.json", manifest)
    # A real isolated worker with a tiny deterministic engine; it never sees gold.
    engine = tmp_path / "engine"
    (engine / "src/sentiment_engine").mkdir(parents=True)
    (engine / "data").mkdir()
    (engine / "src/sentiment_engine/__init__.py").write_text('''from types import SimpleNamespace

def analyze_sentiment(text, apply_modifiers=True):
    positive = text.endswith("good")
    return SimpleNamespace(label="positive" if positive else "negative", score=1 if positive else -1, matches=[1])
''')
    for name in ("sentiment_lexicon.json", "modifiers.json"):
        write_json(engine / "data" / name, {})
    snapshot(engine, root / "candidate")
    snapshot(engine, root / "baseline")
    return root


@pytest.fixture
def frozen(benchmark):
    from scripts.benchmark_v2.release import freeze
    freeze(benchmark, benchmark / "candidate.json", benchmark / "baseline.json",
           benchmark / "release.json", benchmark / "protocol.md", benchmark / "exposures.jsonl")
    return benchmark


@pytest.fixture
def selection(benchmark):
    from scripts.benchmark_v2.release import freeze_selection
    freeze_selection(benchmark, {"M2-L": benchmark / "candidate.json"}, benchmark / "baseline.json",
                     benchmark / "selection.json", benchmark / "protocol.md", benchmark / "exposures.jsonl")
    return benchmark
