# 문서 안내

0.1.0의 현재 결과부터 읽고, 필요한 경우 개발 과정과 과거 baseline 기록을 확인한다.

## 현재 결과

| 문서 | 내용 |
|---|---|
| [M2 최종 결과](evaluation/engine-m2-final.md) | 동결 M2-L의 독립 final 성능, 신뢰구간, 한계 |
| [M2 개발 기록](evaluation/engine-m2-development.md) | 사전 확장, 개발 평가, 오류 감사와 폐기한 비교 결과 요약 |
| [평가 프로토콜 v2](evaluation/sentiment-protocol-v2.md) | 데이터 격리, 후보 동결, 일회성 final 계약 |

최종 판단의 기준은 `engine-m2-final.md`다. 개발셋 수치와 과거 v1 결과는 최종 성능으로
해석하지 않는다.

## 과거 baseline

| 문서 | 내용 |
|---|---|
| [재설계 개발 기록](evaluation/engine-development.md) | 기준 후보 M의 형태소·사전·문법 구현과 검증 |
| [v1 외부 평가 결과](evaluation/sentiment-results.md) | 재설계 이전 baseline의 외부 2,000건 결과 |
| [v1 평가 프로토콜](evaluation/sentiment-protocol.md) | 최초 외부 benchmark 계약 |
| [v1 실행 안내](evaluation/benchmark-guide.md) | 과거 baseline 평가 도구와 산출물 위치 |

## 기계 판독 기록

- `engine-m2-final-results.json`: 최종 지표, 신뢰구간, 해시
- `engine-m2-freeze.json`: 후보와 평가 코드 동결 정보
- `engine-m2-development-results.json`: M2 개발 단계별 측정값
- `engine-m2-error-audit.json`: 개발 오류 분류
- `engine-*.json`, `komoran-*.json`: 기준 후보의 환경·통합·프로파일 기록
- `exposure-register*.jsonl`, `manual-exposures*.jsonl`: 평가 전 노출 문장 등록부

JSON/JSONL의 로컬 절대경로와 과거 문서 위치는 실행 당시 provenance다. 현재 checkout의
실행 경로나 유효한 문서 링크로 해석하지 않는다. 동결 기록의 해시를 보존하기 위해
이 파일들은 후처리하지 않았다.

## 재현 범위

`scripts/benchmark/`는 v1, `scripts/benchmark_v2/`는 M2 평가 계약을 구현한다.
`artifacts/benchmark/`에는 원문·분할·예측 등 큰 생성물이 저장되며 Git에서 제외된다.
최종 holdout은 이미 소비됐으므로 같은 데이터로 0.1.0의 독립 final을 다시 실행하지 않는다.

완료된 구현 계획과 저장소 정리 보고서는 현행 문서에서 제거했으며 Git 이력에 남아 있다.
