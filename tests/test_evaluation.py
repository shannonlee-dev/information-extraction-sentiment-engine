"""데이터 구성, 손으로 계산한 지표, CLI 실행을 검증한다."""
import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from sentiment_engine.evaluation import (
    compare_sentiment, evaluate_extraction, evaluate_sentiment,
    load_extraction_cases, load_sentiment_cases,
)
from sentiment_engine.extraction import extract_information

ROOT = Path(__file__).resolve().parents[1]


def test_fixture_coverage_and_gold_spans():
    extraction = load_extraction_cases()
    assert len(extraction) >= 50
    assert len({c['id'] for c in extraction}) == len(extraction)
    for kind in ('email', 'phone', 'date', 'money', 'url'):
        cases = [c for c in extraction if c['variant'] != 'challenge-unsupported'
                 and any(item['type'] == kind for item in c['expected'])]
        assert len(cases) >= 10
        assert len({c['variant'] for c in cases}) >= 3
    for case in extraction:
        for item in case['expected']:
            assert case['text'][item['start']:item['end']] == item['raw']
    sentiment = load_sentiment_cases()
    assert len(sentiment) >= 100
    assert len({c['id'] for c in sentiment}) == len(sentiment)
    assert all(c['label'] in ('positive', 'negative', 'neutral') for c in sentiment)


def test_extraction_counts_normalization_mismatch_as_fp_and_fn():
    text = 'a@b.co c@d.co'
    gold = [asdict(item) for item in extract_information(text).items]
    gold[1]['normalized'] = 'other@d.co'
    result = evaluate_extraction([{'id': 'one', 'text': text, 'expected': gold}])
    assert result['per_type']['email'] == {
        'tp': 1, 'fp': 1, 'fn': 1, 'precision': 0.5, 'recall': 0.5, 'f1': 0.5,
    }
    assert {e['kind'] for e in result['errors']} == {'fp', 'fn'}


def test_sentiment_known_confusion_including_neutral_error():
    texts = ['좋다', '좋아요', '나쁘다', '좋다', '나쁘다', '오늘은 수요일이다']
    cases = [{'id': str(i), 'text': text, 'label': 'positive' if i < 3 else 'negative'}
             for i, text in enumerate(texts)]
    result = evaluate_sentiment(cases)
    assert result['accuracy'] == 0.5
    assert result['macro_f1'] == pytest.approx(0.533333, abs=1e-6)
    assert result['confusion_matrix']['negative']['neutral'] == 1
    assert len(result['errors']) == 3
    # 중립 정답이 있는 데이터에서는 중립 F1도 평균에 포함한다.
    neutral = [{'id': 'n', 'text': '오늘은 수요일이다', 'label': 'neutral'}]
    assert evaluate_sentiment(neutral)['macro_f1'] == 1


def test_empty_evaluation_has_no_division_by_zero():
    assert evaluate_extraction([])['micro']['f1'] == 0
    assert evaluate_sentiment([])['accuracy'] == 0
    assert evaluate_sentiment([])['macro_f1'] == 0


def test_modifier_comparison_uses_same_sentences():
    cases = [{'id': 'one', 'text': '정말 좋지 않아요', 'label': 'negative'}]
    result = compare_sentiment(cases)
    assert result['without_modifiers']['accuracy'] == 0
    assert result['with_modifiers']['accuracy'] == 1
    assert result['delta']['accuracy'] == 1


def test_full_fixture_evaluation():
    extraction = evaluate_extraction(load_extraction_cases())
    sentiment = compare_sentiment(load_sentiment_cases())
    assert extraction['micro']['recall'] > 0.8
    assert sentiment['with_modifiers']['accuracy'] >= 0.8
    assert sentiment['delta']['accuracy'] > 0
    # 실패를 일부러 만들지는 않는다. 오류 보고 항목이 실제 오분류인지 확인한다.
    for error in sentiment['with_modifiers']['errors']:
        assert error['expected'] != error['predicted']


def test_cli_analysis_and_evaluation(tmp_path):
    text = '문의: test@example.com, 결제 금액은 50,000원입니다. 정말 좋지 않아요.'
    run = subprocess.run([sys.executable, str(ROOT / 'main.py'), '--text', text],
                         cwd=tmp_path, capture_output=True, text=True, check=True)
    result = json.loads(run.stdout)
    assert [item['type'] for item in result['extractions']] == ['email', 'money']
    assert result['sentiment']['score'] == -3
    run = subprocess.run([sys.executable, str(ROOT / 'main.py'), '--evaluate', 'all'],
                         cwd=tmp_path, capture_output=True, text=True, check=True)
    report = json.loads(run.stdout)
    assert 'per_type' in report['extraction']
    assert 'with_modifiers' in report['sentiment']


def test_cli_rejects_blank_input():
    run = subprocess.run([sys.executable, str(ROOT / 'main.py'), '--text', ' '],
                         capture_output=True, text=True)
    assert run.returncode == 2
    assert 'blank' in run.stderr
