import json


def test_build_register_collects_known_examples_and_deduplicates(tmp_path):
    from scripts.build_exposure_register import build_register

    fixture = tmp_path / "fixture.json"
    fixture.write_text(
        json.dumps({"cases": [{"text": "상품이 좋다"}, {"text": "상품이  좋다"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    python_test = tmp_path / "test_sample.py"
    python_test.write_text('assert analyze("정말 나쁘다")\n', encoding="utf-8")
    markdown = tmp_path / "guide.md"
    markdown.write_text(
        "설명 문단은 등록하지 않는다.\n\n```python\nanalyze_sentiment(\"친절하지 않다\")\n```\n"
        + '`{"text":"문제가 해결되다"}`\n',
        encoding="utf-8",
    )
    manual = tmp_path / "manual.jsonl"
    manual.write_text('{"text":"배송이 늦다","source":"conversation"}\n', encoding="utf-8")

    records = build_register(
        fixture_paths=[fixture],
        python_paths=[python_test],
        markdown_paths=[markdown],
        manual_path=manual,
    )

    assert [record["text"] for record in records] == [
        "문제가 해결되다",
        "배송이 늦다",
        "상품이 좋다",
        "정말 나쁘다",
        "친절하지 않다",
    ]
    product = next(record for record in records if record["text"] == "상품이 좋다")
    assert len(product["sources"]) == 2
    assert all(record["id"].startswith("exposure:") for record in records)


def test_build_register_is_deterministic(tmp_path):
    from scripts.build_exposure_register import build_register

    left = tmp_path / "left.py"
    right = tmp_path / "right.py"
    left.write_text('FIRST = "좋아요"\n', encoding="utf-8")
    right.write_text('SECOND = "싫어요"\n', encoding="utf-8")

    first = build_register([], [left, right], [], None)
    second = build_register([], [right, left], [], None)

    assert first == second
