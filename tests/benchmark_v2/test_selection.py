import json

import pytest

from scripts.benchmark_v2.evaluator import choose_candidate, run_selection, run_final
from scripts.benchmark_v2.release import freeze_selection, verify_release


def score(accuracy, f1, positive=.6, negative=.6, errors=0):
    return {"accuracy": accuracy, "macro_f1": f1, "analysis_error_rate": errors,
            "per_class": {"positive": {"recall": positive}, "negative": {"recall": negative}}}


@pytest.mark.parametrize("reports,expected", [
    ({"M2-L": score(.70, .68), "M2-LH": score(.71, .67)}, "M2-LH"),
    ({"M2-L": score(.70, .69), "M2-LH": score(.704, .68)}, "M2-L"),
    ({"M2-LH": score(.70, .68), "M2-L": score(.70, .68)}, "M2-L"),
    ({"M2-L": score(.70, .68), "M2-LH": score(.9, .8, negative=.54)}, "M2-L"),
    ({"M2-L": score(.70, .68), "M2-LH": score(.9, .8, errors=.026)}, "M2-L"),
])
def test_preregistered_selection_rule(reports, expected):
    assert choose_candidate(reports) == expected


def test_no_eligible_candidate():
    with pytest.raises(ValueError, match="eligible"):
        choose_candidate({"M2-L": score(.7, .68, positive=.54)})


def test_selection_release_runs_final_once(selection):
    root = selection
    report = run_selection(root, root / "selection.json", root / "selection-output")
    release_path = root / "selection-output/release.json"
    release = verify_release(release_path, root)
    assert release["format"] == 2
    assert release["selection_report_sha256"]
    assert report["chosen"] == "M2-L"
    final = run_final(root, release_path, root / "final-output")
    assert final["primary_passed"] is True
    assert final["candidate"]["accuracy"] == 1.0
    with pytest.raises((ValueError, FileExistsError), match="attempt"):
        run_selection(root, root / "selection.json", root / "retry")
    with pytest.raises((ValueError, FileExistsError), match="attempt"):
        run_final(root, release_path, root / "final-retry")


def test_selection_report_is_bound_to_release(selection):
    run_selection(selection, selection / "selection.json", selection / "out")
    (selection / "out/report.json").write_text("{}")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_release(selection / "out/release.json", selection)


@pytest.mark.parametrize("names", [["M2-L", "M2-LH", "M2-LHC", "extra"], ["unknown"]])
def test_candidate_limit_and_names(benchmark, names):
    with pytest.raises(ValueError, match="candidate"):
        freeze_selection(benchmark, {name: benchmark / "candidate.json" for name in names},
                         benchmark / "baseline.json", benchmark / "selection.json",
                         benchmark / "protocol.md", benchmark / "exposures.jsonl")
    assert not (benchmark / "selection-attempt.json").exists()


def test_three_distinct_candidates_use_preregistered_simplicity(benchmark):
    from scripts.benchmark.artifacts import snapshot
    root = benchmark
    snapshot(root / "candidate", root / "candidate-h")
    snapshot(root / "candidate", root / "candidate-hc")
    freeze_selection(root, {"M2-LHC": root / "candidate-hc.json", "M2-LH": root / "candidate-h.json",
                            "M2-L": root / "candidate.json"}, root / "baseline.json", root / "selection.json",
                     root / "protocol.md", root / "exposures.jsonl")
    report = run_selection(root, root / "selection.json", root / "out")
    assert report["chosen"] == "M2-L"
    assert len(report["candidates"]) == 3


def test_ineligible_selection_preserves_report_without_release(benchmark):
    from scripts.benchmark.artifacts import snapshot
    root = benchmark
    engine = root / "candidate/src/sentiment_engine/__init__.py"
    engine.write_text(engine.read_text().replace('text.endswith("good")', 'True'))
    snapshot(root / "candidate", root / "one-sided")
    freeze_selection(root, {"M2-L": root / "one-sided.json"}, root / "baseline.json", root / "selection.json",
                     root / "protocol.md", root / "exposures.jsonl")
    with pytest.raises(ValueError, match="eligible"):
        run_selection(root, root / "selection.json", root / "out")
    report = json.loads((root / "out/report.json").read_text())
    assert report["chosen"] is None
    assert report["candidates"]["M2-L"]["accuracy"] == .5
    assert not (root / "out/release.json").exists()
    with pytest.raises(ValueError, match="attempt"):
        run_selection(root, root / "selection.json", root / "retry")


def test_selection_does_not_decode_final_data(selection, monkeypatch):
    from pathlib import Path
    original = Path.read_text
    def guarded(path, *args, **kwargs):
        assert path.name not in ("final.inputs.jsonl", "final.gold.jsonl")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", guarded)
    assert run_selection(selection, selection / "selection.json", selection / "out")["chosen"] == "M2-L"
