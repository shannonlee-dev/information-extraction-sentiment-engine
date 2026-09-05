# 외부 감성 최종평가셋 구축 Implementation Plan

> **For agentic workers:** 후속 실행 지시를 받은 뒤 `superpowers:executing-plans`로 작업별 구현·검증을 진행한다. 체크박스는 실제 결과를 확인한 뒤 표시한다. 현재 승인 범위는 조사와 계획 파일 작성이다.

**Goal:** 외부 쇼핑 후기의 원문과 원래 별점 레이블을 보존하고, 개발에 사용하지 않은 최종 분할에서 현재 또는 개선된 감성 엔진의 성능과 한계를 재현 가능하게 평가한다.

**Architecture:** 데이터 준비, 엔진 실행, 정답 대조를 분리한다. 엔진에는 `id/text`만 전달하고 레이블은 평가기가 관리한다. 기존 합성 fixture는 회귀용으로 유지하고 외부 benchmark에 클래스 균형·기능 태그 제약을 강제하지 않는다.

**Tech Stack:** Python 3.10 이상, 표준 라이브러리, pytest. 평가 환경에만 NumPy/datasketch를 설치한다. 실행 시 Python 3.10/현재 개발 Python에서 호환되는 실제 버전과 wheel 해시를 잠근다. 이번 조사에서 설치·후기 원본 다운로드·성능 실험은 하지 않았다.

**관련 문서:** `docs/private/mission.md`, `docs/private/rubric.md`, 선택적 후속 계획 `docs/superpowers/plans/2026-09-05-sentiment-engine-redesign-v2.md`.

## 1. 범위와 완료 기준

이 계획은 평가 인프라만으로 완료할 수 있다. KOMORAN/KNU 도입은 선행 조건이 아니다. 엔진 개선이 필요하면 별도 재설계 계획을 development에서 수행한 뒤 후보 동결 단계로 돌아온다. 종전 `2026-09-05-sentiment-generalization.md`는 보존하며 이 문서는 그 평가 절을 대체하는 새 제안이다.

| 대안 | 판단 |
|---|---|
| 합성 문장 추가·재분할 | 회귀용. 이미 노출된 문장으로 최종 성능을 판정하지 않음 |
| 외부 benchmark부터 구축하고 엔진 개선을 분리 | 채택. 평가 완료가 JVM·사전 교체에 묶이지 않음 |
| 형태소·사전·구문 엔진부터 전면 교체 | 외부 개발 오류와 환경 검증에 근거한 선택적 후속 작업 |

완료를 다음 세 가지로 구분한다.

1. **평가셋 준비 완료:** 출처·원문·분할·중복 감사·manifest·접근 규칙·지표 테스트가 갖춰짐.
2. **최종 평가 완료:** 동결 엔진을 최종 표본 전체에 실행하고 결과·불확실성을 공개함. 낮은 성능도 유효한 완료 결과다.
3. **성능 목표 달성:** Accuracy ≥ 0.80, binary Macro F1 ≥ 0.80, 양 클래스 Recall 각각 ≥ 0.75, 그룹 bootstrap Accuracy 95% 구간 하한 ≥ 0.75를 모두 충족함.

기준선 대비 개선은 별도 판정한다. paired Accuracy 차이 95% 구간 하한 > 0이면 개선 근거가 있다고 보고한다. baseline이 최종 후보이면 개선 비교는 해당 없음이다. 0.80은 미션 공식 통과선이 아니며 결과를 본 뒤 낮추지 않는다.

## 2. 조사 근거와 현재 상태

2026-09-05에 미션·루브릭·현재 소스와 아래 공식 자료를 확인했다. API/설명 확인은 실제 환경 실행 검증과 구별한다.

- 미션은 사전 200개 이상, 감성 평가 100문장 이상, Accuracy/F1, 수정어 전후 비교를 요구한다. KoNLPy는 허용 사항이다. 기존 5종 정규식 정보 추출을 유지한다.
- 네이버 쇼핑 원본 설명은 2020년 6~7월 수집, 200,000건, `별점<TAB>본문`, 3점 제외, 1·2점 부정/4·5점 긍정이다. 저자는 저장소를 Public Domain으로 표시한다. 실행 때 실제 commit SHA와 파일 바이트를 고정한다. [S1][S2]
- 평가 대상은 **공개 쇼핑 후기 말뭉치에서 미노출 후기의 별점 극성 일치도**다. 원본 자체가 양극성을 거의 균형화했다. 현재 고객 문의·현재 운영 분포·새 플랫폼으로 일반화했다고 주장하지 않는다.
- 같은 출처의 holdout도 개발 의사결정에서 격리하면 개발 과정에 대한 독립성을 가질 수 있다. 다른 시기·기관의 external validation과 구별한다. 공개 자료를 도운 AI가 사전학습에서 보지 않았다는 보장은 없다. [S3]
- LSH는 후보 검색이다. 실제 Jaccard 확인과 선택 표본의 정확 교차 검사를 추가한다. Wilson은 행 독립 근사, 그룹 bootstrap은 관측 가능한 문자열 군집만 반영한다. 상품/사용자 ID 없는 자료에서 상품·사용자 독립성을 보장할 수 없다. [S4][S5][S6]

