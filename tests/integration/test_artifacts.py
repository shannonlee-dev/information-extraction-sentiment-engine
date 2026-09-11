"""CLI 결과 저장, 보고서 생성 및 저장 실패 동작."""

import csv
import json
import subprocess
import sys


def run_cli(tmp_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "sentiment_engine", *args],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )


def test_analysis_is_saved_without_overwriting_previous_runs(tmp_path):
    for text in ("문의: test@example.com", "정말 좋지 않아요"):
        run = run_cli(tmp_path, "--text", text)
        assert run.returncode == 0, run.stderr
        result = json.loads(run.stdout)
        saved = list((tmp_path / "artifacts").glob("analysis-*/result.json"))
        assert any(json.loads(path.read_text()) == result for path in saved)
        assert "result.json" in run.stderr
        assert "summary.md" in run.stderr
    assert len(saved) == 2


def test_sentiment_evaluation_saves_table_and_charts(tmp_path):
    run = run_cli(tmp_path, "--evaluate", "sentiment", "--output-dir", "reports")
    assert run.returncode == 0, run.stderr
    folder = tmp_path / "reports" / "evaluation" / "sentiment"
    result = json.loads(run.stdout)
    assert json.loads((folder / "result.json").read_text()) == result
    with (folder / "comparison.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [row["metric"] for row in rows] == ["Accuracy", "Macro F1"]
    assert float(rows[0]["off"]) == 0.7
    assert float(rows[0]["on"]) == 0.88
    assert float(rows[0]["delta"]) == 0.18
    assert "저장 완료" in run.stderr
    assert "Accuracy" not in run.stderr
    assert (folder / "comparison.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert {path.name for path in folder.iterdir()} == {
        "result.json",
        "comparison.csv",
        "comparison.png",
        "summary.md",
    }
    summary = (folder / "summary.md").read_text(encoding="utf-8")
    assert "100문장 중 88문장 정답" in summary
    assert "| 정확도 | 70.0% | 88.0% | +18.0%p |" in summary
    assert "(comparison.png)" in summary
    assert "오분류 12건" in summary


def test_no_save_keeps_terminal_evaluation_without_creating_files(tmp_path):
    run = run_cli(tmp_path, "--evaluate", "all", "--no-save")
    assert run.returncode == 0, run.stderr
    assert "extraction" in json.loads(run.stdout)
    assert run.stderr == ""
    assert list(tmp_path.iterdir()) == []


def test_extraction_evaluation_saves_json_and_summary(tmp_path):
    run = run_cli(tmp_path, "--evaluate", "extraction")
    assert run.returncode == 0, run.stderr
    folder = tmp_path / "artifacts" / "evaluation" / "extraction"
    assert {p.name for p in folder.iterdir()} == {"result.json", "summary.md"}
    summary = (folder / "summary.md").read_text(encoding="utf-8")
    assert "종합 F1 0.9500" in summary
    assert "정확히 추출 57건 / 추가 추출 0건 / 누락 6건" in summary
    assert "comparison.png" not in summary


def test_summary_survives_missing_chart_dependency(tmp_path, monkeypatch):
    from sentiment_engine.evaluation import compare_sentiment
    from sentiment_engine.reporting import save_artifacts
    from sentiment_engine.reporting import charts
    import pytest

    def missing(*args):
        raise ModuleNotFoundError(name="matplotlib")

    folder = tmp_path / "evaluation" / "sentiment"
    folder.mkdir(parents=True)
    (folder / "comparison.png").write_bytes(b"old chart")
    monkeypatch.setattr(charts, "save_comparison_charts", missing)
    with pytest.raises(ModuleNotFoundError):
        save_artifacts({"sentiment": compare_sentiment([])}, tmp_path, evaluation=True)
    assert not (folder / "comparison.png").exists()
    summary = (folder / "summary.md").read_text(encoding="utf-8")
    assert "0문장 중 0문장 정답" in summary
    assert "오류 사례가 없습니다." in summary
    assert "comparison.png" not in summary


def test_evaluations_reuse_paths_and_keep_modes_separate(tmp_path):
    from sentiment_engine.evaluation import compare_sentiment, evaluate_extraction
    from sentiment_engine.reporting import save_artifacts

    extraction = evaluate_extraction([])
    sentiment = compare_sentiment([])
    for mode, result in (
        ("all", {"extraction": extraction, "sentiment": sentiment}),
        ("sentiment", {"sentiment": sentiment}),
        ("extraction", {"extraction": extraction}),
    ):
        folder = save_artifacts(result, tmp_path, evaluation=True)
        assert folder == tmp_path / "evaluation" / mode
        (folder / "result.json").write_text("old result")
        assert save_artifacts(result, tmp_path, evaluation=True) == folder
        assert json.loads((folder / "result.json").read_text()) == result
    assert {p.name for p in tmp_path.iterdir()} == {"evaluation"}
    assert {p.name for p in (tmp_path / "evaluation").iterdir()} == {
        "all",
        "sentiment",
        "extraction",
    }
    assert not (tmp_path / "evaluation" / "extraction" / "comparison.png").exists()


def test_analysis_summary_escapes_input():
    from sentiment_engine.analysis import analyze_text
    from sentiment_engine.reporting.summary import summary_markdown

    summary = summary_markdown(
        analyze_text("<script>alert(1)</script> | [링크](x) 좋다"), evaluation=False
    )
    assert "<script>" not in summary
    assert "[링크](x)" not in summary
    assert "긍정 · 점수 +2" in summary
    assert "추출된 정보가 없습니다." in summary


def test_invalid_output_directory_reports_failure_without_losing_stdout(tmp_path):
    (tmp_path / "blocked").write_text("keep me")
    run = run_cli(tmp_path, "--text", "좋다", "--output-dir", "blocked")
    assert run.returncode != 0
    assert json.loads(run.stdout)["sentiment"]["score"] == 2
    assert "저장 실패" in run.stderr
    assert (tmp_path / "blocked").read_text() == "keep me"
