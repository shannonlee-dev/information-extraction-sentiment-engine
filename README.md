# Information Extraction & Sentiment Engine

[![CI](https://github.com/shannonlee-dev/information-extraction-sentiment-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/shannonlee-dev/information-extraction-sentiment-engine/actions/workflows/ci.yml)

## 프로젝트 소개

NLP Mission 2 제출용 규칙 기반 한국어 NLP 프로젝트다. Python 내장 `re`로 이메일·전화번호·날짜·금액·URL을 추출하고, 감성 사전 점수에 강조어와 부정어를 적용한다. 기존 추출 규칙, 감성 사전, 정답 데이터와 평가 공식을 재사용했다.

## 핵심 특징

- 5종 정보 추출, 유형별 3가지 이상 변형, 유효성 검사와 정규화
- 감성 단어 613개(고객지원 도메인 91개), regex 토큰화, 점수 합산
- 부정·강조·대표 이중부정 처리 및 `positive / negative / neutral` 판정
- 추출 65문장, 감성 100문장 평가와 실제 실패 사례 출력
- 분석 로직은 Python 표준 라이브러리를 사용하고, 평가 그래프 생성에는 Matplotlib을 사용한다. Java, KoNLPy, 모델 다운로드는 필요 없다.

## 아키텍처

```text
.
├── .github/workflows/ci.yml
├── README.md
├── main.py
├── requirements.txt
├── pyproject.toml
├── docs/
│   ├── evaluation-report.md  # 성능 평가와 실패 사례 분석
│   ├── archive/               # 이전 버전 보고서
│   │   └── legacy-engine-report.md
│   └── plans/                 # 구현 계획과 검증 기록
├── src/sentiment_engine/
│   ├── __init__.py
│   ├── __main__.py            # python -m sentiment_engine
│   ├── cli.py
│   ├── analysis.py
│   ├── models.py
│   ├── reporting/             # 출력과 보고서 생성
│   │   ├── __init__.py
│   │   ├── artifacts.py        # 실행별 JSON·보고서 저장
│   │   ├── comparison.py       # 터미널·CSV 비교표
│   │   └── charts.py           # PNG 그래프
│   ├── data/                  # 설치 파일에 포함되는 데이터
│   │   ├── __init__.py        # 패키지 리소스 위치
│   │   ├── lexicons/          # 분석에 사용하는 사전과 수식어
│   │   │   ├── sentiment_lexicon.json
│   │   │   └── modifiers.json
│   │   └── evaluation/        # CLI와 테스트가 공유하는 정답 데이터
│   │       ├── extraction_cases.json
│   │       └── sentiment_cases.json
│   ├── extraction/
│   │   ├── __init__.py       # 공개 API
│   │   ├── pipeline.py       # 입력 검증·실행·결과 정렬
│   │   └── email.py / phone.py / date.py / money.py / url.py
│   ├── sentiment/
│   │   ├── __init__.py       # 공개 API
│   │   ├── analyzer.py       # 점수 합산·결과 생성
│   │   ├── tokenization.py   # 공통 토큰화
│   │   ├── lexicon.py        # 사전 로딩·활용 확장·최장 매칭
│   │   └── modifiers.py      # 강조·부정 계산
│   └── evaluation/
│       ├── __init__.py       # 공개 API
│       ├── datasets.py       # 정답 데이터 로딩
│       ├── metrics.py        # 공통 지표 계산
│       ├── extraction.py     # 추출 평가
│       └── sentiment.py      # 감성 평가·수식어 전후 비교
└── tests/
    ├── unit/                 # 분석 규칙·평가 지표·모듈 계약
    │   ├── test_extraction.py
    │   ├── test_sentiment.py
    │   ├── test_evaluation.py
    │   └── test_module_boundaries.py
    └── integration/          # 프로세스 실행·인자 처리·JSON 출력
        ├── test_cli.py
        └── test_artifacts.py
```

`main.py`와 `__main__.py`는 `cli.py`의 진입점을 호출한다. `cli.py`는 인자 처리와 JSON 출력을, `analysis.py`의 `analyze_text(text)`는 통합 분석을 담당한다. `models.py`는 결과 dataclass와 `to_dict()` 직렬화를 정의한다. `pyproject.toml`에서 패키지 데이터, 개발 의존성, 테스트 경로를 설정한다.

패키지 내부의 `data/lexicons/`는 분석 규칙이 사용하는 데이터이고, `data/evaluation/`은 평가기의 정답 데이터다. 둘 다 패키지에 포함되며 `importlib.resources`로 읽는다. 애플리케이션이 `tests/`나 저장소 루트 위치에 의존하지 않으므로, wheel만 설치해도 분석과 평가를 실행할 수 있다. `tests/fixtures/`는 향후 테스트에서만 필요한 샘플이 생길 때 사용한다.

### 모듈 수정 기준

- 추출 형식 추가·수정은 `extraction/`의 해당 유형 파일에서 한다. 정규식·유효성 검사·정규화는 함께 유지한다. 새로운 유형을 도입할 때만 `pipeline.py`의 실행 목록과 결과 타입·평가 유형을 함께 갱신한다.
- 토큰 규칙은 `sentiment/tokenization.py`에서 수정한다. 사전 표기와 입력 문장이 같은 토큰화 함수를 사용한다. 활용 확장·긴 표현 우선순위는 `lexicon.py`, 부정 범위·강조 계산은 `modifiers.py`에서 수정한다.
- 평가 데이터 위치는 `evaluation/datasets.py`, 공통 지표 공식은 `metrics.py`, 영역별 정답 비교와 오류 보고는 각 평가기에서 수정한다.
- 결과 저장 정책은 `reporting/artifacts.py`, 비교표 형식은 `comparison.py`, 그래프는 `charts.py`에서 수정한다. 분석·평가 함수는 파일을 쓰지 않고, CLI가 출력 계층을 호출한다.
- 외부 호출부는 기존처럼 `from sentiment_engine.extraction import extract_information`, `from sentiment_engine.sentiment import analyze_sentiment`, `from sentiment_engine.evaluation import evaluate_extraction`을 사용한다. 각 패키지의 `__init__.py`가 공개 API를 명시한다.

## 설치 방법

Python 3.10 이상이 필요하다. 저장소 루트에서 가상환경을 만들고 설치한다. 검증 환경은 Python 3.12다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows에서는 `python -m venv .venv` 실행 후 `.venv\Scripts\activate`로 활성화한다. `requirements.txt`는 `pyproject.toml`의 `dev` 의존성을 포함해 현재 소스를 editable 방식으로 설치한다. 실행만 필요하면 `pip install .`로 일반 설치할 수 있으며, 사전과 평가 데이터도 함께 설치된다.

## CI

GitHub Actions는 모든 push와 pull request에서 Python 3.10·3.12 환경을 각각 준비한다. `pip install ".[dev]"`로 패키지와 데이터를 일반 설치한 뒤 `python -m pytest -q`를 실행하므로, 설치 파일의 데이터 누락도 검증한다. 상태는 문서 상단의 CI 배지와 `.github/workflows/ci.yml`에서 확인할 수 있다.

## 실행 방법

```bash
python -m sentiment_engine --text "문의: test@example.com, 결제 금액은 50,000원입니다. 정말 좋지 않아요."
python -m sentiment_engine --evaluate extraction
python -m sentiment_engine --evaluate sentiment
python -m sentiment_engine --evaluate all
python -m pytest -q
```

저장소에서 기존 `python main.py ...` 명령도 사용할 수 있다. 테스트를 나눠 실행하려면 `python -m pytest tests/unit -q` 또는 `python -m pytest tests/integration -q`를 사용한다.

CLI의 표준 출력(stdout)은 JSON이다. 비교표와 저장 경로는 표준 오류(stderr)에 표시하므로 JSON을 다른 프로그램으로 전달할 수 있다. 위 분석 예제는 이메일 `test@example.com`, 금액 `{"amount": 50000, "currency": "KRW"}`, 감성 `{"score": -3.0, "label": "negative"}`를 반환한다. 전체 응답에는 원문, 추출 위치, 토큰과 단어별 계산 내역도 포함한다. 빈 문장은 오류로 처리한다.

### 결과 파일과 성능 비교 보고서

기본 실행은 현재 작업 디렉터리의 `artifacts/` 아래에 결과를 자동 저장한다. 실행마다 UTC 시각과 고유 접미사가 붙은 새 디렉터리를 만들므로 이전 결과를 덮어쓰지 않는다. 실행이 끝나면 터미널에 실제 저장 경로와 파일 목록이 표시된다.

```text
artifacts/
├── analysis-<실행 ID>/
│   └── result.json         # 원문·추출 결과·진단·감성 분석
└── evaluation-<실행 ID>/
    ├── result.json         # 지표·혼동행렬·오류 사례
    ├── comparison.csv      # 스프레드시트용 비교표
    └── comparison.png      # 공유용 막대그래프
```

`--evaluate sentiment`와 `--evaluate all`은 Accuracy·Macro F1 비교표와 그래프를 함께 생성한다. `--evaluate extraction`은 추출 평가 JSON을 저장한다. 비교표와 그래프는 실행 시 계산한 평가 결과를 사용하며, 사용 문장 수와 합성 데이터라는 점을 표시한다. ON은 강조·부정을 모두 적용하고 OFF는 둘 다 끈다. 표의 값과 증감은 0–1 척도이며 Accuracy `+0.18`은 `+18%p`다.

```bash
# 터미널 출력만 사용 (파일 생성 없음)
python -m sentiment_engine --text "정말 좋지 않아요" --no-save
python -m sentiment_engine --evaluate sentiment --no-save

# 저장할 상위 디렉터리 지정
python -m sentiment_engine --evaluate all --output-dir artifacts/reports
```

`--no-save`와 `--output-dir`는 함께 사용할 수 없다. 저장에 실패하면 JSON은 터미널에 출력하고 오류 메시지와 종료 코드 1을 반환한다. 보고서 일부가 생성된 후 실패하면 해당 파일은 남을 수 있다. 생성 결과는 `.gitignore`의 `artifacts/` 규칙으로 커밋에서 제외된다. 별도 저장 경로를 선택하면 그 경로의 Git 포함 여부는 직접 관리한다.

## 정보 추출 규칙

각 유형의 함수는 **regex 후보 탐색 → 유효성 검사 → 정규화 → 결과 반환** 순서다. 정규식 바로 위의 주석에서 매칭 범위를 설명한다.

| 유형 | 지원 변형 예 | 검사와 정규화 |
| --- | --- | --- |
| Email | `user@domain.com`, `User.Name@sub.domain.co.kr`, `user+tag@example.org` | 연속된 점·잘못된 도메인 거부, 도메인만 소문자화 |
| Phone | `010-1234-5678`, `02 123 4567`, `03112345678` | 지원 지역번호·자릿수·구분자 일관성 검사, 하이픈 형식으로 통일 |
| Date | `2024년 1월 15일`, `2024/01/15`, `2024-01-15` | `datetime.date`로 윤년·월·일 검사, `2024-01-15`로 통일 |
| Money | `10,000원`, `1억 2천만원`, `$100` | 쉼표와 단위 순서 검사, 정수 `amount`와 `KRW / USD` 반환 |
| URL | HTTP(S) 기본 주소, 경로 포함 주소, query·fragment 포함 주소 | 호스트 존재·포트 검사, scheme·호스트 소문자화, 끝 문장부호·닫는 괄호 정리 |

금액 단위는 `억 / 천만 / 만 / 천`이며 `1억 2천만원`은 `120000000 KRW`다. 달러 소수 금액은 지원하지 않는다. URL 경로·쿼리·fragment는 보존하며 실제 접속 여부는 확인하지 않는다.

결과의 `start`는 시작 위치, `end`는 끝 다음 위치다(Python 문자열 인덱스). 잘못된 후보는 추출 결과에서 제외하고 `diagnostics`에 거부 이유를 남긴다. 정규식에 아예 잡히지 않는 표현에는 진단도 없다.

## 감성 분석 규칙

`sentiment/analyzer.py`가 다음 흐름을 조율한다. 토큰화는 `tokenization.py`, 사전과 표현 매칭은 `lexicon.py`, 강조·부정 계산은 `modifiers.py`가 담당한다.

```text
문장 → 어절·문장부호 토큰 → 사전 표현 매칭 → 기본 점수
     → 강조 배율 → 부정 횟수에 따른 반전 → 합산 → label
```

1. 한글·영문·숫자 어절과 문장부호·줄바꿈을 regex로 분리한다. 형태소 분석기는 사용하지 않는다.
2. 사전의 `term`, `variants`를 비교하고, 같은 위치에서는 긴 표현부터 매칭한다. 예를 들어 `문제가 해결되었다`를 잡으면 `문제`를 중복 가산하지 않는다.
3. 흔한 `-고 / -지 / -지만` 등의 어미, 일부 `하다` 활용, 명사 뒤 조사만 추가로 지원한다. 완전한 한국어 활용 분석은 아니다.
4. 감성 표현 바로 앞의 `정말 / 매우 / 아주 / 너무`는 ×1.5, `굉장히`는 ×1.7이다. 연속된 강조어는 배율을 곱한다.
5. 바로 앞의 `안 / 못`, 바로 뒤의 등록된 `않다 / 없다 / 아니다 / 못하다` 표기를 부정으로 센다. 문장부호나 줄바꿈을 건너가지 않는다.
6. 대표 이중부정 `좋지 않은 것은 아니다`는 `않은 + 것은 아니다`를 인식해 두 번 반전한다. 임의의 이중부정을 모두 처리하지는 않는다.
7. 단어별 점수는 `기본 점수 × 강조 배율 × (-1)^부정 횟수`다. 합계가 양수면 positive, 음수면 negative, 0이면 neutral이다.

| 문장 | 계산 | 결과 |
| --- | --- | --- |
| `정말 좋지 않아요` | +2 × 1.5 × -1 | -3, negative |
| `나쁘지 않다` | -2 × -1 | +2, positive |
| `좋지 않은 것은 아니다` | +2 × (-1)² | +2, positive |
| `오늘은 수요일이다` | 매칭 없음 | 0, neutral |

`analyze_sentiment(text, apply_modifiers=False)`는 강조와 부정을 모두 끄고 같은 사전의 기본 점수만 합산한다. `matches`에는 단어·기본 점수·배율·부정 횟수·최종 기여 점수가 담긴다.

## 데이터 구성

| 파일 | 구성 |
| --- | --- |
| `src/sentiment_engine/data/lexicons/sentiment_lexicon.json` | 기존 프로젝트 작성 사전 613개. `term`, `variants`, `score`, 선택적 `domain` |
| `src/sentiment_engine/data/lexicons/modifiers.json` | 앞/뒤 부정어 표기와 강조 배율 |
| `src/sentiment_engine/data/evaluation/extraction_cases.json` | 기존 65문장, 정답 개체 63개. 미지원 변형 6문장과 정답이 빈 7문장 포함 |
| `src/sentiment_engine/data/evaluation/sentiment_cases.json` | 기존 100문장, 긍정 50·부정 50. 단순 감성·강조·부정·이중부정·혼합 감성·난제 포함 |

도메인은 고객지원(`customer_support`)이며 `친절하다`, `불친절하다`, `정확하다` 등 91개 항목이다. 표기 변형을 별개 단어 수로 세지 않는다.

사전과 정답 예제는 기존 프로젝트에서 AI 도움을 받아 작성했으며 독립적인 사람의 검수를 거치지 않았다. 이번 리팩터링에서 정답은 변경하지 않았다. 각 추출 유형은 미지원 사례를 제외하고도 10문장 이상, 3가지 이상 변형을 포함한다. 사전과 규칙 개발에 이미 사용한 교육용 예제이므로 평가 수치를 독립적인 실서비스 성능으로 해석하면 안 된다. 감성의 난제는 불만 고객의 문맥으로 레이블링되었다.

## 평가 리포트

유형별 정밀도·재현율·F1, 감성 분석 성능 비교, 실패 사례와 평가 한계는 [정보 추출 및 감성 분석 평가 리포트](docs/evaluation-report.md)에 정리했다.

## 규칙 기반 NLP의 장단점과 통계 방식 비교

| 관점 | 이 프로젝트의 규칙 기반 방식 | TF-IDF 기반 접근 |
| --- | --- | --- |
| 표현 | 사람이 정한 패턴과 감성 점수 | 문서 내 빈도와 문서 집합 내 희소성으로 단어 가중치 계산 |
| 분류 | 명시적인 점수 합산·부정 규칙 | TF-IDF 벡터와 별도의 분류기 등을 조합 |
| 데이터 | 학습 없이 사전·규칙으로 실행 | IDF를 계산할 문서 집합, 지도 분류라면 레이블 데이터 필요 |
| 장점 | 판단 근거가 명확하고 형식이 정해진 정보에 효과적 | 문서 집합의 다양한 단어 분포를 활용 가능 |
| 단점 | 새 표현·오타·문맥마다 규칙 관리 필요 | 단순 단어 벡터는 어순·부정·반어를 충분히 표현하지 못함 |

TF-IDF 자체는 감성 분류기가 아니다. 이 저장소에는 TF-IDF나 학습 모델을 구현하지 않았다.

## 한계 및 개선 방향

regex 토큰화는 형태소 분석보다 활용형·붙여쓰기 처리에 약하고, 가까운 수식어 규칙은 복잡한 부정 범위를 놓친다. 반어, aspect-based sentiment, 담화 문맥 처리는 구현하지 않았다. 개선한다면 오류가 반복되는 표기를 사전에 추가하고, 별도의 중립·미등록 문장으로 평가한 뒤 필요한 범위만 형태소 분석이나 통계 분류기와 비교할 수 있다.

이번 제출에서는 외부 벤치마크, M/M2 개발 실험, exposure/workset, profiling, release 파이프라인, 컴파일 사전과 모델·환경 해시 검증, 과거 실험 문서·테스트를 제거했다. 핵심 미션 로직과 데이터, 재계산 가능한 평가만 남겼다.

리팩터링 이전 엔진의 분석 방식과 외부 평가 기록은 [이전 엔진 분석 및 평가 보고서](docs/archive/legacy-engine-report.md)에 보존했다. 해당 보고서의 구현 설명과 수치는 이전 버전을 기준으로 한다.