현재 `evaluation.py`의 기본 감성 입력은 `tests/fixtures/sentiment_cases.json`이다. `load_sentiment_cases`의 균형/기능 태그 제약은 외부 benchmark에 재사용하지 않는다. `sentiment_validation_cases.json`도 개발·회귀 자료다. 두 파일을 다시 나눠 holdout으로 부르지 않는다.

현재 작업 트리에는 미커밋 소스·사전·테스트와 미추적 파일이 있다. HEAD만으로 기준선을 재현할 수 없다. `sentiment.py`는 저장소 루트의 `data/`를 읽으므로 스냅샷은 `src/`와 `data/`를 함께 보존한다. README의 92%/90% 등은 과거 합성 평가 기록이며 이번 조사에서 재실행한 값이 아니다.

## 3. 원본과 산출 파일

```text
artifacts/benchmark/v1/
  source.json                 # URL, commit SHA, SHA-256, 크기, 출처 조건
  raw/naver_shopping.txt       # 받은 바이트 그대로
  raw/source-readme.md         # 고정 원본 설명
  exclusions.jsonl             # 원본 행 ID, 제외 사유
  groups.jsonl                 # 대표/제거된 행 ID, 중복 키, 그룹 대응
  manifest.json                # 준비 코드·환경·프로토콜·분할 파일 해시
  development.inputs.jsonl     # {id, text}
  development.gold.jsonl       # {id, rating, label, group_id, source_line, text_sha256}
  selection.inputs.jsonl
  selection.gold.jsonl
  final.inputs.jsonl
  final.gold.jsonl
  baseline/                   # 상대 경로 보존 src/, data/, main.py, 설치 파일
  baseline.json                # 실행 환경, 자원 해시, 실제 import 경로
  candidates/                 # 후보별 불변 스냅샷/manifest
  runs/                       # ID별 예측, 집계, 접근·실행 이력
  release.json                 # 선택 후보·baseline·evaluator·프로토콜 해시
```

`text`는 TSV 본문 그대로다. 오타·띄어쓰기 수정, 문장 재작성, 문장 단위 분할, AI 재라벨링을 하지 않는다. JSON escape와 별점→극성 매핑은 저장 형식 변환이다. 엔진 전처리는 별도의 동결된 모델 동작이다. 최종셋은 **원문을 보존한 선택·정제 표본**이며 정제 전 raw 전체와 구별한다.

## 4. 데이터 준비 프로토콜 v1

### 4.1 파싱·정확 중복

1. 원본 접근 전에 이 절과 5~7절을 `docs/evaluation/sentiment-protocol.md`에 저장하고 해시한다. source commit SHA는 실행 때 확인한 실제 값만 쓴다. `master` URL만으로 manifest를 완료하지 않는다.
2. 원본 바이트를 저장·해시한 뒤 UTF-8 strict로 읽는다. 디코딩 실패는 준비 실패다. LF/CRLF 레코드 구분자만 제거하고 첫 TAB에서만 나눈다. 본문의 추가 TAB·공백을 보존한다.
3. ID=`원본 SHA-256:1-based 행 번호`. 1/2→negative, 4/5→positive. 3점은 `excluded_rating_3`, 잘못된 별점/TAB 부재는 `malformed_record`, 공백뿐인 본문은 `empty_text`로 제외하고 전부 기록한다. 길이·감성어·예측에 의한 제외는 없다.
4. 중복 키만 NFC 정규화 후 Unicode 공백 연속을 ASCII 공백 하나로 축약하고 양끝을 제거한다. 대소문자·구두점·숫자·부정어는 유지한다. 원문은 바꾸지 않는다.
5. 같은 키에 양극성 레이블이 공존하면 모든 행을 `conflicting_exact_label`로 제외한다. 4점/5점처럼 같은 극성 별점 차이는 충돌이 아니다.
6. 같은 키·극성은 가장 작은 원본 행 번호 하나를 대표로 남긴다. 제거 ID·별점을 대응표에 남긴다. 이후 추정 대상은 정확 중복 제거 후의 후기 분포다.

### 4.2 근접 중복·노출

