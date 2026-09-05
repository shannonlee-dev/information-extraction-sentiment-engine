import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from sentiment_engine import analyze, extract_information


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAIN_PATH = PROJECT_ROOT / "main.py"
SAMPLE_TEXT = (
    "support@company.co.kr 02-1234-5678 2024년 3월 15일 50,000원 "
    "https://Example.COM/help 정말 좋지 않다 2024년 2월 30일"
)


def _run_cli(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(MAIN_PATH), *arguments],
        cwd=cwd or PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def test_analyze_combines_all_extractions_sentiment_and_diagnostics() -> None:
    extraction_result = extract_information(SAMPLE_TEXT)

    result = analyze(SAMPLE_TEXT)

    assert [item.type for item in result.extractions] == [
        "email",
        "phone",
        "date",
        "money",
        "url",
    ]
    assert [asdict(item)["normalized"] for item in result.extractions] == [
        "support@company.co.kr",
        "02-1234-5678",
        "2024-03-15",
        {"amount": 50_000, "currency": "KRW"},
        "https://example.com/help",
    ]
    assert result.sentiment.label == "negative"
    assert result.diagnostics == extraction_result.diagnostics
    assert [(item.raw, item.reason) for item in result.diagnostics] == [
        ("2024년 2월 30일", "invalid_calendar_date")
    ]


@pytest.mark.parametrize("text", [None, 123, ["좋다"]])
def test_analyze_rejects_non_string_input(text: object) -> None:
    with pytest.raises(TypeError):
        analyze(text)  # type: ignore[arg-type]


@pytest.mark.parametrize("text", ["", " \t\n"])
def test_analyze_rejects_blank_input(text: str) -> None:
    with pytest.raises(ValueError):
        analyze(text)


def test_json_cli_matches_the_complete_api_result_from_an_independent_cwd(
    tmp_path: Path,
) -> None:
    completed = _run_cli("--text", SAMPLE_TEXT, "--format", "json", cwd=tmp_path)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert "정말" in completed.stdout
    assert "\\uc815\\ub9d0" not in completed.stdout
    assert json.loads(completed.stdout) == asdict(analyze(SAMPLE_TEXT))


def test_default_cli_output_has_analysis_section_labels() -> None:
    completed = _run_cli("--text", SAMPLE_TEXT)

    assert completed.returncode == 0
    assert "Extractions:" in completed.stdout
    assert "Sentiment:" in completed.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        (),
        ("--text", ""),
        ("--text", "문장", "--evaluate", "all"),
        ("--format", "xml", "--text", "문장"),
    ],
)
def test_invalid_cli_invocations_report_errors(arguments: tuple[str, ...]) -> None:
    completed = _run_cli(*arguments)

    assert completed.returncode != 0
    assert completed.stderr
    assert "Traceback" not in completed.stderr


@pytest.mark.parametrize("mode", ["extraction", "sentiment", "all"])
@pytest.mark.parametrize("output_format", ["text", "json"])
def test_evaluation_cli_modes_work_from_independent_cwd(tmp_path, mode, output_format):
    completed = _run_cli("--evaluate", mode, "--format", output_format, cwd=tmp_path)
    assert completed.returncode == 0
    assert completed.stderr == ""
    if output_format == "json":
        result = json.loads(completed.stdout)
        if mode in ("extraction", "all"):
            extraction = result["extraction"] if mode == "all" else result
            assert "per_type" in extraction and "micro" in extraction
        if mode in ("sentiment", "all"):
            sentiment = result["sentiment"] if mode == "all" else result
            assert set(sentiment) == {"without_modifiers", "with_modifiers", "delta"}
    else:
        assert "precision" in completed.stdout
        assert "f1" in completed.stdout


def test_cli_can_evaluate_a_separate_sentiment_dataset(tmp_path):
    from sentiment_engine.evaluation import DEFAULT_SENTIMENT_CASES_PATH
    path = DEFAULT_SENTIMENT_CASES_PATH.with_name("sentiment_validation_cases.json")
    completed = _run_cli("--evaluate", "sentiment", "--sentiment-cases", str(path),
                         "--format", "json", cwd=tmp_path)
    assert completed.returncode == 0
    result = json.loads(completed.stdout)["with_modifiers"]
    assert result["accuracy"] >= 0.8
    assert result["majority_baseline_accuracy"] == 0.5
    assert all(e["case_id"].startswith("validation-") for e in result["errors"])


def test_cli_reports_missing_custom_sentiment_data(tmp_path):
    completed = _run_cli("--evaluate", "sentiment", "--sentiment-cases", str(tmp_path / "missing.json"))
    assert completed.returncode == 2
    assert "evaluation configuration error" in completed.stderr
    assert "Traceback" not in completed.stderr


@pytest.mark.parametrize("arguments", [("--text", "좋다"), ("--evaluate", "extraction")])
def test_custom_sentiment_dataset_is_not_silently_ignored(arguments):
    completed = _run_cli(*arguments, "--sentiment-cases", "unused.json")
    assert completed.returncode == 2
    assert "requires --evaluate sentiment or all" in completed.stderr


@pytest.mark.parametrize("failure", [FileNotFoundError("missing fixtures"), ValueError("bad fixtures"),
    UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad encoding")])
def test_evaluation_cli_reports_fixture_errors(monkeypatch, capsys, failure):
    from sentiment_engine import cli
    def fail():
        raise failure
    monkeypatch.setattr(cli, "load_extraction_cases", fail)
    assert cli.main(["--evaluate", "extraction"]) == 2
    captured = capsys.readouterr()
    assert "evaluation configuration error" in captured.err
    assert captured.out == ""


@pytest.mark.parametrize(
    "failure",
    [
        FileNotFoundError("missing sentiment resource"),
        ValueError("invalid sentiment entry"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
    ],
)
def test_cli_reports_resource_and_configuration_errors_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: Exception,
) -> None:
    from sentiment_engine import cli

    def fail_analysis(text: str) -> None:
        raise failure

    monkeypatch.setattr(cli, "analyze", fail_analysis)

    exit_code = cli.main(["--text", "문장"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "analysis configuration error" in captured.err
    assert str(failure) in captured.err
    assert "Traceback" not in captured.err
