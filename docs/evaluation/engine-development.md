# 감성 엔진 재설계 개발 기록

2026-09-06. **M 엔진 구현, 개발 비교와 후보 동결 완료.** 승인된 위치 계약 개정으로
B1을 통과한 뒤 compiled 사전과 국소 수정어 문법을 공개 API에 연결했다.
새로운 독립 selection/final 평가는 미실행이다. 기존 v1 final은 이미 노출되었으므로
새 엔진의 독립 판정에 재사용하지 않는다. 외부 정확도 80% 달성을 주장하지 않는다.

## 구현과 위치 계약

`korean.py`의 단일 잠금·지연 초기화 어댑터가 KOMORAN을 호출한다. 원문은 보존하고
jar의 Java 공백 축약·trim과 대응하는 경계표로 UTF-16 위치를 Python 위치로 변환한다.
인접 SW surrogate 두 개는 실제 `getMorph()`의 UTF-16 값이 원문 문자와 정확히
일치할 때만 복원한다. 원문 공백에 해당하는 TAB/SW는 위치 추적에 남기고 감성 토큰에서
제외한다. 형태소를 문자열 검색으로 정렬하거나 잘못된 범위를 임의로 보정하지 않는다.

여러 어절로 된 고유명사(예: 날짜 `3월 15일`)는 전체 범위를 유지하고 시작 어절 번호를
부여한다. 축약 활용형의 양수 길이 중첩은 허용한다. zero-length, 역전, 범위 초과,
단독 surrogate, 원문 어절에 속하지 않는 끝점은 `MorphologyError(ValueError)`다.
공백 대응표와 원문 어절 번호는 수정어 거리와 줄 경계 검사에도 사용한다.

일부 음절 뒤 호환 자모 입력에서 KOMORAN은 원문 길이를 줄인다. `좋아요ㅎ좋다`처럼
범위 숫자는 유효해도 뒷부분 위치가 어긋날 수 있다. 분석 결과의 첫 시작과 마지막 끝이
분석기 입력 전체 길이를 덮지 않으면 명시적으로 실패시킨다. 개발 4,000건 중 **81건**이
이 검사에서 실패했다. 조용한 오프셋 복원이나 기존 엔진 fallback은 없다. 기술 예문 통과는
모든 사용자 입력의 분석 성공을 보장하지 않는다.

## 사전 감사와 문법

M은 프로젝트 직접 구축 사전만 사용한다. 원본 297개를 전수 감사한 결과 compiled
canonical 항목은 **262개(긍정 128, 부정 134), 고객지원 도메인 58개, 미해결 key 충돌 0개**다.
활용형은 canonical로 병합하고 합성 예외 26개는 제외 기록과 함께 원본에 보존했다.
독립 어휘 89개를 보강했다. AI 보조 감사이며 독립 사람 검수는 수행하지 않았다.
점수 ±1/±2/±3은 약한/명확한/강한 평가를 나타내는 경험적 값이다.

- [검수·채택·제외·POS alias](../../data/lexicon_annotations.json): 각 표면형의 관측 key와 판단.
- [출처와 집계](../../data/lexicon_provenance.json): 원본 해시, 추가·제외 어휘, 점수 기준.
- [compiled 사전](../../data/sentiment_lexicon_compiled.json): canonical key와 source/annotation/model/adapter 해시.
- [빌더](../../scripts/build_sentiment_lexicon.py): 같은 KOMORAN으로 컴파일하며 말단 조사·어미만 제거한다.

내부 조사·파생접사·서술격은 보존한다. 문맥에서 실제 관측한 명사 POS alias만 명시적으로
허용한다. 동일 key·동일 점수는 병합하고 반대 점수는 검수 override 또는 제외가 필요하다.
KNU는 이용·파생물 배포 근거를 확정하지 못해 도입하지 않았다. K 후보는 없다.