- 키 길이 20 Unicode code points 미만은 정확 중복만 검사한다. 모두 20자 이상인 문장 사이 문자 5-gram **집합** Jaccard ≥ 0.85이면 연결한다. 의미 동등성을 뜻하지 않는다.
- 후보 탐색은 datasketch MinHash `num_perm=256`, `seed=20260905`, LSH `params=(32,8)`. shingle을 정렬해 UTF-8로 넣는다. 기본 hash 함수·실제 라이브러리 버전도 기록한다. 확정 비교는 `20*intersection >= 17*union`으로 한다.
- 연결의 connected component가 그룹이다. A-B, B-C가 연결되면 A-C가 임계값 미만이어도 같은 그룹이다. 그룹 ID는 정렬된 대표 원본 ID 목록의 SHA-256이다. 큰 그룹·체인 통계를 보고하며 크다는 이유로 삭제하지 않는다.
- **근접 그룹의 양극성 혼합은 허용하고 함께 배치한다.** 부정어 한 개 차이가 실제 극성을 바꿀 수 있다. 정확 중복의 레이블 충돌과 다르게 취급한다.
- `docs/evaluation/exposure-register.jsonl`에 기존 fixture, 계획/테스트 예문, 사용자가 보여준 원문, 공식 README의 쇼핑 미리보기 10문장과 출처를 등록한다. 도구 출력에서 열람한 원문도 포함한다. 이들과 정확/근접 중복인 그룹은 development로만 배치한다.
- LSH 후 제안된 development/selection/final과 exposure register 사이 **교차 분할 정확 검사**를 한다. shingle 개수 비율 `min/max < 0.85`이면 생략할 수 있다. 나머지는 실제 교집합/합집합을 검사한다. 누락 연결은 union 후 같은 분할 알고리즘을 처음부터 다시 적용한다. 새 교차 연결이 없을 때까지 반복하고 iteration별 기록을 남긴다. 원문 열람·모델 실행 전에 완료한다.
- exposure는 `exposure:<내용 해시>` ID를 가진 가상 노드다. 그 노드와 연결된 원본 그룹은 exposed로 표시하고 development로 이동한다. exposure 노드 자체를 평가 행으로 세지 않는다. 준비가 성공하면 그룹 ID를 각 inputs 대응 gold 행에 붙인다. 개발 중 새로 작성/열람한 예문도 후보 목록 동결 전에 exposure에 추가하여 자동 교차 검사한다. 새 중복은 연결 그룹 전체를 development로 이동하고 benchmark 버전을 올린다. 나머지 split 소속은 고정하고 빈자리를 새 표본으로 채우지 않는다. 개발/선택에 사용된 행을 final로 승격하지 않는다. 이동 후 표본 준비 게이트를 다시 확인하고 실제 감소 수를 보고한다. selection 점수 공개 후에는 후보에 새 예문/규칙을 추가할 수 없다. 이미 최종 점수를 본 뒤 발견한 충돌은 기존 결과의 한계로 남기고 독립성 주장을 정정한다.
- 이 검사는 선택된 집합 사이에서 정의한 문자열 누출을 검사한다. reserve 전체를 통한 잠재 유사성이나 의미 유사성 부재를 증명하지 않는다. v1에서 reserve 원문을 개발용으로 추가 열람하지 않는다.

### 4.3 결정적 그룹 분할

development 약 4,000건, selection 약 2,000건, final 약 2,000건을 목표로 한다. 그룹을 쪼개지 않으며 나머지는 reserve로 잠근다. 1:1을 강제하지 않고 정제 후 별점 1/2/4/5 비율을 가깝게 유지한다.

```text
seed=20260905; N=정확 중복 정제 후 전체 대표 행 수
N<8000이면 준비 실패: 임의의 합성 보충/표본 축소 금지
targets={development:4000, selection:2000, final:2000, reserve:N-8000}
target[split,rating]=targets[split]*전체 rating 비율
노출 그룹을 development에 먼저 배치하고 counts에 반영
나머지 그룹을 (-그룹 행 수, sha256(seed|group_id))로 정렬
그룹 rating 벡터 v마다 split별 비용 증가 계산:
 sum_r (((counts[s,r]+v[r]-target[s,r])^2
         -(counts[s,r]-target[s,r])^2)/max(target[s,r],1))
비용 증가가 가장 작은 split에 그룹 전체 배치
동률은 sha256(seed|group_id|split) 순서로 결정
파일 행 순서는 원본 행 번호의 숫자 오름차순
```

