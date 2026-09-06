# 정보 추출·감성 분석 엔진

## 프로젝트 소개

한국어 고객 문의와 같은 비정형 문자열에서 이메일, 전화번호, 날짜, 금액, URL을 추출하고 문장 전체의 감성을 규칙으로 판정하는 Python 프로젝트다. 추출기는 정규표현식으로 후보를 찾은 뒤 의미 검증과 정규화를 수행한다. 감성 분석기는 프로젝트 사전의 점수를 합산하고 부정어와 강조어를 제한된 범위에서 적용한다.

핵심 질문은 두 가지다. 명시적인 규칙으로 어떤 입력을 높은 정밀도로 처리할 수 있는가, 그리고 표기 변형·활용·문맥이 늘어날 때 재현율과 유지보수 비용이 어떻게 변하는가. 고정 합성 데이터 평가는 이 질문을 관찰하기 위한 장치이며 실제 고객 분포의 성능을 대표하지 않는다.

지원 결과는 원문 범위 `start`(포함)와 `end`(미포함), 원문 `raw`, 정규화 값과 계산 근거를 함께 제공한다. 공개 API는 `extract_information`, `analyze_sentiment`, 두 결과를 합치는 `analyze`다.

재설계 이전 baseline의 외부 쇼핑 후기 2,000건 최종 정확도는 **36.20%**였다.
현재 감성 엔진은 KOMORAN·감사된 사전·국소 문법으로 재구성했다. 동결 M2-L의 독립 final 10,000건 정확도는 **60.62%**로, 목표 70%에 미달했다. [M2 최종 결과](docs/evaluation/engine-m2-final.md)에 기준 M 비교와 CI를 기록했다.
M2의 reserve 기반 공개 development 10,000건 정확도는 **60.61%**로, 목표 67%에는 미달한다.
사전 확장 과정과 남은 오류는 [M2 개발 기록](docs/evaluation/engine-m2-development.md)에 정리했다.
현재 상태와 정리 내역은 [프로젝트 진단](docs/project-audit.md), 측정 근거는
[외부 평가 결과](docs/evaluation/sentiment-results.md)에 정리했다.

## 핵심 특징

- 5종 정보 추출과 정규화, 원문 범위·오류 진단 제공
- KOMORAN 형태소·품사로 활용형을 매칭하고 원문 공백·이모지 위치를 복원
- 사전 출처·검수·충돌을 기록하고 국소 부정·강조의 연결 근거를 추적

## 아키텍처

```text
입력 문자열
├── extraction.py: 정규식 후보 → 검증 → 정규화
├── korean.py → sentiment.py → sentiment_rules.py: 형태소 → 사전 사건 → 문법 연결 → 합산
└── __init__.py: 두 결과를 AnalysisResult로 통합
                    ↓
             cli.py / evaluation.py
```

| 경로 | 책임 |
|---|---|
| `main.py` | CLI 진입점 |
| `src/sentiment_engine/__init__.py` | `analyze`, `analyze_sentiment`, `extract_information` 공개 |
| `src/sentiment_engine/models.py` | 필드 재할당을 막는 결과 데이터 클래스와 타입 계약(내부 목록은 변경 가능) |
| `src/sentiment_engine/extraction.py` | 5종 후보 패턴, 유효성 검증, 정규화, 진단 |
| `src/sentiment_engine/sentiment.py` | compiled 자원 해시 검증, 최장 형태소 key 일치, 공개 API |
| `src/sentiment_engine/sentiment_rules.py` | 국소 문법, 연산자 단일 소비, 기여도 합산 |
| `src/sentiment_engine/korean.py` | 단일 KOMORAN 어댑터, 원문 위치 복원, JVM·모델 검증 |
| `src/sentiment_engine/evaluation.py` | 고정 gold 로딩, 정확 일치 지표, 오류 목록 생성 |
| `src/sentiment_engine/cli.py` | 인자 검증과 text/JSON 직렬화 |
| `data/` | 감성어와 수정어 JSON 자원 |
| `tests/fixtures/` | 고정 평가 문장과 gold 레이블 |

추출 후보가 형식 검증에서 제외되면 `Diagnostic`에 원문 범위와 사유가 남는다. 정상적인 미매칭은 진단 오류로 만들지 않는다. 결과는 원문 위치 순서로 정렬되고 동일 유형·범위의 중복은 제거된다.

