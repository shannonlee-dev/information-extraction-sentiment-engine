"""CLI 결과 저장, 보고서 생성 및 저장 실패 동작."""
import csv
import json
import subprocess
import sys


def run_cli(tmp_path, *args):
    return subprocess.run(
        [sys.executable, '-m', 'sentiment_engine', *args],
        cwd=tmp_path, capture_output=True, text=True,
    )


def test_analysis_is_saved_without_overwriting_previous_runs(tmp_path):
    for text in ('문의: test@example.com', '정말 좋지 않아요'):
        run = run_cli(tmp_path, '--text', text)
        assert run.returncode == 0, run.stderr
        result = json.loads(run.stdout)
        saved = list((tmp_path / 'artifacts').glob('analysis-*/result.json'))
        assert any(json.loads(path.read_text()) == result for path in saved)
        assert 'result.json' in run.stderr
    assert len(saved) == 2


def test_sentiment_evaluation_saves_table_and_charts(tmp_path):
    run = run_cli(tmp_path, '--evaluate', 'sentiment', '--output-dir', 'reports')
    assert run.returncode == 0, run.stderr
    folders = list((tmp_path / 'reports').glob('evaluation-*'))
    assert len(folders) == 1
    folder = folders[0]
    result = json.loads(run.stdout)
    assert json.loads((folder / 'result.json').read_text()) == result
    with (folder / 'comparison.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert [row['metric'] for row in rows] == ['Accuracy', 'Macro F1']
    assert float(rows[0]['off']) == 0.7
    assert float(rows[0]['on']) == 0.88
    assert float(rows[0]['delta']) == 0.18
    assert '저장 완료' in run.stderr
    assert 'Accuracy' not in run.stderr
    assert (folder / 'comparison.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    assert {path.name for path in folder.iterdir()} == {
        'result.json', 'comparison.csv', 'comparison.png',
    }


def test_no_save_keeps_terminal_evaluation_without_creating_files(tmp_path):
    run = run_cli(tmp_path, '--evaluate', 'all', '--no-save')
    assert run.returncode == 0, run.stderr
    assert 'extraction' in json.loads(run.stdout)
    assert run.stderr == ''
    assert list(tmp_path.iterdir()) == []


def test_extraction_evaluation_only_saves_json(tmp_path):
    run = run_cli(tmp_path, '--evaluate', 'extraction')
    assert run.returncode == 0, run.stderr
    folder, = (tmp_path / 'artifacts').iterdir()
    assert [p.name for p in folder.iterdir()] == ['result.json']


def test_invalid_output_directory_reports_failure_without_losing_stdout(tmp_path):
    (tmp_path / 'blocked').write_text('keep me')
    run = run_cli(tmp_path, '--text', '좋다', '--output-dir', 'blocked')
    assert run.returncode != 0
    assert json.loads(run.stdout)['sentiment']['score'] == 2
    assert '저장 실패' in run.stderr
    assert (tmp_path / 'blocked').read_text() == 'keep me'
