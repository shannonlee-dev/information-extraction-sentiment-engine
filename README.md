# 정보 추출·감성 분석 엔진

## 프로젝트 소개

한국어 비정형 문자열에서 이메일, 전화번호, 날짜, 금액, URL을 추출하고 문장 감성을
규칙으로 판정하는 Python 프로젝트다. 추출 결과에는 원문 범위와 정규화 값이,
감성 결과에는 점수와 계산 근거가 포함된다.

공개 API는 `extract_information`, `analyze_sentiment`, 두 결과를 합치는 `analyze`다.
현재 버전은 **0.1.0**이며 저장소 checkout에서의 editable 설치를 지원한다.

## 핵심 특징

- 5종 정보 추출, 형식 검증, 정규화 및 오류 진단
- KOMORAN 형태소·품사 기반의 한국어 활용형 매칭
- 감성 사전 점수와 제한된 부정·강조·이중부정 규칙
- 원문 위치, 사전 항목, 수정어 적용 내역을 포함한 설명 가능한 결과
- 고정 fixture와 외부 리뷰 benchmark를 분리한 평가 체계

## 아키텍처

```text
입력 문자열
├── extraction.py: 정규식 후보 → 의미 검증 → 정규화
├── korean.py: KOMORAN 분석 → 원문 위치 복원
├── sentiment.py → sentiment_rules.py: 사전 매칭 → 국소 문법 → 점수 합산
└── __init__.py: 추출과 감성을 AnalysisResult로 통합
                    ↓
             cli.py / evaluation.py
```

| 경로 | 책임 |
|---|---|
| `src/sentiment_engine/` | 공개 API, 추출기, 감성 분석기, CLI |
| `data/` | 원본·검수·compiled 감성 사전과 수정어 |
| `tests/` | 기능·회귀·평가 계약 테스트와 고정 fixture |
| `scripts/` | 사전 빌드, 환경 확인, 외부 benchmark 재현 도구 |
| `docs/evaluation/` | 평가 프로토콜, 결과 보고서, 기계 판독 기록 |

## 요구 환경과 설치

- Python 3.10 이상
- JDK 17과 올바른 `JAVA_HOME`
- Linux 기준 검증 환경: Python 3.10.20/3.12.3, Temurin 17.0.20.1

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-runtime.lock
python -m pip install -r requirements.txt
```

`requirements-runtime.lock`은 런타임 의존성을 해시로 고정한다.
`requirements.txt`는 현재 checkout과 테스트 의존성을 editable 방식으로 설치한다.
`requirements-eval.lock`과 KOMORAN probe 잠금 파일은 과거 평가 환경 재현을 위해 유지한다.

감성 자원 경로가 저장소 루트를 기준으로 계산되므로 독립 wheel 설치는 아직 지원하지 않는다.
JVM 또는 모델 구성이 잘못되면 자동 대체하지 않고 명시적인 구성 오류를 반환한다.

## 사용법

```bash
python main.py --text "문의: help@example.com, 결제 금액은 50,000원입니다. 정말 좋지 않아요."
python main.py --text "배송이 빨라서 만족합니다." --format json
python main.py --evaluate all
python main.py --evaluate all --format json
```

Python API:

```python
from sentiment_engine import analyze, analyze_sentiment, extract_information

result = analyze("배송이 빠르다. 문의: help@example.com")
extractions = extract_information("2024년 3월 15일, 50,000원")
sentiment = analyze_sentiment("정말 좋지 않다")
```

`--text`와 `--evaluate`는 함께 사용할 수 없다. 기본 출력은 사람이 읽는 텍스트이며
`--format json`은 UTF-8 JSON을 출력한다. 비문자열은 `TypeError`, 빈 문자열은
`ValueError`로 거부한다. CLI의 인자·자원 구성 오류는 종료 코드 2를 반환한다.

## 지원 범위

| 유형 | 지원 예 | 정규화 | 주요 제외 범위 |
|---|---|---|---|
| 이메일 | `user@example.com` | 도메인 소문자화 | 완전한 RFC 5322 |
| 전화 | `010-1234-5678`, `02 1234 5678` | 국내 하이픈 형식 | 국제번호, 한글 숫자 |
| 날짜 | `2024년 3월 15일`, `2024/03/15` | `YYYY-MM-DD` | 점 구분 날짜 |
| 금액 | `50,000원`, `$100` | 금액과 통화 코드 | 한글 수사, `USD 100` |
| URL | `https://example.com/path` | scheme·host 소문자화 | scheme 없는 URL |