## 설치 및 실행 방법

Python 3.10 이상과 **JDK 17**이 필요하다. Python 3.10.20/3.12.3 및 Temurin 17.0.20.1에서 검증했다. JDK를 설치하고 `JAVA_HOME`을 설치 경로로 지정한다. 감성 JSON 자원 경로가 소스 저장소를 기준으로 계산되므로 현재 배포 형태는 저장소의 editable 설치를 전제로 한다. 독립 wheel 설치를 지원한다고 가정하지 않는다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --require-hashes -r requirements-runtime.lock
python -m pip install -r requirements.txt
```

`requirements.txt`의 `-e .[test]`가 현재 저장소를 editable 방식으로 설치한다. 감성 분석은 KoNLPy 0.6.0, 번들 KOMORAN, JPype1 1.6.0을 사용한다. 전체 검증에는 pytest 8.x, datasketch 1.6.5, SciPy 1.15.3을 사용한다. 기존 requirements-eval.lock은 과거 baseline 평가 환경 기록으로 보존하며 새 런타임과 혼합 설치하지 않는다. JVM이나 모델이 없으면 명시적 구성 오류를 반환한다. 분석과 평가는 다음처럼 실행한다.

```bash
python main.py --text "문의: support@company.co.kr, 전화 02-1234-5678, 일시 2024년 3월 15일, 참가비 50,000원. 정말 좋지 않아요."
python main.py --text "문의는 support@example.com으로 주세요." --format json
python main.py --evaluate extraction --format json
python main.py --evaluate sentiment --format json
python main.py --evaluate sentiment --sentiment-cases tests/fixtures/sentiment_validation_cases.json --format json
python main.py --evaluate all --format json
python main.py --evaluate all
python -m pytest
```

`--text`와 `--evaluate`는 동시에 사용할 수 없다. `--sentiment-cases`는 감성 평가용 JSON 경로를 지정하며 `--evaluate sentiment` 또는 `all`과 함께 사용한다. 데이터 크기·균형·기능 태그 검증은 기본 데이터와 동일하다. 기본 출력은 사람이 읽는 텍스트이며 `--format json`은 UTF-8 JSON을 출력한다. 정상 실행은 종료 코드 0, 인자·자원 구성 오류는 stderr 설명과 종료 코드 2를 반환한다. API는 비문자열에 `TypeError`, 빈 문자열·공백 입력에 `ValueError`를 발생시킨다.

Python API 예시는 다음과 같다.

```python
from sentiment_engine import analyze, analyze_sentiment, extract_information