union이 바뀌면 같은 절차를 다시 적용한다. seed/알고리즘은 점수를 보기 전에 고정한다. 실제 행/그룹 수·별점/극성 분포·최대 그룹 크기를 보고한다. selection/final이 목표 ±10%를 벗어나거나 한 클래스가 40% 미만이면 준비 게이트에서 중단하고 집계만으로 새 준비 설계를 검토한다. seed를 바꾸어 원하는 표본을 고르지 않는다. 외부 자료에 합성 fixture 기능 태그 비율을 강제하지 않는다.

비용 비교는 정수 비율 또는 `fractions.Fraction`으로 계산해 부동소수 동률에 의존하지 않는다. hash 입력은 모호한 문자열 연결 대신 정렬된 JSON 배열을 UTF-8로 직렬화한다(`ensure_ascii=False`, `separators=(',',':')`). 데이터 JSONL은 키 정렬·UTF-8·LF로 고정한다. 준비 코드/프로토콜/lock 해시가 달라지면 같은 seed라도 새 준비 버전이다. 정확 감사가 시간·메모리 제한으로 끝나지 않으면 중단 기록을 남기고 완료했다고 표시하지 않는다.

## 5. 실행·접근·후보 계약

### 오류 및 격리

- 예측 worker는 `{id,text}`만 읽고 `{id,predicted,score,match_count,neutral_reason,error_type}`을 반환한다. gold/rating/label 입력 인자를 받지 않는다.
- 후보 스냅샷 절대 `src/`를 `PYTHONPATH`로 지정한 별도 프로세스에서 import한다. `__file__`이 스냅샷 안인지, 실제 사전 해시가 일치하는지 검사한다. user site·우연한 editable install 유입을 막는다.
- worker는 재사용한다. 모든 엔진에 초기화 timeout 120초, 행 timeout 10초를 동일 적용한다. 긴 문장을 잘라서 성공 처리하지 않는다.
- 행별 예외/timeout/worker 종료는 그 ID의 `analysis_error`. 다음 행을 위한 worker 재초기화는 허용하되 실패 행 재시도로 좋은 예측을 고르지 않는다. raw stack trace 대신 오류 유형만 기록한다.
- 알 수 없는 label, 비유한 score(NaN/Infinity), 잘못된 JSON 응답은 현재 요청 ID의 `invalid_prediction` 오류로 집계한다. evaluator의 gold와 응답 ID 대응이 깨지면 실행 무결성 오류로 종료한다. 정상 예측의 점수/neutral_reason은 엔진의 실제 matches를 근거로 기록한다.
- manifest/모듈 경로 불일치, worker 최초 초기화 실패는 **실험 준비 실패**다. 유효한 Accuracy=0 평가로 처리하지 않는다. 컨트롤러 중단은 불완전 실행이며 누락/중복 ID가 있으면 최종 보고를 거부한다.

### 선택과 최종 사용

1. baseline은 현재 작업 트리의 실행 파일 allowlist로 복제한다. `src/`, `data/`, `main.py`, 설치 명세를 상대 경로까지 보존한다. tracked diff와 미추적 실행 파일 목록·해시를 기록한다. `.env`, `.git`, 토큰, 가상환경은 복제하지 않는다.
2. development에서만 오류를 보고 규칙·사전을 수정한다. 사전과 테스트의 일반 어휘 중첩은 정상이다. 최종 문장에서 사전 항목을 추출하는 것은 금지한다.
3. selection 접근 전에 **최대 3개 후보**를 동결한다. baseline을 반드시 포함하고 나머지는 B 계획의 적격 후보로 한다. 후보가 하나면 selection을 사용하지 않는다.
4. selection은 후보당 수정어 켬을 한 번 평가하고 집계만 공개한다. 최고 binary Macro F1과 0.005 이내 후보 중 baseline 우선, 없으면 등록 순서 우선으로 선택한다. 결과 후 후보 추가·코드 변경은 금지한다.
5. 선택 후보·baseline·evaluator·protocol·split·노출 목록·환경·실행 제한·seed를 release manifest로 잠근다. final 전에 전부 검증한다.
6. final은 선택 후보 켬/끔 및 baseline 켬만 실행한다. 주 비교는 후보 켬 대 baseline 켬, 켬/끔은 미션 요구 보조 비교다. baseline이 선택되면 같은 실행을 재사용한다.
7. 처음에는 전체 지표·CI·오류 수·판정만 공개한다. 결과 확정 후 원문 오류를 열어 분석한다. 이후 수정한 모델은 같은 세트로 독립 재합격시키지 않는다.
8. 동일 동결물 재실행은 재현성 검사로 허용하고 실행 이력을 남긴다. selection을 보고 구현을 바꾸면 해당 selection의 자격을 폐기하고 final을 잠근 채 계획을 개정한다.

