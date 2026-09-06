# M2 동결 후보의 독립 final 결과

Phase 2를 development **60.61%**에서 종료하고 M2-L 한 후보를 동결했다.
2026-09-07에 v2 direct 경로로 selection 평가를 생략하고 untouched final **10,000건**을
한 번 실행했다. **Final Accuracy 60.62%, 목표 70% 미달**이다.
이 결과 이후 엔진·사전·평가 인프라를 수정하지 않았으며 같은 holdout을 재평가하지 않았다.

## 같은 final에서 기준 M과 비교

기준 후보 M은 `0c25c75145f308a572083702f51f3e238169bb42`의 엔진이다.
추적 파일의 Git blob과 스냅샷 해시를 대조했고, 자동 생성된 egg-info 패키징 메타데이터는
별도로 기록했다. 두 후보 모두 modifier on이며 같은 입력·gold·그룹을 사용했다.
분석 실패와 중립 예측도 Accuracy 분모에 포함한다.

| 지표 | 기준 M | 동결 M2-L | M2-L − M |
|---|---:|---:|---:|
| Accuracy | 48.24% | 60.62% | +12.38%p |
| Macro F1 | 0.589757 | 0.695179 | +0.105422 |
| Positive recall | 68.35% | 77.95% | +9.59%p |
| Negative recall | 28.44% | 43.56% | +15.12%p |
| no_match | 3923 | 2422 | -1501 |
| analysis error | 192 (1.92%) | 192 (1.92%) | 0 |
| 중립 예측 | 4112 | 2706 | -1406 |
| 상쇄 | 189 | 284 | 95 |

## 95% 신뢰구간

| 지표 | 기준 M | M2-L |
|---|---:|---:|
| Accuracy Wilson | 47.26%–49.22% | 59.66%–61.57% |
| Accuracy 그룹 bootstrap | 47.24%–49.23% | 59.67%–61.59% |
| Macro F1 그룹 bootstrap | 0.580183–0.599357 | 0.686408–0.704231 |

동일 그룹을 함께 재표집한 기준 M 대비 Accuracy 차이의 95% CI는
**+11.68–+13.06%p**,
Macro F1 차이의 95% CI는 **+0.098655–+0.112371**다.
PCG64 seed 20260906, 2,000회 percentile bootstrap을 사용했다.
그룹은 9,999개, 최대 그룹 점유율은 0.02%,
분모 퇴화 표집은 0회다. CI는 표본 변동을 나타내며 별점 라벨의
잡음이나 다른 운영 분포로의 일반화까지 보장하지 않는다.

## 데이터 독립성과 일회성 실행

개발 종료 후 노출 등록부를 다시 만들었다. 사전·검수 문맥, 테스트·문서·수동 예제,
기존 노출을 수집했다. 기존 전체 그룹과 등록 예제를 정규화 완전 중복 및 길이 20자 이상
5-shingle Jaccard ≥ 0.85로 완전 후보 탐색해 연결 성분을 구성했다.
기존 그룹은 분할하지 않았고, old non-reserve·mining·development·노출에 연결된
untouched 10행을 제외했다. 원문을 바꾸지 않았고 분할 간 중복은 0건이다.

Seed 20260907로 라벨과 무관하게 전체 그룹을 배정했다. v2 스키마가 요구하는
selection 5,000건은 파일만 준비했고 selection 시도·선택 평가를 하지 않았다.
Final 10,000건과 별도로 future reserve 126,888건이 남는다.
원본 경로가 상대 경로였던 준비 단계 오류는 release 전에 절대 경로 메타데이터로
수정했다. 이때 holdout 파일 바이트는 바뀌지 않았고 final 시도도 시작 전이었다.

후보 manifest와 direct release, 환경·파일 목록·해시를 실행 전에 검증했다.
`final-attempt.json` 생성으로 시도를 소비하고 M2-L과 기준 M의 예측을 각각 한 번 실행했다.
Selection 시도 마커는 없으며 release의 selection manifest/report는 null이다.
Final은 실행 후 노출 데이터로 취급한다. 목표 미달 여부와 무관하게 동일 v2 final 재실행은 금지한다.

## 목표와 남은 한계

| 판정 | 결과 |
|---|---|
| Accuracy ≥ 0.70 | False |
| Macro F1 ≥ 0.68 | True |
| Positive recall ≥ 0.60 | True |
| Negative recall ≥ 0.60 | False |
| Analysis error rate ≤ 0.025 | True |

개발 Gate 67% 미달 상태에서 사용자의 명시적 지시로 개발을 종료했다. 평가 코드의
목표값이나 통계 정책은 바꾸지 않았다. 주 목표 판정은 `False`, 보조 목표
전체 판정은 `False`다. 반올림으로 성공 판정을 올리지 않는다.

미매칭, 불완전한 형태소 분석, 혼합 측면·부정 범위·가정·상태 변화 해석이 남아 있다.
별점은 감성의 잡음 있는 대리값이다. 독립적인 사람의 사전 검수나 실제 운영 분포 검증을
완료했다고 주장하지 않는다. 남은 문제를 이 final의 개별 문장에 맞춰 수정하지 않았다.
향후 개선이 별도로 승인되면 새로운 untouched reserve와 새 benchmark 버전에서 평가해야 한다.

과거 v1 final 36.20%, M의 과거 development 49.85%, M2 development 60.61%와
이번 M2 final 60.62%는 서로 다른 평가 결과다.

## 검증과 산출물

엔진의 마지막 전체 회귀는 **564개**, Python 3.10 관련 테스트는 **152개** 통과했다.
Final 전에 v2 계약 테스트 **53개**를 재확인했다. 실행 전후 release·후보·평가 코드의
해시를 확인했으며 엔진·사전·평가 인프라 변경은 없다.

- [최종 집계·CI·해시 기록](engine-m2-final-results.json): 클래스별 P/R/F1, 혼동행렬과 목표 판정 포함
- [후보 동결 기록](engine-m2-freeze.json)
- [최종 개발 기록](engine-m2-development.md)
- 원본 집계: `artifacts/benchmark/v2/final-run/report.json`
- Direct release: `artifacts/benchmark/v2/release.json`
- 일회성 시도: `artifacts/benchmark/v2/final-attempt.json`
- 준비 계보: `artifacts/benchmark/v2/source.json`

Release SHA-256: `e23097c0cc0e4ea6d4e237e7d794340256de8ee3917233238e5df1e0ead8b5dc`.
원문과 예측은 로컬 artifacts에 보존하고 이 문서에는 리뷰 원문을 싣지 않았다.
