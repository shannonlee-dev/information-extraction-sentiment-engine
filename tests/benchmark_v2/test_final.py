import json

import pytest

from scripts.benchmark_v2.evaluator import main, run_final, run_selection


def test_final_report_and_one_shot(frozen):
    report = run_final(frozen, frozen / "release.json", frozen / "out")
    assert report["candidate"]["n"] == 2
    assert report["candidate"]["confusion_matrix"]["negative"]["negative"] == 1
    assert report["candidate"]["no_match_count"] == 0
    assert report["candidate"]["cancellation_count"] == 0
    assert report["candidate"]["analysis_error_rate"] == 0
    assert report["candidate"]["wilson_accuracy"][0] > 0
    assert report["paired_intervals"]["delta"]["accuracy"] == [0, 0]
    assert all(report["target_checks"].values())
    with pytest.raises((ValueError, FileExistsError), match="attempt"):
        run_final(frozen, frozen / "release.json", frozen / "retry")


@pytest.mark.parametrize("extra", [["--candidate-manifest", "unfrozen.json"], ["--modifiers", "off"]])
def test_cli_rejects_final_overrides(frozen, extra):
    with pytest.raises(SystemExit):
        main(["--benchmark", str(frozen), "--split", "final", "--release-manifest", str(frozen / "release.json"),
              "--output", str(frozen / "out"), *extra])
    assert not (frozen / "final-attempt.json").exists()


def test_final_requires_frozen_release(benchmark):
    with pytest.raises((ValueError, FileNotFoundError)):
        run_final(benchmark, benchmark / "candidate.json", benchmark / "out")
    assert not (benchmark / "final-attempt.json").exists()


@pytest.mark.parametrize("kind", ["selection", "final"])
def test_failure_after_attempt_consumes_run(request, kind, monkeypatch):
    from scripts.benchmark_v2 import evaluator
    root = request.getfixturevalue("selection" if kind == "selection" else "frozen")
    def fail(*args, **kwargs):
        raise RuntimeError("worker failed")
    monkeypatch.setattr(evaluator, "run_predictions", fail)
    run = run_selection if kind == "selection" else run_final
    manifest = root / ("selection.json" if kind == "selection" else "release.json")
    with pytest.raises(RuntimeError, match="worker failed"):
        run(root, manifest, root / "out")
    assert (root / f"{kind}-attempt.json").exists()
    with pytest.raises((ValueError, FileExistsError), match="attempt"):
        run(root, manifest, root / "retry")


@pytest.mark.parametrize("kind", ["selection", "final"])
def test_existing_output_directory_is_never_reused(request, kind):
    root = request.getfixturevalue("selection" if kind == "selection" else "frozen")
    out = root / "out"
    out.mkdir()
    (out / "predictions.jsonl").write_text("keep")
    run = run_selection if kind == "selection" else run_final
    manifest = root / ("selection.json" if kind == "selection" else "release.json")
    with pytest.raises((ValueError, FileExistsError)):
        run(root, manifest, out)
    assert (out / "predictions.jsonl").read_text() == "keep"
    assert not (root / f"{kind}-attempt.json").exists()


def test_failed_final_preserves_exposed_report_and_cannot_retry(benchmark):
    from scripts.benchmark.artifacts import snapshot
    from scripts.benchmark_v2.release import freeze
    root = benchmark
    engine = root / "candidate/src/sentiment_engine/__init__.py"
    engine.write_text(engine.read_text().replace('text.endswith("good")', 'True'))
    snapshot(root / "candidate", root / "one-sided")
    freeze(root, root / "one-sided.json", root / "baseline.json", root / "release.json",
           root / "protocol.md", root / "exposures.jsonl")
    report = run_final(root, root / "release.json", root / "out")
    assert report["candidate"]["accuracy"] == .5
    assert report["primary_passed"] is False
    assert report["final_exposed"] is True
    assert "v3" in report["next_step"]
    previous = (root / "out/report.json").read_bytes()
    with pytest.raises(ValueError, match="attempt"):
        run_final(root, root / "release.json", root / "retry")
    assert (root / "out/report.json").read_bytes() == previous