최종 읽기는 `--split final --release-manifest` 검증과 접근 로그로 보호한다. 같은 파일시스템의 모든 사용자를 막는 보안 경계는 아니다. 일반 pytest/CI는 작은 합성 데이터만 읽는다.

## 6. 지표와 신뢰구간

정답 행 `positive,negative`, 예측 열 `positive,negative,neutral,analysis_error`의 **2×4 혼동행렬 C**를 사용한다. neutral은 no_match(매칭 없음), cancellation(양·음 기여 합계 0), other_zero로 구분한다. baseline에서 구분할 증거가 부족하면 other_zero다.

```text
N=sum(C); TP_y=C[y,y]
FN_y=sum(C[y,:])-TP_y; FP_y=sum(C[:,y])-TP_y
P_y=TP_y/(TP_y+FP_y); R_y=TP_y/(TP_y+FN_y)
F1_y=2*TP_y/(2*TP_y+FP_y+FN_y)
Accuracy=(TP_positive+TP_negative)/N
Macro F1=(F1_positive+F1_negative)/2
```

0분모 클래스 지표는 0과 플래그로 반환한다. 빈 평가셋은 오류다. neutral/error를 N과 정답 클래스 FN에 포함한다. 출력 전용 클래스를 Macro F1 평균에 넣지 않는다. 판정은 반올림 전 값으로 하고 화면만 소수 6자리다.

비교 기준: 전부 positive, 전부 negative, 개발셋 다수 클래스 고정(동률 negative), 동결 현재 엔진. final의 최대 클래스 비율은 참고 상한이며 final 레이블로 선택한 기준선 모델로 부르지 않는다.

Wilson 95%는 z=1.959963984540054로 계산한다. 행 독립 근사인 보조 구간이다. [S5]

```python
from math import sqrt

def wilson(correct: int, total: int) -> tuple[float, float]:
    if total <= 0 or not 0 <= correct <= total:
        raise ValueError("invalid counts")
    z = 1.959963984540054
    p = correct / total
    den = 1 + z*z/total
    center = (p + z*z/(2*total)) / den
    half = z*sqrt(p*(1-p)/total + z*z/(4*total*total)) / den
    return max(0.0, center-half), min(1.0, center+half)
```

주 구간은 paired cluster percentile bootstrap 2,000회다. seed=20260906, NumPy `Generator(PCG64(seed))`, 정렬된 G개 그룹에서 매번 G개를 복원추출한다. 그룹의 모든 행을 중복 횟수만큼 합친다. 후보/기준선/수정어 비교는 같은 그룹 인덱스를 사용한다. Accuracy/Macro F1 및 Accuracy 차이의 2.5/97.5 percentile(`method='linear'`)을 기록한다. 개별 모델 CI를 서로 빼서 차이 CI를 만들지 않는다. [S6]

한 클래스가 사라진 반복은 동일한 0분모 정책을 적용하고 수를 보고한다. 퇴화 구간은 [값,값]과 플래그로 표기하며 확실성 보증으로 해석하지 않는다. 그룹 수·최대 그룹 비중도 함께 보고한다. rating/길이별 결과는 설명용이며 좋은 하위집단을 전체 결과로 채택하지 않는다.

손계산 계약: gold=[P,P,N,N], pred=[P,error,P,neutral]이면 Accuracy=0.25, positive P/R/F1=0.5, negative F1=0, Macro F1=0.25, error=1, neutral=1, 행렬 합계=4다.

## 7. 파일 책임·인터페이스

새 코드는 `scripts/benchmark/`에 두어 엔진 실행 의존성과 분리한다. `scripts/__init__.py`, `scripts/benchmark/__init__.py`는 빈 패키지 파일이다. 공개 analyze API와 기존 fixture CLI는 유지한다.

| 파일 | 책임 |
|---|---|
| `docs/evaluation/sentiment-protocol.md` | 실행 전 확정 프로토콜·선택 규칙·변경 이력 |
| `docs/evaluation/exposure-register.jsonl` | 노출 문장·출처 |
| `requirements-eval.in`, `requirements-eval.lock` | 실제 검증한 평가 환경 버전·전이 의존성·해시 |
| `scripts/benchmark/data.py` | 파싱·중복·분할 |
| `scripts/benchmark/metrics.py` | 행렬·Wilson·paired bootstrap |
| `scripts/benchmark/artifacts.py` | allowlist 스냅샷·manifest 검증 |
| `scripts/benchmark/runner.py` | worker·timeout·입출력 검증 |
| `scripts/prepare_sentiment_benchmark.py` | 준비 CLI |
| `scripts/predict_sentiment_benchmark.py` | gold 없는 예측 worker |
| `scripts/evaluate_sentiment_benchmark.py` | 개발·선택·최종 평가 CLI |
| `tests/benchmark/test_data.py` | 원문·중복·분할 계약 |
| `tests/benchmark/test_metrics.py` | 손계산·재표집 계약 |
| `tests/benchmark/test_runner.py` | 오류·누락·경로·잠금 |
| `README.md`, `docs/evaluation/sentiment-results.md`, `.gitignore` | 결과·재현·산출물 제외 |

