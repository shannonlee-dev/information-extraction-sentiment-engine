# Information Extraction & Sentiment Engine

[![CI](https://github.com/shannonlee-dev/information-extraction-sentiment-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/shannonlee-dev/information-extraction-sentiment-engine/actions/workflows/ci.yml)

정규식 기반 정보 추출과 사전 기반 감성 분석을 제공하는 한국어 NLP 라이브러리 및 CLI.

- **정보 추출**: 이메일·전화번호·날짜·금액·URL 탐지, 유효성 검사 및 정규화
- **감성 분석**: 강조·부정·일부 이중부정을 반영한 점수와 `positive` / `negative` / `neutral` 분류
- **평가**: 추출 Precision·Recall·F1, 감성 Accuracy·Macro F1 및 수식어 적용 전후 비교

분석은 Python 표준 라이브러리로 동작하며, 평가 그래프에는 Matplotlib을 사용한다.

## 설치

Python 3.10 이상. 저장소 루트에서 실행한다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
```

Windows에서는 `python -m venv .venv`로 생성한 뒤 PowerShell에서 `.venv\Scripts\Activate.ps1`로 활성화한다.

## 사용법

### CLI

설치 없이 저장소의 소스를 바로 실행할 수도 있다. `--text` 또는 `--evaluate`를 지정한다.
그래프를 저장하려면 위 설치 과정으로 Matplotlib을 설치한다.

```bash
python3 main.py --help
python3 main.py --text "정말 좋지 않아요" --no-save
python3 main.py --evaluate all --no-save
```

패키지 설치 후에는 모듈로 실행한다.

```bash
# 문장 분석
python -m sentiment_engine --text "문의: test@example.com, 결제 금액은 50,000원입니다. 정말 좋지 않아요."

# 전체 평가 및 보고서 생성
python -m sentiment_engine --evaluate all

# 파일 저장 없이 JSON 출력
python -m sentiment_engine --text "정말 좋지 않아요" --format json --no-save
```

| 옵션 | 설명 |
| --- | --- |
| `--text TEXT` | 분석할 문장. `--evaluate`와 함께 사용할 수 없음 |
| `--evaluate {extraction,sentiment,all}` | 평가 대상 선택 |
| `--format {auto,text,json}` | 기본값 `auto`: 터미널은 텍스트, 파이프·리다이렉션은 JSON |
| `--output-dir PATH` | 결과 저장 디렉터리. 기본값 `artifacts/` |
| `--no-save` | 결과 파일 저장 생략. `--output-dir`와 함께 사용할 수 없음 |

분석 결과에는 정규화된 추출 값, 원문 위치, 감성 점수와 단어별 계산 내역이 포함된다. 위 예제의 감성 결과는 `score: -3.0`, `label: negative`다.

### Python API

```python
from sentiment_engine import analyze_text, analyze_sentiment, extract_information

result = analyze_text("문의: test@example.com. 정말 좋지 않아요.")
print(result["sentiment"]["label"])  # negative

entities = extract_information("결제 금액은 50,000원입니다.").to_dict()
sentiment = analyze_sentiment("나쁘지 않다").to_dict()
```

`analyze_sentiment(text, apply_modifiers=False)`로 강조·부정 처리를 끌 수 있다. 추출 위치 `start`와 `end`는 Python 문자열 인덱스이며, `end`는 포함하지 않는다.

## 결과 파일

기본 실행은 `artifacts/`에 결과를 저장한다. 분석은 실행별 폴더를 생성하고, 평가는 대상별 최신 결과를 덮어쓴다.

| 경로 | 생성 파일 |
| --- | --- |
| `artifacts/analysis-<실행 ID>/` | `result.json`, `summary.md` |
| `artifacts/evaluation/extraction/` | `result.json`, `summary.md` |
| `artifacts/evaluation/sentiment/` | `result.json`, `summary.md`, `comparison.csv`, `comparison.png` |
| `artifacts/evaluation/all/` | `result.json`, `summary.md`, `comparison.csv`, `comparison.png` |

저장 경로와 오류는 표준 오류(stderr)에 출력한다. 저장 실패 시 분석·평가 결과는 출력되며 종료 코드 1을 반환한다.

## 개발

```bash
python -m pip install -r requirements.txt
python -m pytest -q
```

`requirements.txt`는 개발 의존성을 포함해 소스를 editable 모드로 설치한다.

```text
src/sentiment_engine/
├── analysis.py     # 통합 분석 API
├── cli.py          # 명령행 인터페이스
├── models.py       # 결과 모델
├── extraction/     # 유형별 추출·검증·정규화
├── sentiment/      # 토큰화·사전 매칭·수식어 처리
├── evaluation/     # 데이터 로딩·지표 계산
├── reporting/      # 터미널 출력·보고서·그래프
└── data/           # 감성 사전·수식어·평가 데이터
tests/
├── unit/
└── integration/
```

## 평가 및 한계

추출 65문장, 감성 100문장으로 평가한다. 데이터는 사전·규칙 개발에 사용한 합성 예제로, 독립적인 벤치마크가 아니다. 지표와 실패 사례는 [평가 리포트](docs/evaluation-report.md)를 참고한다.

정규식과 사전에 등록된 표현을 지원하며, 복잡한 활용형·부정 범위·반어·담화 문맥은 처리에 한계가 있다. 국제 전화번호, 점 구분 날짜, 소수 달러 금액, 스킴 없는 URL은 지원하지 않는다.