사건은 형태소/POS 연속열의 leftmost-longest 순서로 고른다. 임의의 중간 토큰 삭제와
합성명사 내부 부분 매칭을 막는다. 국소 문법은 선행 MAG 강조·안/못, `-지 않다/못하다`,
명사+조사+없다/아니다, 명사+안/못+하다, `않은 것은 아니다` 등의 연속 구조를 처리한다.
문법으로 허용된 연결에만 원문 사이 어절 2개 상한을 적용한다. 다른 절·줄을 넘어
가장 가까운 감성어에 붙이지 않는다. `형편없다`, `마음에 들다`는 원자적 어휘로 내부
연산자를 소비한다. 각 연산자는 한 사건만 소유하며 rule ID와 대상 사건을 추적한다.

공개 API와 결과 필드는 유지한다. 수정어 off는 같은 사건의 기본 점수만 합산한다.
강조 곱은 최대 2, 부정은 횟수의 홀짝으로 부호를 결정한다. 공개 `raw`는 원문에서
잘라내고 같은 어절의 말단 어미·조사를 포함한다. `tokens`의 기존 표시용 분절은 유지한다.

기존 테스트 중 가까운 감성어에 부정을 임의 배분하던 기대값과 합성 문장 사전 예외는
새 계약에 맞췄다. `피해없다`, `문제가 해결되다`를 단일 평가 문장으로 취급하지 않는다.
인용 발화, 가정·희망, 장거리 문맥, 혼합 감성의 우선순위 판단은 지원 범위 밖이다.
고정 합성 fixture의 문장·레이블과 정보 추출 코드는 변경하지 않았다.

## 개발 비교와 오류 진단

기존 baseline snapshot의 저장된 development 예측과 M의 새 예측을 비교했다.
M worker는 gold 없이 id/text만 받는다. 평가 도구는 development 파일·해시와 기존
baseline 예측을 읽으며 selection/final 원문은 열거나 재평가하지 않는다.

| 후보 | 수정어 | Accuracy | Macro F1 | 중립 | 분석 오류 |
|---|---|---:|---:|---:|---:|
| baseline | off | 35.850% | 0.485015 | 2,382 | 0 |
| baseline | on | 36.275% | 0.491518 | 2,369 | 0 |
| M | off | 48.300% | 0.586493 | 1,612 | 81 |
| M | on | **49.850%** | **0.607908** | 1,593 | 81 |

분모는 각 4,000건이며 중립·분석 오류도 오답이다. baseline→M on 차이는 +13.575%p다.
형태소·사전·문법을 함께 바꾼 결과이므로 형태소 분석기만의 인과 효과로 해석하지 않는다.
같은 M 사전·사건의 on/off 차이는 +1.550%p: 정답 전환 71건, 오답 전환 9건,
둘 다 정답 1,923건, 둘 다 오답 1,997건이다. M on 중립은 미매칭 1,509건과
양·음 상쇄 84건이다. 미매칭 전체를 어휘 부족 또는 형태소 오류 중 하나로 단정하지 않는다.
[전체 집계](engine-development-results.json), [오류 집계·표본 ID](engine-development-diagnostics.json).

M on 오답을 ID 문자열 순으로 정렬한 첫 25건의 원문·형태소·사건을 AI가 검토했다.
여러 원인이 겹칠 수 있는 비무작위 표본이며 아래 수치는 전체 오류의 원인 비율이 아니다.

| 진단 범주 | 표본 중 건수 | 판단 예 |
|---|---:|---|
| 형태소·위치 | 8 | 미등록어 NA, 잘못된 분절, 원문 길이 축소 |
| 사전 coverage | 6 | `굿`, `아프다`, `속상하다` 등의 미수록 평가 |
| 극성·점수 | 2 | 긍정·부정 어휘 강도 합계와 전체 별점의 불일치 |
| 연결·경계 | 1 | 무공백 명사 뒤 술어에 합성명사 방지 조건이 적용됨 |
| 혼합 감성 | 4 | `편합니다`와 `늦어요`의 상쇄, 장단점 공존 |
| 문맥 | 14 | `좋겠는데`라는 희망, 비교 대상·기능 불만·간접 추천 |
| 별점 잡음 가능성 | 3 | 긍정 문면과 부정 gold 등; 정답 오류로 확정하지 않음 |