다음은 구현 완료 코드가 아니라 내부 함수 사양이다.

```text
parse_source(path:Path) -> (rows:list[dict], exclusions:list[dict])
  row={id,text,rating:int,label,source_line:int,text_sha256}
group_rows(rows:list[dict], exposures:list[str]) -> list[dict]
  group={group_id,rows:list[dict],exposed:bool}
allocate_groups(groups:list[dict], seed:int) -> dict[str,list[dict]]
  keys=development,selection,final,reserve
cross_split_pairs(splits:dict[str,list[dict]], exposures:list[str]) -> list[tuple[str,str]]
metrics(gold:list[dict], predictions:list[dict]) -> dict
paired_intervals(gold:list[dict], a:list[dict], b:list[dict], *, seed:int, repeats:int) -> dict
snapshot(root:Path, destination:Path) -> dict
verify_manifest(path:Path) -> dict
run_predictions(inputs:Path, candidate_manifest:Path, output:Path, *, modifiers:bool) -> dict
```

CLI 구현 계약은 다음과 같다. baseline/후보 manifest에는 사용할 Python 실행 파일과 runtime 환경 지문도 저장한다. evaluator는 같은 Python이 두 엔진을 실행한다고 가정하지 않는다. 아래 명령은 작업 완료 후의 실행 인터페이스이며 현재 존재하는 구현으로 주장하지 않는다.

```bash
python -m scripts.benchmark.artifacts snapshot --root . \
  --output artifacts/benchmark/v1/baseline
python -m scripts.evaluate_sentiment_benchmark \
  --benchmark artifacts/benchmark/v1 --split development \
  --candidate-manifest artifacts/benchmark/v1/baseline.json \
  --modifiers both --output artifacts/benchmark/v1/runs/development-baseline
python -m scripts.evaluate_sentiment_benchmark \
  --benchmark artifacts/benchmark/v1 --split selection \
  --selection-manifest artifacts/benchmark/v1/candidates/selection.json \
  --output artifacts/benchmark/v1/runs/selection
```

`snapshot`은 output에 파일을 복제하고 그 형제 경로 `<output>.json`에 manifest를 쓴다. selection.json은 순서 있는 후보 manifest 경로/해시 배열, tie-break, protocol/split/evaluator 해시를 담는다. selection CLI가 선택 결과와 release.json을 생성한다. 단일 후보일 때도 selection manifest를 입력으로 받되 selection 입력/gold는 열지 않고 후보 동결 결과만 만든다. final CLI는 release에 지정된 켬/끔 조건을 사용하며 `--candidate-manifest`나 `--modifiers` override를 거부한다.

## 8. 실행 작업

### A1 — 프로토콜·현재 기준선·환경 보존

**Files:** protocol, exposure register, requirements-eval 파일, artifacts.py, test_runner.py, .gitignore.
**Consumes:** 현재 작업 트리, 이 계획. **Produces:** baseline 스냅샷·실제 환경 lock.

- [ ] HEAD·diff·미추적 실행 파일을 기록하고 src/data/main/설치 명세를 복제한다. 별도 프로세스에서 import·자원 해시를 확인한다.
- [ ] baseline의 합성 fixture 켬/끔과 정보 추출 결과를 저장한다. 과거 보고 수치를 강제하지 않고 현재 관측과 차이를 기록한다.
- [ ] protocol·노출 목록을 고정한다. 평가 환경을 설치·검증해 실제 버전·wheel 해시를 잠근다.
- [ ] data 누락 거부, 후보 밖 import 거부, 1바이트 변경 감지, .env 제외 테스트를 작성→실패 확인→구현한다.
- [ ] `python -m pytest tests/benchmark/test_runner.py -q` 실행. 기대: 위 계약 통과 및 baseline 실행 경로 일치.

### A2 — 데이터 준비·분할 구현

**Files:** data.py, prepare CLI, test_data.py, source/manifest/exclusions 산출물.
**Consumes:** 고정 protocol·exposures·원본 TSV. **Produces:** 세 split의 inputs/gold와 감사 기록.

- [ ] 파싱 계약과 중복·분할 테스트를 먼저 작성하고 구현 전 실패를 확인한다.

