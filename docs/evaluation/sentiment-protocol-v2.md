# M2 독립 감성 평가 프로토콜 v2

이 프로토콜은 M 기준 커밋 `0c25c75145f308a572083702f51f3e238169bb42` 이후의
독립 평가를 정의한다. 현재 구현 범위는 **Phase 1: 평가 릴리스와 일회성 실행 인프라**다.
실제 M2 workset, selection/final 생성, 사전 확장 및 정확도 측정은 아직 수행하지 않았다.

## 역사와 개발 경계

v1의 `scripts/benchmark/*`, 기존 prepare/run/evaluate 스크립트,
`sentiment-protocol.md`, `exposure-register.jsonl`은 수정하지 않는다.
v2는 기존 스냅숏 검증, 독립 예측 워커, 지표 계산만 가져다 사용하고 해당 의존 파일도
릴리스 해시에 포함한다. 감성 공개 API, 형태소 분석 실패 의미, 원문 위치와 정보 추출 동작은 유지한다.

학습 모델, 라벨을 이용한 사전 유도, 점수·가중치 탐색, 리뷰 문장별 예외를 금지한다.
개발에는 old v1 reserve 그룹만 사용한다. old development/selection/final 그룹은 제외한다.
후속 Phase 2에서 mining 40,000행과 open development 10,000행을 그룹 단위로 배정한다.
mining과 워커 입력은 `{id, text}`만 허용한다. 개발 중 selection/final은 만들거나 열지 않는다.

후보와 예제를 모두 동결한 뒤 v2 노출 등록부를 다시 생성한다. 이때 old non-reserve,
mining, open development, 등록된 노출과 연결되지 않은 untouched 그룹에서만
selection 약 5,000행, final 약 10,000행을 생성한다. 그룹 분리와 중복 배제,
원문 바이트 보존 및 출처 검증은 후속 데이터 준비 단계의 필수 조건이다.
Phase 1의 파일 해시 검증 자체를 reserve 적격성이나 독립성 검증으로 해석하지 않는다.

## 준비된 데이터 계약

벤치마크 디렉터리는 다음 파일을 보유한다.

- `manifest.json`: `format: 2`, `benchmark_version: "v2"`, 원본 경로/해시,
  프로토콜/노출 등록부 해시, split별 행 수와 inputs/gold SHA-256.
- `protocol.md`, `exposures.jsonl`: 준비 시점의 프로토콜과 노출 등록부 사본.
- `source.json`, `groups.jsonl`, `exclusions.jsonl`: 준비 단계의 출처·그룹·제외 기록.
- `selection.inputs.jsonl`, `selection.gold.jsonl`, `final.inputs.jsonl`, `final.gold.jsonl`.

원본 경로는 절대 경로다. 추가 split은 development/reserve만 허용한다.
inputs는 정확히 `id`, `text`만 포함한다. gold는 `id`, `label`, `group_id`를 포함하고
선택적으로 원본과 동일한 `text`를 포함할 수 있다. ID는 비어 있지 않은 고유 문자열이고,
inputs/gold 순서와 ID는 일치해야 한다. 정답은 positive/negative만 허용한다.

동결·사전 검증은 모든 split의 바이트 해시를 확인하지만 내용을 디코딩하지 않는다.
실행할 split의 스키마·행 수·정답 정합성 검사는 시도 마커를 생성한 다음 수행한다.
워커에는 검증된 inputs 파일의 id/text만 전달하며 gold 경로나 정답을 전달하지 않는다.
이는 협조적인 후보의 프로세스·입력 격리이며 악성 후보에 대한 OS 파일 접근 샌드박스는 아니다.

## 후보와 릴리스 동결

허용 후보는 `M2-L`, `M2-LH`, `M2-LHC`로 최대 3개다. modifier 설정은 on으로 고정한다.
M 기준 후보와 M2 후보는 각각 기존 `scripts.benchmark.artifacts snapshot`으로 보존한다.
M 기준 스냅숏은 위 기준 커밋의 엔진을 사용해야 한다. 비교 대상 스냅숏의 실제 출처는
후보 manifest의 source HEAD/diff/status로 감사한다.