result = analyze("배송이 정말 빠르다. 문의: help@example.com")
only_extractions = extract_information("2024년 3월 15일, 50,000원")
base_sentiment = analyze_sentiment("정말 좋다", apply_modifiers=False)
```

통합 CLI 예제의 JSON 결과에는 네 추출 항목과 감성 `score=-3.0`, `label="negative"`가 나온다. `정말`이 `좋지`의 2점에 1.5배를 적용하고 `않아요`가 부호를 한 번 반전한 결과다.

## 데이터 구성과 감성 사전 출처

원본은 613개 항목이며 감사·충돌 제외·활용형 병합 후 compiled 대표 어휘는 **565개**다.
그중 긍정 207개·부정 358개, 직접 구축한 `customer_support` 어휘는 **73개**다.
점수는 ±1(약함), ±2(명확함), ±3(매우 강함)의 경험적 설정이다. 통계 학습값이 아니다.
`lexicon_annotations.json`은 각 원본·variant의 의미·품사·원자성·유지/제외 이유와 AI 검수를,
`lexicon_provenance.json`은 구축 정책과 추가·제외 이력을 기록한다. KNU는 이용·배포
조건이 확인되지 않아 도입하지 않았다. 서로 다른 동의어는 유지하며 활용형은 중복 집계하지 않는다.

모든 사전 항목의 `source`는 `project`다. 외부 감성 사전에서 가져오거나 변형했다는 기록이 없으므로 외부 출처나 라이선스를 주장하지 않는다. 현재 저장소에도 프로젝트 라이선스 선언이 없으므로 임의의 라이선스를 부여하지 않는다. 사전과 평가 fixture는 프로젝트에서 생성했으며 AI 도움을 받아 작성됐다. 독립적인 사람의 검수는 하지 않았다. M2는 공개 쇼핑 후기의 라벨 없는 mining과 development로 개선했으며, 동결 후보의 독립 final 평가는 완료했으며, 실제 운영 고객 분포 검증은 하지 않았다.

`modifiers.json`에는 부정 대표어 5개와 강조 대표어 5개 및 활용형이 있다. `sentiment_cases.json`은 긍정 50개와 부정 50개의 프로젝트 작성 합성 문장이다. 강조 15개 이상, 단일 부정 15개 이상, 이중부정 10개 이상, 혼합 극성 10개 이상, 비꼼·문맥 도전 10개 이상을 고정해서 포함한다. `extraction_cases.json`도 프로젝트 작성 고정 gold이며 5개 유형의 지원 사례와 미지원 도전 사례를 함께 둔다. 이 데이터는 재현 가능한 기능 평가에는 적합하지만 자연 발화 빈도나 운영 분포를 표본화하지 않았다.

## 정규표현식 구조와 정규화 규칙

정규식은 넓은 후보를 찾고 Python 검증 코드가 달력, 도메인, 단위 순서 같은 의미를 판단한다. 주요 문법은 `(?P<name>...)` 이름 있는 캡처 그룹, `[...]` 문자 클래스, `+`, `*`, `?`, `{m,n}` 수량자, `(?:...)` 비캡처 그룹, 앞뒤 문맥을 소비하지 않는 `(?<!...)`·`(?!...)` lookaround다.

| 유형 | 구조와 지원 범위 | 검증·정규화와 경계 |
|---|---|---|
| 이메일 | `local`과 `domain` 이름 그룹을 `@`로 연결한다. 로컬 문자 클래스는 영문·숫자와 일반 atom 기호를 `+`로 받고, 도메인은 점으로 반복되는 영문·숫자·하이픈 레이블이다. 좌우 lookaround는 더 큰 이메일형 토큰의 중간 일치를 막는다. | 로컬의 처음/끝 점과 연속 점, 빈·하이픈 경계 레이블, 2~63자 영문 최종 도메인을 검사한다. 로컬은 보존하고 도메인만 소문자로 만든다. 완전한 RFC 5322 구현은 아니다. |
| 전화 | `area`, `exchange`, `subscriber` 이름 그룹은 `\d{...}` 수량자를 쓰고 두 separator 그룹은 `[- ]?`로 하이픈·공백·무구분을 받는다. 양쪽 digit lookaround는 긴 숫자의 부분 일치를 막는다. | 국내 지역/휴대전화 접두어와 동일한 구분자, 교환국 길이를 검사하고 `지역-교환국-가입자`로 만든다. 국제 국가번호와 한글 숫자는 지원하지 않는다. |
| 날짜 | 세 패턴이 `year`, `month`, `day` 그룹으로 `YYYY년 M월 D일`, `YYYY/M/D`, `YYYY-M-D`를 받는다. `\s*`, `{4}`, `{1,2}`가 공백과 자리 수를 제한하며 digit lookaround가 숫자 일부 일치를 막는다. | `datetime.date`로 윤년과 실제 달력 날짜를 검증하고 `YYYY-MM-DD`로 만든다. 점 구분 형식은 지원하지 않는다. |
| 금액 | USD는 문자 경계 lookaround 사이에서 `$`와 `number`를 캡처한다. KRW는 `body` 그룹 안에서 숫자·쉼표 문자 클래스와 `억|천만|만|천` 비캡처 선택을 `*`로 반복하고 `원`을 요구한다. 내부 토큰 패턴은 `number`, 선택적 `unit` 그룹을 제공한다. | 정수 또는 올바른 3자리 쉼표를 검증한다. KRW 단위는 큰 단위에서 작은 단위 순서로 합산해 `{amount, currency}`로 만든다. 소수 USD, `USD 100`, 한글 수사는 지원하지 않는다. |
| URL | `https?://\S+`에서 `s?`는 선택적 HTTPS의 `s`, `\S+`는 공백 전까지의 후보다. 대소문자를 무시한다. | 끝 문장부호와 짝이 남는 닫는 괄호를 제거하고 `urlsplit`으로 host·port를 검증한다. scheme과 host를 소문자로 만들고 path/query/fragment는 보존한다. `www.`만 있는 scheme 없는 URL은 지원하지 않는다. |