```python
def test_parser_preserves_text_and_maps_ratings(tmp_path):
    from scripts.benchmark.data import parse_source
    path = tmp_path / "source.tsv"
    path.write_bytes("5\t  좋아요\t🙂  \r\n2\t별로\n3\t보통\nX\t오류\n".encode())
    rows, excluded = parse_source(path)
    assert [r["label"] for r in rows] == ["positive", "negative"]
    assert rows[0]["text"] == "  좋아요\t🙂  "
    assert rows[0]["source_line"] == 1
    assert {r["reason"] for r in excluded} == {"excluded_rating_3", "malformed_record"}
```

- [ ] 정확 중복 상충 제외, 같은 극성 대표 선택, 근접 그룹 양극성 유지, 체인 연결, 19/20자 경계, 0.85 경계, 원문 보존을 검사한다.
- [ ] 입력 순서를 뒤집어도 같은 split ID, exposure는 development, 그룹 무분할, 같은 seed 결정성을 검사한다. hash 입력·직렬화 옵션도 고정한다.
- [ ] LSH가 빈 후보를 반환해도 정확 교차 감사가 누락을 검출하는지 작은 전체 쌍 완전탐색과 대조한다.
- [ ] 4절 알고리즘을 구현한다. 준비 코드가 감성 엔진을 import/호출하지 않는지 확인한다.
- [ ] 실제 source SHA·원본 바이트·README·출처 조건을 확보하고 다음 명령을 실행한다.

```bash
python -m pytest tests/benchmark/test_data.py -q
python -m scripts.prepare_sentiment_benchmark \
  --source artifacts/benchmark/v1/raw/naver_shopping.txt \
  --source-manifest artifacts/benchmark/v1/source.json \
  --protocol docs/evaluation/sentiment-protocol.md \
  --exposures docs/evaluation/exposure-register.jsonl \
  --output artifacts/benchmark/v1 --seed 20260905
```

- [ ] 기대: 원문 대신 split/제외 통계, 교차 누출 0, 해시 출력. 재실행에서 input/gold/group 바이트 동일. timestamp는 별도 실행 로그에만 기록한다.

**Gate:** 표본·비율·추적·교차 검사 통과 뒤 development만 열 수 있다.

### A3 — 지표·gold 없는 실행기

**Files:** metrics.py, runner.py, predict/evaluate CLI, test_metrics.py, test_runner.py.
**Consumes:** inputs/gold, 후보 스냅샷. **Produces:** 완전한 ID별 예측·2×4 지표·CI.

- [ ] 6절 손계산, 모두 neutral/error/정답, 레이블 뒤집힘, 빈 자료, ID 누락/중복 테스트를 작성한다.
- [ ] 동일 A=B이면 차이 CI=[0,0], 그룹 전체 동시 재표집, seed 재현, Wilson 0/N과 N/N 범위를 검사한다.
- [ ] worker gold 인자 거부, 오류 후 다음 행 처리, timeout/초기화 실패 구별, import 경로 위조 거부 테스트를 작성하고 실패를 확인한다.
- [ ] 5~6절 계약으로 구현한다. 기존 fixture 로더는 유지하고 외부 benchmark 로더를 분리한다.
- [ ] `python -m pytest tests/benchmark -q` 실행. 작은 합성 파일로 CLI 결과를 손계산과 대조한다. final은 읽지 않는다.

### A4 — 외부 development 진단

**Files:** development 결과와 protocol 개발 기록. 엔진 변경은 B 계획 담당.
**Consumes:** baseline·development만. **Produces:** 오류 유형과 후보 구성 근거.

- [ ] baseline 켬/끔을 development 전체에 실행하고 모든 해시·실제 N을 기록한다.
- [ ] ID hash 순 오분류 최대 100건 및 정답 50건을 점검한다. 형태소/사전/극성/범위/혼합/문맥/별점 불일치/실행 오류로 분류하고 불명확하면 미분류로 남긴다. AI 보조 분석을 사람 검수라고 쓰지 않는다.
- [ ] gold를 고치지 않고 반복되는 오류와 가설을 기록한다. baseline만으로 final 평가를 진행하거나, B 계획으로 개선 후보를 만들어 돌아온다.
- [ ] selection/final 원문·개별 예측·점수 미노출 여부를 확인한다.

### A5 — 후보 선택·release 동결

**Files:** candidates, release.json, 접근 기록.
**Consumes:** 미션 적격 후보 1~3개·selection. **Produces:** final 후보 하나.

- [ ] 후보별 기능/API 테스트를 확인하고 스냅샷을 만든다. 목록·등록 순서·tie-break를 점수 보기 전에 기록한다.
- [ ] 여러 후보이면 selection 집계만 보고 5절대로 선택한다. 하나면 selection 사용을 생략한다.
- [ ] 후보·baseline·모델·사전·의존성·evaluator·protocol·split 해시를 잠근다. 실행 시 설정 override를 금지한다.
- [ ] 작은 합성 테스트에서 manifest 불일치 시 final 파일을 열기 전에 종료하는지 확인한다.