데이터 준비 후 실행 등록은 다음 중 하나를 한 번만 수행한다. 아래 명령의 경로는
후속 단계에서 실제로 준비하고 감사한 로컬 산출물 경로다. 이 문서의 예제는 데이터를 생성하지 않는다.

```bash
python -m scripts.benchmark_v2.release selection \
  --benchmark artifacts/m2 \
  --candidate M2-L=artifacts/candidates/M2-L.json \
  --baseline-manifest artifacts/candidates/M.json \
  --protocol docs/evaluation/sentiment-protocol-v2.md \
  --exposures docs/evaluation/exposure-register-v2.jsonl \
  --output artifacts/m2/selection-manifest.json
```

복수 후보는 `--candidate NAME=MANIFEST`를 반복한다. 단일 후보를 직접 확정할 때는
`selection` 대신 `direct`를 사용하고 출력 경로를 `artifacts/m2/release.json`으로 지정한다.
직접 확정하면 selection을 열지 않는다. 이미 동결하거나 시도한 벤치마크에는 다시 등록할 수 없다.

두 경로는 같은 format-2 final 릴리스 스키마를 사용한다. 릴리스에는 다음을 고정한다.

- 기준 SHA, 선택된 후보와 기준 후보 manifest, modifier 설정.
- 선택 manifest와 집계 보고서 경로·해시(직접 확정 시 null).
- 벤치마크 manifest, 모든 split, 원본 및 그룹·제외·출처 파일의 해시.
- 현재 프로토콜·노출 등록부와 준비 당시 사본의 해시.
- 후보 스냅숏의 파일 목록·해시, 평가 Python 코드와 요구사항 파일의 목록·해시.
- Python 실행 파일 경로·버전, 플랫폼, 관련 패키지 버전, JVM 라이브러리 해시·경로,
  Java 실행 환경 변수. JVM을 찾지 못한 환경은 null로 기록하며 엔진의 실패 처리는 유지한다.
- 아래의 선택 정책 및 최종 목표값.

`freeze-record.json`은 등록 manifest의 경로/해시를, `release-record.json`은 final 릴리스의
경로/해시를 별도로 고정한다. 따라서 릴리스 JSON의 후보, modifier 또는 파일 목록을 수정해도
검증에 실패한다. 실행 코드의 파일 추가/삭제와 스냅숏 allowlist의 파일 추가도 거부한다.
절대 경로를 사용하므로 실행 환경과 아티팩트 위치를 보존해야 한다.

이 기록은 로컬 재현성·변경 탐지를 위한 것이다. 기록 자체와 모든 해시를 동시에 다시 쓰거나
시도 마커를 삭제하는 행위를 허용하는 서명·외부 불변 저장소는 아니므로,
해당 파일과 디렉터리는 감사 이력의 일부로 보존해야 한다.

## 일회성 후보 선택

선택을 열기 전 개발 Gate S는 accuracy 약 0.67, macro F1 0.65, 양·음성 recall 각각
0.58, analysis error rate 0.025 이하다. 가능하면 개발 accuracy 0.68–0.70을 확보한다.
개발 Gate S와 개발 종료 여부의 확인은 후속 후보·데이터 준비 단계의 책임이다.

```bash
python -m scripts.benchmark_v2.evaluator \
  --benchmark artifacts/m2 --split selection \
  --selection-manifest artifacts/m2/selection-manifest.json \
  --output artifacts/m2/selection-run
```