단일 리뷰를 사전 예외로 추가하거나 gold를 수정하지 않았다. 초기 baseline 오답도 같은
방법으로 첫 25건을 검토했고 활용·높임·무공백 입력, 혼합 감성, 별점 불일치를 관찰했다.
위치 축소는 별도 합성 입력으로 재현해 공통 fail-fast 검사를 추가했다.

## 실행 환경과 검증

Ubuntu/WSL2 Linux 6.6.87.2 x86_64에서 별도 `/tmp` 환경으로 설치했다.
Python 3.10.20 / 3.12.3, Temurin JDK **17.0.20.1+1**, heap 상한 **1,024 MiB**,
KoNLPy **0.6.0** 번들 `komoran-3.0.jar`, JPype1 **1.6.0**, NumPy **2.2.6**,
lxml **6.0.2**, packaging **25.0** 조합이다. 실제 jar/model과 JVM 해시는
[후보 환경 기록](engine-candidate-M-provenance.json)에 저장했다.
`requirements-runtime.lock`은 runtime hash lock, `requirements.txt`는 editable/test 설치다.
기존 `requirements-eval.lock`은 과거 baseline 환경 기록이므로 새 runtime과 혼합하지 않는다.

- 최신 Python 3.12 전체 `python -m pytest -q`: **356 passed**.
- 최신 Python 3.10 감성·CLI `python -m pytest tests/sentiment tests/test_integration_cli.py -q`: **209 passed**.
- 이전 단계 Python 3.10 전체 354개 통과 후, 마지막 위치 축소 검사 2개를 포함한 관련 검증을 재실행했다.
- 실제 어댑터 probe: 두 버전 모두 **16/16**, 종료 코드 0.
  [3.10](komoran-adapter-python310.json), [3.12](komoran-adapter-python312.json).
- compiled 재생성의 바이트 동일성, 부정 연결 대상·연산자 단일 소유, 강조 부호·합계,
  원문 span, 모델/자원 누락, JVM 부재 진단을 검사했다.
- 기존 `--text`, `--evaluate all`, JSON/text 출력과 종료 코드 통합 검사가 통과했다.
  A1 snapshot의 정보 추출 전체 결과와 일치한다: TP 57 / FP 0 / FN 6, micro F1 0.95.
- 고정 합성 기본/추가 100문항의 M on 정확도는 각각 86%/88%다. 기존 baseline의
  92%/90%보다 낮다. 새 문법이 제거한 거리 기반 연결·문장 예외도 영향을 주므로
  모든 평가셋에서 개선되었다고 주장하지 않는다. [통합 집계](engine-integration.json).

전체 개발 입력을 순회하되 매번 형태소 캐시를 비우고 JVM은 유지했다. on 분석을 측정한 뒤
같은 입력의 off 사건·raw·기본 점수·span 동일성과 기여도 합계를 확인했다.
분석 성공 **3,919건 모두** 불변식을 통과했고 매칭 입력은 2,410건이다.

| Python | cold 첫 분석 | warm p50 / p95 | peak RSS |
|---|---:|---:|---:|
| 3.10.20 | 2.530초 | 0.636 / 2.265 ms | 683.4 MiB |
| 3.12.3 | 2.214초 | 0.519 / 1.622 ms | 596.0 MiB |

성공 입력 길이는 min 5 / p50 29 / p95 100 / max 140 Python code point다.
오류 81건은 지연 분포에서 제외하고 별도 집계했다. 동시 probe 종료 후 각 환경에서
순차 측정했다. 측정 오차와 장비 의존성이 있으며 장문 입력에 대한 보장은 아니다.
기존 worker의 초기화 120초·행당 10초 제한에서 on/off 모두 timeout 0건이었다.
[3.10 프로파일](engine-profile-python310.json), [3.12 프로파일](engine-profile-python312.json).

