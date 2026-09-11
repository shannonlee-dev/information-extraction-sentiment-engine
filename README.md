# Information Extraction & Sentiment Engine

[![CI](https://github.com/shannonlee-dev/information-extraction-sentiment-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/shannonlee-dev/information-extraction-sentiment-engine/actions/workflows/ci.yml)

규칙 기반 한국어 정보 추출 및 감성 분석 엔진입니다. 이메일, 전화번호, 날짜, 금액, URL을 정규화해 추출하고 감성 사전·강조·부정 규칙으로 문장 점수를 계산합니다.

## Features

- 이메일, 전화번호, 날짜, 금액, URL 추출과 유효성 검사
- 추출값 정규화 및 제외 사유(diagnostics) 제공
- 613개 감성 표현의 최장 일치 매칭
- 강조어·부정어·대표 이중부정 처리
- 추출 및 감성 평가, JSON·Markdown·CSV·PNG 결과 저장

## Requirements

- Python 3.10+
- Matplotlib (평가 그래프 생성 시)

## Install

```bash
git clone https://github.com/shannonlee-dev/information-extraction-sentiment-engine.git
cd information-extraction-sentiment-engine
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Windows에서는 가상환경을 `.venv\Scripts\activate`로 활성화합니다.

## Usage

문장을 분석합니다.

```bash
python -m sentiment_engine --text "문의: test@example.com, 결제 금액은 50,000원입니다. 정말 좋지 않아요."
```

평가 데이터를 실행합니다.

```bash
python -m sentiment_engine --evaluate extraction
python -m sentiment_engine --evaluate sentiment
python -m sentiment_engine --evaluate all
```

기본 출력은 터미널에서는 사람이 읽기 쉬운 텍스트이며, 파이프나 리다이렉션에서는 JSON입니다.

```bash
# 저장하지 않고 JSON 출력
python -m sentiment_engine --text "배송이 빨라요" --format json --no-save

# 결과를 지정한 위치에 저장
python -m sentiment_engine --evaluate all --output-dir artifacts/reports
```

`main.py`도 동일한 명령행 인터페이스를 제공합니다.

## Python API

```python
from sentiment_engine.analysis import analyze_text
from sentiment_engine.extraction import extract_information
from sentiment_engine.sentiment import analyze_sentiment

result = analyze_text("배송이 빨라요. 문의는 help@example.com으로 주세요.")
sentiment = analyze_sentiment("정말 좋지 않아요")
extraction = extract_information("결제 금액은 50,000원입니다.")
```

`extract_information()`과 `analyze_sentiment()`의 반환 객체는 `to_dict()`로 JSON 직렬화 가능한 딕셔너리로 변환할 수 있습니다.

## Output

명령은 기본적으로 `artifacts/` 아래에 결과를 저장합니다.

- 일반 분석: `summary.md`, `result.json`
- 추출 평가: `summary.md`, `result.json`
- 감성·전체 평가: `summary.md`, `result.json`, `comparison.csv`, `comparison.png`

`--no-save`를 사용하면 파일을 생성하지 않습니다.

## Development

```bash
python -m pytest -q
python -m pytest tests/unit -q
python -m pytest tests/integration -q
```

## Limitations

이 엔진은 형태소 분석이나 학습 모델을 사용하지 않습니다. 새 표현, 오타, 복잡한 문맥, 반어 및 일반적인 이중부정은 규칙 범위 밖일 수 있습니다.

평가 데이터와 지표, 실패 사례는 [평가 리포트](docs/evaluation-report.md)를 참고하세요.