금액이나 날짜처럼 정규식만으로 의미를 모두 표현하면 패턴이 읽기 어려워진다. 현재 구조는 후보 탐색과 의미 검증을 나눠 잘못된 달력 날짜, 잘못된 쉼표, 단위 역순을 구체적인 진단 사유로 남긴다.

## 감성 점수·부정어·강조어·이중부정

공개 `tokens`는 기존 한글·영문·숫자 및 `.!?,;:` 정규식 표시를 유지한다. 내부에서는
KOMORAN 형태소·품사를 사용한다. Java의 공백 축약·trim에 대한 경계 대응표와
UTF-16 변환으로 원문 위치를 복원하고, 실제 surrogate 값이 일치하는 SW 쌍만
이모지로 복원한다. TAB은 원문 경계 추적에 남긴다.

사전은 `(morph, POS)` 열로 컴파일한다. 활용 어미는 어휘 말단에서만 분리하고,
파생 접사와 관용구 내부 구성은 유지한다. 같은 시작점에서는 긴 key, 명시 우선순위,
canonical ID 순으로 결정한다. 명사 복합어의 일부나 `피해`와 `피하다`를 혼동하지
않도록 품사·어절 경계를 검사한다. 모델의 문맥별 품사 오분석까지 해결하는 것은 아니다.

```text
contribution = base_score × min(연결된 강조 배수의 곱, 2.0) × (-1)^(연결된 부정 수)
score = round(기여도 합, 6)
```

| 지원 문법 | 예와 연결 |
|---|---|
| 선행 안/못 | `안 매우 친절하다`에서 같은 술어에 연결 |
| -지 + 부정 보조용언 | `친절하지 않았다`, `좋지 못하다` |
| 감성 명사 + 없다/아니다 | `불만이 없다`; `불만을 말할 시간이 없다`에는 연결하지 않음 |
| 명사화 이중부정 | `친절하지 않은 것은 아니다`; 문장 경계를 건너지 않음 |
| 명사 + 부정 + 경동사 | `만족 안 해요`의 국소 구성 |
| 연속 강조 부사 | `정말 아주 친절하다`의 배수는 2.0으로 제한 |

어절 거리 상한 2는 이미 문법적으로 연결된 수정어의 안전 상한이다. 가까운 표현을
임의로 선택하지 않는다. 원자적 어휘의 내부 연산자는 소비된 것으로 추적하며
외부 부정만 추가한다. `apply_modifiers=False`는 동일한 사건의 부정·강조 적용만 끈다.
문장 예외였던 `문제가 해결되다` 같은 구성은 사전에서 제외하고 각 어휘를 합산한다.

총점의 부호로 positive/negative/neutral을 판정한다. 양수와 음수 기여가 모두 있으면
`mixed=true`다. 마지막 절을 우선하지 않으며 상태 변화·인용·반어·의향은 일반적으로
해석하지 않는다. 지원 문법과 테스트 변경 근거는 [개발 기록](docs/evaluation/engine-development.md)에 있다.

## 재설계 이전 baseline의 평가 방법과 결과

2026-09-05에 Python 3.12.3 가상환경에서 다음 명령으로 측정했다.

```bash
python main.py --evaluate extraction --format json
python main.py --evaluate sentiment --format json
python main.py --evaluate sentiment --sentiment-cases tests/fixtures/sentiment_validation_cases.json --format json
```

추출 데이터는 총 65문장이고, 각 유형의 지원 정답이 등장하는 문장 10개 이상과 표기 변형 3종 이상을 포함한다. 미지원 도전 6문장을 제외한 지원·음성 사례 59문장에서는 오류가 없었다.

추출 평가는 `(case ID, type, start, end, normalized)`의 완전 일치를 TP로 센다. 같은 원문 범위라도 정규화가 다르면 FP와 FN으로 각각 집계하고 별도 normalization mismatch도 기록한다. `Precision = TP / (TP + FP)`는 추출 결과 중 맞는 비율이고, `Recall = TP / (TP + FN)`은 정답 중 찾아낸 비율이다. `F1 = 2PR / (P + R)`은 둘의 조화 평균이다. 분모가 0이면 해당 지표를 0.0으로 기록한다. 예를 들어 neutral 정답이 없는 이번 감성 평가의 neutral Recall과 F1은 0.0이다.

