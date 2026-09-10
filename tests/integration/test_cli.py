"""명령행 분석·평가와 오류 응답을 검증한다."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(params=['script', 'module'])
def command(request):
    if request.param == 'script':
        return [sys.executable, str(ROOT / 'main.py')]
    return [sys.executable, '-m', 'sentiment_engine']


def test_cli_analysis_and_evaluation(tmp_path, command):
    text = '문의: test@example.com, 결제 금액은 50,000원입니다. 정말 좋지 않아요.'
    run = subprocess.run([*command, '--text', text],
                         cwd=tmp_path, capture_output=True, text=True, check=True)
    result = json.loads(run.stdout)
    assert [item['type'] for item in result['extractions']] == ['email', 'money']
    assert result['sentiment']['score'] == -3
    run = subprocess.run([*command, '--evaluate', 'all'],
                         cwd=tmp_path, capture_output=True, text=True, check=True)
    report = json.loads(run.stdout)
    assert 'per_type' in report['extraction']
    assert 'with_modifiers' in report['sentiment']


def test_cli_rejects_blank_input(command):
    run = subprocess.run([*command, '--text', ' '],
                         capture_output=True, text=True)
    assert run.returncode == 2
    assert 'blank' in run.stderr


@pytest.mark.parametrize('mode', ['extraction', 'sentiment', 'all'])
def test_text_evaluation_summary(tmp_path, command, mode):
    run = subprocess.run([*command, '--evaluate', mode, '--format', 'text', '--no-save'],
                         cwd=tmp_path, capture_output=True, text=True, check=True)
    assert '프로젝트 작성 평가 데이터' in run.stdout
    assert '"errors"' not in run.stdout
    if mode in ('extraction', 'all'):
        assert '0.9500' in run.stdout
        assert '누락·추가 추출 오류: 6건' in run.stdout
    if mode in ('sentiment', 'all'):
        assert '100문장' in run.stdout
        assert '0.8800' in run.stdout
        assert '+0.1800' in run.stdout
    assert run.stderr == ''


def test_text_analysis_summary(command):
    run = subprocess.run([*command, '--text', '50,000원입니다. 정말 좋지 않아요.',
                          '--format', 'text', '--no-save'],
                         capture_output=True, text=True, check=True)
    assert '부정' in run.stdout
    assert '점수 -3' in run.stdout
    assert '50,000 KRW' in run.stdout


@pytest.mark.parametrize('tty', [False, True])
@pytest.mark.parametrize('output_format', ['auto', 'text', 'json'])
def test_output_selection(monkeypatch, capsys, tty, output_format):
    from sentiment_engine.cli import main

    monkeypatch.setattr(sys.stdout, 'isatty', lambda: tty)
    main(['--text', '좋다', '--no-save', '--format', output_format])
    output = capsys.readouterr()
    if output_format == 'text' or (output_format == 'auto' and tty):
        assert '감성  긍정' in output.out
    else:
        assert json.loads(output.out)['sentiment']['label'] == 'positive'
    assert output.err == ''


def test_missing_matplotlib_guidance(monkeypatch, capsys):
    from sentiment_engine import cli

    def missing_dependency(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'matplotlib'", name='matplotlib')

    monkeypatch.setattr(cli, 'save_artifacts', missing_dependency)
    with pytest.raises(SystemExit) as error:
        cli.main(['--evaluate', 'sentiment', '--format', 'json'])
    output = capsys.readouterr()
    assert error.value.code == 1
    assert 'sentiment' in json.loads(output.out)
    assert 'python -m pip install' in output.err
    assert '--no-save' in output.err
