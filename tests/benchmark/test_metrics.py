import pytest


def test_metrics_matches_hand_calculation_contract():
    from scripts.benchmark.metrics import metrics

    gold = [
        {"id": "1", "label": "positive", "group_id": "a"},
        {"id": "2", "label": "positive", "group_id": "b"},
        {"id": "3", "label": "negative", "group_id": "a"},
        {"id": "4", "label": "negative", "group_id": "b"},
    ]
    predictions = [
        {"id": "1", "predicted": "positive"},
        {"id": "2", "predicted": "analysis_error"},
        {"id": "3", "predicted": "positive"},
        {"id": "4", "predicted": "neutral"},
    ]

    result = metrics(gold, predictions)

    assert result["accuracy"] == 0.25
    assert result["macro_f1"] == 0.25
    assert result["per_class"]["positive"]["precision"] == 0.5
    assert result["per_class"]["positive"]["recall"] == 0.5
    assert result["per_class"]["negative"]["f1"] == 0.0
    assert result["prediction_counts"]["analysis_error"] == 1
    assert sum(sum(row.values()) for row in result["confusion_matrix"].values()) == 4


def test_metrics_rejects_empty_or_mismatched_ids():
    from scripts.benchmark.metrics import metrics

    with pytest.raises(ValueError, match="empty"):
        metrics([], [])
    with pytest.raises(ValueError, match="IDs"):
        metrics([{"id": "a", "label": "positive"}], [{"id": "b", "predicted": "positive"}])


def test_wilson_covers_boundary_counts():
    from scripts.benchmark.metrics import wilson

    assert wilson(0, 4)[0] == 0.0
    assert wilson(4, 4)[1] == 1.0
    with pytest.raises(ValueError):
        wilson(5, 4)


def test_paired_bootstrap_uses_same_group_resamples():
    pytest.importorskip("numpy")
    from scripts.benchmark.metrics import paired_intervals

    gold = [
        {"id": "1", "label": "positive", "group_id": "a"},
        {"id": "2", "label": "negative", "group_id": "a"},
        {"id": "3", "label": "positive", "group_id": "b"},
        {"id": "4", "label": "negative", "group_id": "b"},
    ]
    predictions = [{"id": row["id"], "predicted": row["label"]} for row in gold]

    result = paired_intervals(gold, predictions, predictions, seed=20260906, repeats=20)

    assert result["a"]["accuracy"] == [1.0, 1.0]
    assert result["delta"]["accuracy"] == [0.0, 0.0]
