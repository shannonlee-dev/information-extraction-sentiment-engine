import hashlib
import json

import pytest


def test_prepare_records_actual_counts_and_refuses_overwrite(tmp_path):
    from scripts.prepare_sentiment_benchmark import prepare
    source = tmp_path / "data.tsv"
    source.write_text("".join(f"{5 if i % 2 else 1}\tr-{i}\n" for i in range(8001)), encoding="utf-8")
    manifest = tmp_path / "source.json"
    manifest.write_text(json.dumps({"sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                                    "size": source.stat().st_size}))
    protocol, exposures = tmp_path / "protocol.md", tmp_path / "exposures.jsonl"
    protocol.write_text("test contract")
    exposures.write_text('{"text":"r-3"}\n')
    output = tmp_path / "benchmark"
    result = prepare(source, manifest, protocol, exposures, output, 20260905)
    for split, info in result["splits"].items():
        actual = (output / f"{split}.inputs.jsonl").read_text().splitlines()
        assert info["rows"] == len(actual)
    assert result["source_rows"] == 8001
    assert sum(x["rows"] for x in result["splits"].values()) + result["reserve_rows"] == 8001
    assert result["cross_split_pairs"] == []
    assert (output / "exposures.jsonl").read_bytes() == exposures.read_bytes()
    with pytest.raises(ValueError, match="already prepared"):
        prepare(source, manifest, protocol, exposures, output, 20260905)
