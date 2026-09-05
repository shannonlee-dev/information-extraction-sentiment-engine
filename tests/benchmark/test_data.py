import json

import pytest


def test_parser_preserves_text_and_maps_ratings(tmp_path):
    from scripts.benchmark.data import parse_source

    path = tmp_path / "source.tsv"
    path.write_bytes("5\t  좋아요\t🙂  \r\n2\t별로\n3\t보통\nX\t오류\n".encode())

    rows, excluded = parse_source(path)

    assert [row["label"] for row in rows] == ["positive", "negative"]
    assert rows[0]["text"] == "  좋아요\t🙂  "
    assert rows[0]["source_line"] == 1
    assert {item["reason"] for item in excluded} == {"excluded_rating_3", "malformed_record"}


def test_exact_duplicate_conflict_is_not_scored(tmp_path):
    from scripts.benchmark.data import group_rows, parse_source

    path = tmp_path / "source.tsv"
    path.write_text("5\t배송이 빨라요\n1\t 배송이  빨라요 \n", encoding="utf-8")
    rows, _ = parse_source(path)

    groups = group_rows(rows, [])

    assert groups == []


def test_same_polarity_exact_duplicate_keeps_earliest_representative(tmp_path):
    from scripts.benchmark.data import deduplicate_rows

    rows = [
        {"id": "later", "text": "배송이 빨라요", "rating": 5, "label": "positive", "source_line": 2},
        {"id": "first", "text": " 배송이  빨라요 ", "rating": 4, "label": "positive", "source_line": 1},
    ]

    representatives, exclusions = deduplicate_rows(rows)

    assert [row["id"] for row in representatives] == ["first"]
    assert exclusions[0]["reason"] == "duplicate_exact"
    assert exclusions[0]["representative_id"] == "first"


def test_near_groups_are_connected_without_rewriting_source_text(tmp_path):
    from scripts.benchmark.data import group_rows

    base = "abcdefghijklmnopqrstuv"
    rows = [
        {"id": "a", "text": base, "rating": 5, "label": "positive", "source_line": 1},
        {"id": "b", "text": base[:-1] + "w", "rating": 1, "label": "negative", "source_line": 2},
    ]

    groups = group_rows(rows, [])

    assert len(groups) == 1
    assert [row["text"] for row in groups[0]["rows"]] == [rows[0]["text"], rows[1]["text"]]
    assert groups[0]["exposed"] is False


def test_allocation_is_input_order_independent_and_keeps_groups_intact():
    from scripts.benchmark.data import allocate_groups

    groups = [
        {"group_id": f"g-{i}", "rows": [{"id": f"r-{i}", "rating": 1 if i % 2 else 5, "source_line": i}], "exposed": i == 0}
        for i in range(8_000)
    ]

    first = allocate_groups(groups, seed=20260905)
    second = allocate_groups(list(reversed(groups)), seed=20260905)

    assert {key: [row["id"] for row in value] for key, value in first.items()} == {
        key: [row["id"] for row in value] for key, value in second.items()
    }
    assert first["development"][0]["id"] == "r-0"


def test_json_hash_serialization_is_stable():
    from scripts.benchmark.data import stable_hash

    assert stable_hash(["가", "나"]) == stable_hash(["가", "나"])
    assert stable_hash(["가", "나"]) != stable_hash(["나", "가"])