선택 적격성은 analysis error rate ≤ 0.025, positive/negative recall 각각 ≥ 0.55다.
적격 후보 중 최대 accuracy에서 0.005 이내인 후보를 묶고, 그 안에서 macro F1이 가장 높은
후보를 고른다. macro F1 차이 ≤ 1e-12는 부동소수점 동률로 처리한다.
그 다음 `M2-L`, `M2-LH`, `M2-LHC` 순서로 단순한 후보를 선택한다.
후보의 등록 순서는 결과에 영향을 주지 않는다.

출력은 후보별 예측, 집계 `report.json`, final용 format-2 `release.json`이다.
전원 부적격이면 집계 보고서를 보존하고 릴리스를 만들지 않으며 시도는 소비된다.
선택 후 코드·사전·modifier·평가 정책을 변경하지 않는다.

## 독립 final

```bash
python -m scripts.benchmark_v2.evaluator \
  --benchmark artifacts/m2 --split final \
  --release-manifest artifacts/m2/selection-run/release.json \
  --output artifacts/m2/final-run
```

직접 확정 경로에서는 `--release-manifest artifacts/m2/release.json`을 사용한다.
final은 동결된 릴리스만 받으며 후보·modifier override를 받지 않는다.
선택된 후보와 M 기준 후보를 같은 gold·그룹에서 비교한다.
동일 manifest면 예측을 재사용하며 별도 개선을 주장하지 않는다.

필수 보고 내용은 accuracy, macro F1, 클래스별 precision/recall/F1, 2×4 confusion matrix,
예측 수, neutral/no_match/cancellation/analysis-error 수와 error rate, Wilson accuracy 구간,
그룹 bootstrap 구간 및 paired 기준 후보 비교다. Bootstrap은 PCG64 seed 20260906,
2,000회, 그룹 단위 percentile 95% 구간으로 고정한다.

주 목표는 반올림 전 accuracy ≥ **0.70**이다. 보조 목표는 macro F1 ≥ 0.68,
positive recall ≥ 0.60, negative recall ≥ 0.60, analysis error rate ≤ 0.025다.
`primary_passed`와 `secondary_passed`를 따로 기록하며, 0.699x를 성공으로 올림하지 않는다.

## 시도 소비와 출력 보존

`selection-attempt.json`과 `final-attempt.json`은 벤치마크 디렉터리에 배타적으로 생성한다.
마커가 만들어지는 순간 시도는 소비된다. 그 다음 입력 해석·워커·보고서 생성이 실패해도 재시도하지 않는다.
출력 디렉터리를 바꿔도 같은 벤치마크의 재평가는 거부한다. 기존 출력 디렉터리는 비어 있어도
재사용하지 않으며 모든 JSON은 배타적 생성 모드로 쓴다. 검증 또는 기존 출력 경로 검사에서
거부되어 아직 마커가 없다면 입력을 열지 않은 상태다.

final은 실행 즉시 노출된 것으로 취급한다. 목표 미달 보고서는 `final_exposed: true` 및
새 untouched reserve를 사용하는 v3 후속 지시를 보존한다. 실패한 final을 수정한 엔진으로
재평가하지 않는다. 기존 보고서는 개발 증거로 사용할 수 있으나 새로운 독립 성과는 새로운
벤치마크 버전에서만 주장한다. Git에 올리는 결과에는 집계 지표와 ID/해시만 포함하고
홀드아웃 리뷰 원문을 출력하지 않는다.

v1 final 36.20%, M development 49.85%, 향후 M2 development/selection/final은 서로 구분한다.
별점은 감성의 잡음 있는 대리값이며, 풍자·측면별 감정·문맥에는 규칙 기반 방법의 한계가 남는다.

## Phase 1 검증

`python -m pytest -q tests/benchmark_v2`로 데이터·동결·선택·최종 평가 계약을 검증하고,
`python -m pytest -q`로 기존 감성·추출·CLI·v1 회귀를 함께 검증한다.
테스트 데이터는 임시 디렉터리의 인공 입력이며 실제 reserve/selection/final을 사용하지 않는다.
M2 수집·사전·실측 보고서는 후속 단계에서 별도 검토한다.