| 유형 | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| email | 13 | 0 | 0 | 1.000000 | 1.000000 | 1.000000 |
| phone | 11 | 0 | 2 | 1.000000 | 0.846154 | 0.916667 |
| date | 11 | 0 | 1 | 1.000000 | 0.916667 | 0.956522 |
| money | 11 | 0 | 2 | 1.000000 | 0.846154 | 0.916667 |
| url | 11 | 0 | 1 | 1.000000 | 0.916667 | 0.956522 |
| micro | 57 | 0 | 6 | 1.000000 | 0.904762 | 0.950000 |

감성 평가는 기존 100문항과 추가 100문항을 따로 보고한다. 각각 긍정 50개·부정 50개라서 한 클래스만 찍는 기준선은 **정확도 50%**다. 중립 예측도 오답으로 포함한다. Macro F1은 gold support가 있는 positive/negative F1의 평균이며, 별도의 중립 클래스 F1은 평균에서 제외한다. 따라서 중립으로 회피한 경우가 많으면 Macro F1이 Accuracy보다 높을 수 있으므로 두 수치와 중립 예측 수를 함께 읽어야 한다.

| 데이터 | 수정어 | Accuracy | Macro F1 | Positive F1 | Negative F1 | 중립 예측 | 오분류 |
|---|---|---:|---:|---:|---:|---:|---:|
| 기존 100문항 | 끔 | 0.700000 | 0.721683 | 0.776699 | 0.666667 | 7 | 30 |
| 기존 100문항 | 켬 | 0.920000 | 0.951571 | 0.990099 | 0.913043 | 7 | 8 |
| 추가 100문항 | 끔 | 0.700000 | 0.733004 | 0.729167 | 0.736842 | 9 | 30 |
| 추가 100문항 | 켬 | 0.900000 | 0.942434 | 0.937500 | 0.947368 | 9 | 10 |

기존 구현(`4a6f8d9`)을 같은 기존 100문항에서 재현한 결과는 수정어 끔 Accuracy `0.43` / Macro F1 `0.588357`, 켬 Accuracy `0.44` / Macro F1 `0.602477`이었다. 이전 baseline 개선 당시 수정어 켬 정확도는 **44% → 92%, +48%p**이며 중립 예측은 **54 → 7건**으로 줄었다. 당시 낮은 성능의 큰 원인은 활용형 미인식과 부정어 연결 오류였다. 해당 baseline에서 수정어 자체의 정확도 효과는 기존 데이터에서 `70% → 92% (+22%p)`, 추가 데이터에서 `70% → 90% (+20%p)`다.

수정어 적용 후 기존 데이터의 혼동행렬은 positive 정답 50개 중 positive 50, negative 0, neutral 0이며 negative 정답 50개 중 positive 1, negative 42, neutral 7이다. 추가 데이터는 positive 정답에서 positive 45, negative 0, neutral 5, negative 정답에서 positive 1, negative 45, neutral 4다. CLI JSON에는 `majority_baseline_accuracy`, `neutral_predictions`, 클래스별 P/R/F1, 혼동행렬, 원문·점수 근거를 포함한 전체 오류 목록이 나온다.

| 기능 | 기존 건수 | 기존 수정어 끔 → 켬 Accuracy | 추가 건수 | 추가 수정어 끔 → 켬 Accuracy |
|---|---:|---:|---:|---:|
| 일반 표현 | 30 | 1.00 → 1.00 | 30 | 1.00 → 1.00 |
| 강조 | 20 | 1.00 → 1.00 | 20 | 1.00 → 1.00 |
| 단일부정 | 20 | 0.00 → 1.00 | 20 | 0.00 → 1.00 |
| 이중부정 | 10 | 1.00 → 1.00 | 10 | 1.00 → 1.00 |
| 혼합 극성 | 10 | 0.90 → 1.00 | 10 | 1.00 → 1.00 |
| 반어·문맥 도전 | 10 | 0.10 → 0.20 | 10 | 0.00 → 0.00 |

