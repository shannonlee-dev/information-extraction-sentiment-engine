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