정규식은 후보만 찾고 Python 코드가 달력 날짜, 도메인, 숫자 구분자, 화폐 단위 순서를
검증한다. 지원하지 않는 형식을 추측해 보정하지 않는다.

감성 분석은 `(형태소, 품사)`로 컴파일한 사전을 최장 일치시키고 다음 식으로 점수를 계산한다.

```text
contribution = base_score × min(강조 배수의 곱, 2.0) × (-1)^(부정 수)
score = round(기여도 합, 6)
```

점수의 부호가 각각 `positive`, `negative`, `neutral`을 결정한다. 양·음 기여가 함께
있으면 `mixed=true`다. 문장 경계를 넘는 수정어 연결, 반어, 인용, 의향과 일반적인
담화 문맥 해석은 지원하지 않는다.

## 감성 사전

원본 613개 항목을 감사하고 충돌과 중복 활용형을 정리해 대표 어휘 565개를 compiled
사전에 포함했다. 긍정 207개, 부정 358개이며 점수 ±1~±3은 경험적 강도이지 학습된
통계값이 아니다.

- `data/sentiment_lexicon.json`: 원본 사전
- `data/lexicon_annotations.json`: 품사·의미·채택/제외 근거
- `data/lexicon_provenance.json`: 구축 정책과 변경 이력
- `data/sentiment_lexicon_compiled.json`: 런타임용 결정적 산출물
- `data/modifiers.json`: 부정어와 강조어

사전과 평가 fixture는 프로젝트에서 AI 도움을 받아 작성했으며 독립적인 사람의 검수를
거치지 않았다. 상세 출처와 판단 근거는 provenance와 annotations에 기록돼 있다.

사전을 변경한 뒤에는 같은 잠금 환경에서 compiled 파일을 다시 생성한다.

```bash
python -m scripts.build_sentiment_lexicon \
  --source data/sentiment_lexicon.json \
  --annotations data/lexicon_annotations.json \
  --output data/sentiment_lexicon_compiled.json
python -m pytest -q
```

원본·검수 파일·분석기 모델의 해시가 다르면 런타임은 오래된 compiled 파일을 거부한다.

## 평가 결과

동결한 M2-L 후보를 2026-09-07 외부 쇼핑 후기 final 10,000건에서 한 번 평가했다.

| 지표 | 기준 M | M2-L |
|---|---:|---:|
| Accuracy | 48.24% | **60.62%** |
| Macro F1 | 0.589757 | **0.695179** |
| Positive recall | 68.35% | **77.95%** |
| Negative recall | 28.44% | **43.56%** |
| 분석 오류율 | 1.92% | 1.92% |

M2-L은 기준 M보다 정확도가 12.38%p 높았지만 목표 70%에는 미달했다. 별점은 감성의
잡음 있는 대리값이며 이 결과는 실제 고객 문의 분포의 성능을 보장하지 않는다.
고정 합성 fixture는 회귀 검사용이며 독립 외부 평가와 구분한다.

통계, 데이터 독립성, 한계는 [M2 최종 결과](docs/evaluation/engine-m2-final.md), 전체 자료의
역할은 [문서 안내](docs/README.md)에서 확인할 수 있다.

## 한계

- 명시하지 않은 추출 형식은 놓칠 수 있다.
- 사전 밖 표현, 비꼼, 상태 변화, 복합 문맥에는 취약하다.
- 분석기 실행에는 JVM이 필요하고 프로세스 메모리 비용이 발생한다.
- 외부 benchmark 결과를 운영 환경의 품질 보증으로 사용할 수 없다.
- 현재 저장소에는 별도 라이선스가 없다. 공개 열람이 재사용·배포 허가를 뜻하지 않는다.

## 문서

평가 보고서, 프로토콜, 개발 기록과 기계 판독 산출물은
[docs/README.md](docs/README.md)에 현재/과거 단계별로 정리했다.