강조는 점수 크기를 바꾸므로 부호가 이미 맞으면 정확도가 변하지 않는다. 이중부정의 수정어 끔 정확도가 높은 것은 원래 사전 극성과 gold가 같은 문장들이기 때문이다. 따라서 이중부정 구현은 레이블 외에 `negation_count=2`와 기여도를 단위 테스트로 검증한다.

추가 데이터 `sentiment_validation_cases.json`은 구현 전에 문장과 레이블을 고정한 AI 보조 합성 자료다. 기존 문장을 복사하지 않고 다른 어휘·높임말·과거형을 포함하지만, 같은 작성 주체와 문법 유형을 공유하므로 독립적인 블라인드 평가나 실제 고객 분포 검증으로 보지 않는다. 구 구현에서는 추가 데이터 정확도가 7%였다. 두 데이터 모두 이번 작업 중 문장·레이블을 바꾸지 않았다. 당시 합격선은 두 데이터 각각 Accuracy와 Macro F1 0.80 이상이었다. 현재 재설계는 명시적 형태소·문법 계약과 개발 비교로 검증하며 이 과거 지표를 새 엔진 결과로 사용하지 않는다.

## 재설계 이전 baseline의 실패 사례

### 정보 추출 오류

새 평가의 여섯 오류는 모두 gold에는 있지만 현재 지원 문법 밖이라 놓친 FN이다. FP와 정규화 실패는 0건이었다.

| ID·분류 | 입력 | Gold | 예측 | 원인 | 개선과 trade-off |
|---|---|---|---|---|---|
| `phone-011` FN | `+82-10-1234-5678` | `010-1234-5678` | 없음 | 국내 접두어만 허용 | `+82` 변환 분기를 추가하면 국제 표기 Recall은 늘지만 국가번호·선행 0 규칙과 오인식 검증이 늘어난다. |
| `phone-012` FN | `공일공-일이삼사-오육칠팔` | `010-1234-5678` | 없음 | 숫자 문자 클래스가 `\d`뿐임 | 한글 숫자 전처리는 Recall을 높이지만 일반 단어 속 음절을 숫자로 바꾸는 FP 위험과 유지 규칙이 생긴다. |
| `date-011` FN | `2024.01.15` | `2024-01-15` | 없음 | 점 구분 패턴 없음 | 점 구분 패턴을 추가하면 Recall이 늘지만 문장부호·버전 번호와 충돌할 수 있어 경계 검증이 필요하다. |
| `money-011` FN | `백만원` | `1000000 KRW` | 없음 | 숫자 계수와 제한된 단위만 받음 | 한글 수사 파서를 추가하면 Recall은 늘지만 조합 문법과 단위 중의성 유지비가 커진다. |
| `money-012` FN | `USD 100` | `100 USD` | 없음 | `$` 접두 형식만 지원 | ISO 통화코드를 받으면 Recall이 늘지만 코드 경계와 다른 약어를 엄격히 검사하지 않으면 FP가 늘 수 있다. |
| `url-011` FN | `www.example.com/path` | `https://www.example.com/path` | 없음 | HTTP(S) scheme 필수 | scheme 없는 host 검출과 HTTPS 기본값을 추가하면 Recall은 늘지만 도메인처럼 보이는 일반 문자열 FP와 추론된 scheme 정책 부담이 생긴다. |

### 감성 오분류

수정어 적용 후 남은 기존 8건과 추가 10건을 모두 기록한다. 최소 10건의 실패 분석을 위해 모델에 오답을 강제하지 않고 두 평가의 실제 오류 18건을 사용한다.