## 재현과 후보 인계

JDK 17을 설치하고 `JAVA_HOME`을 지정한다. Python 3.10에서도 같은 절차를 사용한다.

```bash
uv venv /tmp/sentiment-komoran-venv --python python3.12
uv pip install --python /tmp/sentiment-komoran-venv/bin/python \
  --require-hashes -r requirements-runtime.lock
uv pip install --python /tmp/sentiment-komoran-venv/bin/python -r requirements.txt
/tmp/sentiment-komoran-venv/bin/python -m scripts.probe_komoran \
  --output /tmp/komoran-adapter.json
/tmp/sentiment-komoran-venv/bin/python -m scripts.build_sentiment_lexicon \
  --output /tmp/sentiment-lexicon-compiled.json
cmp data/sentiment_lexicon_compiled.json /tmp/sentiment-lexicon-compiled.json
/tmp/sentiment-komoran-venv/bin/python -m scripts.run_engine_development \
  --output artifacts/benchmark/redesign-development-replay
```

개발 비교는 기존 `artifacts/benchmark/v1` development와 baseline snapshot이 필요하다.
출력 경로가 있으면 덮어쓰지 않고 실패하므로 새 경로를 지정한다. 최종 측정 스냅샷은
`artifacts/benchmark/redesign-development-M-final/candidate-M/`, 검증용 manifest는
그 형제 `candidate-M.json`이다. `candidate-manifest.json`에는 코드·사전·compiled·model·
JDK·lock·protocol·입출력 해시를 고정했다. 문서의 환경 기록은 이 파일의 사본이며
상대 `candidate-M.json` 경로는 **원래 산출물 디렉터리 기준**이다. 계획 문서 해시는
동결 시점의 값이고 이후 결과·체크리스트 갱신은 후보 코드에 영향을 주지 않는다.

```bash
python -m scripts.profile_sentiment_engine \
  --candidate-manifest artifacts/benchmark/redesign-development-M-final/candidate-M.json \
  --inputs artifacts/benchmark/v1/development.inputs.jsonl \
  --output /tmp/engine-profile.json
```

상세 snapshot·예측·개발 원문은 Git 제외 대상이고 집계·환경·검수 근거만 문서에 보존한다.
이번 인계는 M 개발 후보 하나다. A5~A7의 새 독립 평가에는 기존 개발·노출 자료를
제외한 새 표본과 평가 버전이 필요하다. 복수 후보 선택 경로의 기존 release 형식 불일치도
그 전에 해결해야 한다. v1의 완료된 release/final 파일은 변경하지 않았다.

## 최초 B1 실패 이력

2026-09-05의 직접 UTF-16 경계 변환 probe는 Python 3.10/3.12 모두 초기화했지만
16개 중 6개 위치 사례에서 실패해 당시 B2~B4를 중단했다.
[초기 3.10 보고서](komoran-probe-python310.json), [초기 3.12 보고서](komoran-probe-python312.json).

| 사례 | 최초 관측 |
|---|---|
| `좋다  좋다`, `  좋다` | 반복 공백 축약·선행 trim으로 원문 위치 불일치 |
| `🙂 좋다`, `🙂` | surrogate 반쪽 SW 두 개, Python 문자열 변환 오류 |
| `좋다\t좋다`, `좋다  \t나쁘다` | TAB/SW 어절 소유 실패와 공백 축약 위치 불일치 |

실제 jar를 `javap -c -p`로 확인해 Java `replaceAll("[ ]+", " ")`와 `trim()`을
확인했다. 이후 사용자가 공백 대응표, 정확한 surrogate 쌍 복원, TAB 추적을 승인했고
현재 단일 어댑터에 적용·재검증했다. 초기 raw probe의 부적격 결과와 현재 어댑터의
적격 결과는 대상 계약이 다르다. 최초 진단 의존성 파일은 이력을 위해 보존한다.