### A6 — 최종 실행·판정·오분류 공개

**Files:** final 결과, results 문서.
**Consumes:** release·final·baseline. **Produces:** 유효한 미노출 평가와 목표 판정.

```bash
python -m scripts.evaluate_sentiment_benchmark \
  --benchmark artifacts/benchmark/v1 --split final \
  --release-manifest artifacts/benchmark/v1/release.json \
  --output artifacts/benchmark/v1/runs/final
```

- [ ] 해시를 검증하고 지정된 켬/끔·baseline 조건만 실행한다. 모든 neutral/error를 분모에 넣는다.
- [ ] 행렬 합계=N, 모든 ID 1회, 후보/기준선 표본 동일, bootstrap seed/그룹 동일을 확인한다.
- [ ] 전체 결과·성능 목표별 통과/미달·개선 여부를 저장한 뒤 원문 오답을 연다. 열람 시각을 기록한다.
- [ ] 실제 오분류 10건 이상에 입력/gold/예측/근거/원인/개선 한계를 쓴다. 부족하면 development의 실제 오답으로 보충하고 출처를 구별한다.
- [ ] 수정어 전후 결과와 낮은 성능도 남긴다. final을 본 뒤 수정했다면 다음 버전의 미노출 검증으로 재사용하지 않는다.

### A7 — 재현·전체 회귀·문서화

**Files:** README, results, .gitignore, benchmark 테스트.

- [ ] `python -m pytest -q` 실행, 정보 추출 결과를 A1과 대조한다. 기존 5종 P/R·실패 5건 분석이 유지되는지 확인한다.
- [ ] 깨끗한 checkout+lock 환경에서 고정 source→같은 split 해시→같은 동결 예측을 재현한다. 이는 모델 재튜닝이 아니다.
- [ ] 실제 N·별점 분포·정제·CI·출처·오분류·한계·재현 명령을 문서화한다. 규칙/통계 방식 차이와 중립/복합 정책도 유지한다.
- [ ] `git diff --check`와 변경 목록을 확인한다. artifacts/raw/비밀 파일을 stage하지 않는다. 기존 사용자 변경과 실행 변경을 구별해 제출한다.

## 9. 미션 추적·중단 규칙

| 요구 | 담당 |
|---|---|
| 사전 200개·도메인 30개 | A5 현재 후보 검증 / 개선 시 B2 |
| 토큰화·사전 합산·부정·강조·이중부정 | A5 / 개선 시 B3 |
| 100개 이상 평가·Accuracy/F1 | A2·A3·A6 |
| 수정어 전후·오분류 10건 | A4·A6 |
| 정규식 5종·50문장·P/R·실패 5건 | A1 보존·A7 회귀/문서 |
| 설치·출처·충돌·확장·한계·중립/복합 | A1·A3·A7 / B2·B4 |

데이터·환경·manifest 실패는 영향받은 단계를 미완료로 보고한다. KOMORAN/KNU 실패는 baseline 평가를 막지 않는다. final 오류를 발견하면 결과를 보존하고 새 protocol/benchmark 버전으로 다룬다. 점수가 낮다는 이유로 레이블·분모·합격선을 바꾸지 않는다.

## 10. 조사 출처

- **[S1]** [쇼핑 후기 설명](https://github.com/bab2min/corpus/tree/master/sentiment): 필드·수집 기간·극성 매핑·분포·공개 미리보기.
- **[S2]** [말뭉치 저장소](https://github.com/bab2min/corpus): 저자의 Public Domain 표기. 모든 원 게시물/플랫폼 권리 관계를 별도 보증하는 것으로 확대하지 않음.
- **[S3]** [scikit-learn 데이터 누출 지침](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage): test 정보로 모델·전처리 선택을 하지 않는 원칙. scikit-learn 설치 요구는 아님.
- **[S4]** [datasketch MinHash LSH](https://ekzhu.com/datasketch/lsh.html): Jaccard 후보 검색. 정확 교차 검사는 본 계획의 추가 설계.
- **[S5]** [NIST 비율 신뢰구간](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm): Wilson 공식.
- **[S6]** [SciPy bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html): paired/percentile 원리. 그룹 확장·seed·반복 수는 본 계획의 선택이며 SciPy 설치는 필수가 아님.

공식 README/API 문서를 조사했으며 후기 원본 전체를 내려받거나 평가하지 않았다. 공개 미리보기에서 노출된 문장을 exposure register에 넣는다. 모든 작업 체크박스는 미실행 상태다.