| ID | 원문 | 정답 → 예측 (점수) | 원인 |
|---|---|---|---|
| `sentiment-091` | 참 잘도 처리했네요 | negative → neutral (0) | 표면 감성어 없이 처리 방식을 비꼬는 표현이다. |
| `sentiment-092` | 최고네요, 벌써 세 번째 고장이에요 | negative → positive (1) | 최고 +3과 고장 -2의 합이 +1이다. 고장 횟수가 앞 칭찬을 반어로 바꾸는 문맥을 모른다. |
| `sentiment-093` | 배송이 빛의 속도네요, 일주일밖에 안 걸렸어요 | negative → neutral (0) | 속도 비유와 일주일 대기의 모순을 해석하지 못한다. |
| `sentiment-094` | 웃음밖에 안 나와요 | negative → neutral (0) | 웃음이 만족인지 어이없음인지 문맥이 필요하다. |
| `sentiment-096` | 다시 사고 싶지는 않아요 | negative → neutral (0) | 재구매 의향을 감성으로 변환하는 의미 표현이 사전에 없다. |
| `sentiment-097` | 이 정도면 괜찮다고 해야 하나요 | negative → neutral (0) | 평가를 의심하는 수사의문과 미등록 괜찮다 활용이 겹친다. |
| `sentiment-098` | 기대를 안 했는데 역시나네요 | negative → neutral (0) | 기대와 실제 결과를 연결하는 문맥이 빠져 있다. |
| `sentiment-100` | 설명과 다른데 우연이겠죠 | negative → neutral (0) | 설명과 실제의 불일치를 완곡하게 비판하는 문장이다. |
| `validation-091` | 손에서 내려놓을 수가 없네요 | positive → neutral (0) | 내려놓지 못한다는 행동이 높은 만족을 암시하지만 명시적 감성어가 없다. |
| `validation-092` | 다음 달에도 여기로 오려고요 | positive → neutral (0) | 재방문 계획을 긍정 의향으로 해석하지 못한다. |
| `validation-093` | 가족에게 하나씩 더 사줬어요 | positive → neutral (0) | 추가 구매 행동에 담긴 만족을 추론하지 못한다. |
| `validation-094` | 기대 안 했는데 횡재했네요 | positive → neutral (0) | 미등록 횡재 표현과 기대 대비 결과를 해석해야 한다. |
| `validation-095` | 이런 곳이 동네에 생기다니요 | positive → neutral (0) | 지역에 생긴 사실을 반기는 화자의 태도가 함축되어 있다. |
| `validation-096` | 참 빠르네요, 한 달 만에 왔어요 | negative → positive (2) | 빠르다 +2를 그대로 반영하며 한 달이라는 반어 단서를 놓친다. |
| `validation-097` | 직접 고치는 편이 낫겠네요 | negative → neutral (0) | 직접 수리와 비교해 서비스를 비판하는 맥락을 놓친다. |
| `validation-098` | 다음에는 다른 곳으로 갈게요 | negative → neutral (0) | 이용 중단 의향이 불만을 암시하지만 명시적 감성어가 없다. |
| `validation-099` | 광고만 보고 산 제가 잘못이죠 | negative → neutral (0) | 광고와 구매 후 평가, 자기 비판에 담긴 불만을 연결하지 못한다. |
| `validation-100` | 버리는 데도 돈이 드네요 | negative → neutral (0) | 폐기 비용이라는 사실에서 불만을 추론하지 못한다. |

의향·관용구를 사전에 추가하면 일부 미인식을 줄일 수 있지만 같은 행동이 항상 같은 감성은 아니다. 반어 문구를 무조건 반전하면 문자 그대로의 칭찬을 오분류한다. 남은 문제는 별도 문맥 표본과 독립 검수가 필요하며, 이번 평가 문장 전체를 사전에 등록하는 방식으로 해결하지 않았다.

## 규칙 기반 시스템의 장점과 한계

규칙 기반 추출은 지원 문법에서 결과 이유를 패턴·검증·정규화 단계까지 추적할 수 있고, 이번 고정 데이터에서는 FP 없이 Precision 1.0을 보였다. 요구 형식이 안정적이고 오탐 비용이 큰 입력 폼, 로그, 정형 문서에 적합하다. 출력 형식과 금지 조건을 코드로 직접 통제할 수 있는 것도 장점이다.

반면 입력 형식 하나가 늘 때 패턴과 검증을 함께 확장해야 한다. 이번 평가의 국제 전화, 점 날짜, 한글 금액, scheme 없는 URL처럼 알려진 형식도 명시하지 않으면 놓친다. 높은 Precision은 합성 고정 데이터 범위의 관찰이며 새로운 운영 입력에서도 보장되지 않는다.

감성 규칙은 각 표현의 점수, 강조 배수, 부정 횟수와 원문 범위를 공개하므로 판정 근거를 검사하기 쉽다. 하지만 한국어 조사·어미와 불규칙 활용, 접속사로 바뀌는 담화 중심, 비꼼과 배경 문맥을 단순 사전 합산으로 포괄하기 어렵다. 수정 전 44%는 이론적 한계의 증거로 보기 어려웠다. 활용형·연결 구현을 개선한 뒤에도 남은 18개 오류가 반어·의향·문맥 해석의 한계를 더 분명하게 보여준다.

