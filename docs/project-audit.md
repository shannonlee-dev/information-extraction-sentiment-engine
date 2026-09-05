# 프로젝트 진단 및 정리

2026-09-05 기준. 실행 코드, 사전, 테스트, 평가 도구, 의존성, 문서와 Git 변경 내역을 확인했다.
정보 추출과 평가 기반은 재사용할 수 있지만, 감성 엔진은 외부 데이터에서 성능 목표에 미달한다.

## 진단

| 영역 | 확인 결과 | 판단 |
|---|---|---|
| 정보 추출 | 기본 합성 65문장 평가에서 micro Precision 1.0, Recall 0.904762, F1 0.95 | 지원 범위가 명확한 추출기로 유지. 실제 고객 분포의 성능은 미검증 |
| 감성 분석 | 외부 2,000건 Accuracy 36.2%, Macro F1 0.48596, 미매칭 1,169건 | 어휘·활용형·구어체 누락을 개발 분할에서 구분해야 함. 정리만으로 성능이 개선되지는 않음 |
| API·CLI·테스트 | 전체 pytest 272개 통과, 기본 CLI 평가 정상 종료 | 실행에 연결된 모듈과 회귀 fixture 유지 |
| 단일 후보 평가 | 데이터·스냅샷·release 검증과 완료된 실행 재개 정상 | 원본, 분할, 동결 코드, 노출 목록, 결과와 잠금 파일 유지 |
| 복수 후보 선택 | 선택 경로가 `format: 1` release를 만들지만 최종 검증은 `format: 2`만 허용 | 미사용 경로의 호환 결함. 후보 비교 도입 전에 수정 필요 |
| 설치·의존성 | 평가 가상환경의 `pip check` 통과. 분석기는 저장소 editable 설치를 전제로 함 | 독립 wheel 배포와 Python 3.10 실행은 이번에 검증하지 않음 |
| 문서 | 완료된 계획과 대체된 제안이 2,410행 남아 있었음 | 현행 README·프로토콜·결과·가이드로 통합하고 과거 문서는 Git 이력으로 보존 |

복수 후보 문제는 `scripts/evaluate_sentiment_benchmark.py`의 선택 결과 생성과
`scripts/benchmark/release.py`의 검증 조건을 대조해 확인했다. 선택 경로는 기존
`release.json`도 덮어쓸 수 있으므로 완료된 v1에서 실행하면 안 된다. v1은 이 경로를
사용하지 않았다. 기존 release가 평가 스크립트의 해시도 고정하므로 이번 정리에서는
동결 코드를 변경하지 않았다. 후속 변경은 평가 버전을 분리해 검증해야 한다.

## 정리 내역

- 삭제: 초기 구현 계획, 초기 설계 명세, 대체된 감성 일반화 제안, 완료된 외부 평가 구현 계획.
- 이동: 미실행 재설계 제안을 [sentiment-redesign-plan.md](sentiment-redesign-plan.md)로 옮기고 현재 상태와 평가 참조를 갱신.
- 보존: 삭제 후 자동 수집에서 빠지는 과거 노출 문장 61개를 `evaluation/manual-exposures.jsonl`에 이관. 동결 노출 목록 448건은 변경하지 않음.
- 제거: 저장소 작업 영역의 Python 캐시와 빈 작업 보조 디렉터리. 가상환경과 평가 산출물은 유지.
- 남은 로컬 파일: `.pytest_cache/` 일부는 `nobody` 소유 디렉터리의 삭제 권한이 없어 남았다. 관리자 삭제에는 암호가 필요했으며, Git에서는 이미 제외돼 있다.
- README 첫 부분에 실제 외부 성능과 진단 문서 연결을 추가.

삭제 문서와 기존 평가 작업 전체는 커밋 `db765d9`에서 복원할 수 있다. 노출 기록의
과거 경로·줄 번호는 당시 출처이며 현행 문서 링크가 아니다. `docs/private/`의 사용자
원본 자료와 `.agents/`, `.codex/` 설정은 유지했다.

## 검증

- `.venv-eval/bin/python -m pytest -q`: 272 passed, skip 0.
- `.venv-eval/bin/python main.py --evaluate all`: 추출·감성 합성 평가 정상 종료.
- `.venv-eval/bin/python -m scripts.run_sentiment_benchmark`: 동결본을 검증하고 기존 최종 보고서 경로 반환.
- `.venv-eval/bin/python -m pip check`, `bash -n scripts/run_benchmark.sh`, `git diff --check`: 통과.
- 정리 후 임시 노출 목록을 생성해 기존 448문장이 모두 남아 있는지 확인.
- v1 release, 최종 보고서, 동결 노출 목록의 정리 전후 SHA-256 일치 확인.

이번에는 완료된 최종 평가를 재채점하지 않았다. 다음 독립 성능 판정에는 새 표본과
중복·노출 검사가 필요하다. 측정 방법과 한계는 [평가 결과](evaluation/sentiment-results.md)에 있다.