## 사전 변경과 재현

원본·annotations를 수정한 뒤 같은 런타임으로 compiled 사전을 다시 생성한다.
원본·검수·분석기/model 해시가 다르면 런타임은 오래된 compiled 파일을 거부한다.
프로세스 내 캐시와 JVM은 설정 변경 후 재사용하지 말고 새 프로세스로 검증한다.

```bash
python -m scripts.build_sentiment_lexicon --source data/sentiment_lexicon.json \
  --annotations data/lexicon_annotations.json --output data/sentiment_lexicon_compiled.json
python -m scripts.probe_komoran --output /tmp/komoran-probe.json
python -m pytest -q
python main.py --evaluate all
```

[개발 기록](docs/evaluation/engine-development.md)에 환경, 사전 감사, 기존 테스트에서
바뀐 의미 계약, 개발 비교와 한계를 기록한다. 여러 어절을 한 고유명사로 반환하면 토큰 전체 범위와 시작 어절 번호를 보존한다. 원문 경계가 성립하지 않거나 zero-length 형태소가 반환되면 명시적 분석 오류가 된다.

## 외부 감성 최종 benchmark

실제 외부 평가를 완료했다. 20만 건에서 개발 4,000개·선택 2,000개·최종 2,000개를
구성했고, 기존 엔진의 최종 Accuracy는 **36.20%**, Macro F1은 **0.48596**으로
목표에 미달했다. 미매칭 중립 출력이 주요 실패 경로다.
자세한 결과와 한계는 [평가 결과](docs/evaluation/sentiment-results.md),
한 번에 실행하는 방법은 [실행 가이드](docs/evaluation/benchmark-guide.md)를 참고한다.

외부 쇼핑 후기의 원문·별점·분할·중복 감사와 엔진 실행을 분리한 평가
인프라는 `scripts/benchmark/`와 `scripts/prepare_sentiment_benchmark.py`에
있다. worker에는 `{id, text}`만 전달하고, gold는 evaluator가 별도로
관리한다. 정확/근접 중복, 노출 문장, 2×4 혼동행렬, Wilson 구간, 그룹
paired bootstrap을 manifest와 함께 고정한다.

프로토콜은 [`docs/evaluation/sentiment-protocol.md`](docs/evaluation/sentiment-protocol.md),
결과 상태와 실행 명령은 [`docs/evaluation/sentiment-results.md`](docs/evaluation/sentiment-results.md)에
있다. 공개 점수는 실제 실행 산출물에 근거한다.
기존 `tests/fixtures/` 평가는 회귀용 합성 자료이며
외부 최종 benchmark와 섞지 않는다.

## 규칙 기반 방식과 머신러닝 방식 비교

| 관점 | 규칙 기반 | 머신러닝 기반 |
|---|---|---|
| 적합 조건 | 형식이 안정적이고 명시적 제약이 있으며 학습 데이터가 적을 때 | 표현 변이가 크고 충분한 대표 학습·검증 데이터가 있을 때 |
| 강점 | 결과 근거 추적, 즉시 수정, 출력 제약 통제, 작은 실행 환경 | 활용·유사 표현과 복잡한 문맥을 데이터에서 일반화할 가능성 |
| 약점 | 미등록 형식의 낮은 Recall, overlap·충돌, 수동 유지비, 비꼼·문맥 한계 | 데이터·라벨·학습 비용, 분포 변화, 확률적 오류, 설명과 재현 관리 부담 |
| 대표 적용 | 이메일·전화·날짜 정규화, 엄격한 업무 코드, 감사 가능한 소규모 정책 | 대규모 리뷰 감성, 다양한 자연어 분류, 문맥 의존 표현 |

두 방식은 배타적이지 않다. 엔티티의 엄격한 형식과 최종 출력 검증은 규칙으로 두고, 다양한 문장의 감성 후보나 활용 정규화는 학습 모델로 제안한 뒤 규칙으로 제한하는 혼합 구성이 가능하다. 다만 현재 프로젝트는 규칙 기반 동작과 그 한계를 측정하는 범위이며 ML 모델이나 비교 실험 결과를 포함하지 않는다.
