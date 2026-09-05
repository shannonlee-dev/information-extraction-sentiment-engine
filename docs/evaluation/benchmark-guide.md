# 외부 감성 평가 실행 안내

Ubuntu 터미널에서 아래 두 줄을 실행하면 환경 준비, 원본 확보, 노출 목록 생성,
중복 제거와 분할, 기존 엔진 개발평가, 동결 및 최종평가가 순서대로 실행됩니다.

```bash
cd /home/shannon/__dev/cody/information-extraction-sentiment-engine
bash scripts/run_benchmark.sh
```

Python 3.12와 venv 모듈을 사용해 검증합니다. Ubuntu에서 venv 생성 자체가
실패하면 시스템 관리자가 python3-venv를 설치해야 합니다. 현재 작업 환경에는
가상환경이 준비되어 있습니다. 첫 실행은 인터넷 연결이 필요합니다.

중복 인덱싱은 2만 건마다 진행 상황을 출력합니다. 환경과 데이터에 따라 몇 분
걸릴 수 있습니다. 마지막까지 성공해야 최종 평가가 완료된 것입니다.
이미 완료된 단계는 재사용합니다. 완료 후 같은 명령을 다시 실행해도 최종셋을
재채점하지 않고 저장된 결과 경로를 보여줍니다. 실패한 최종 시도의 기록도 남깁니다.

결과 파일:

- 개발 평가: artifacts/benchmark/v1/runs/development-baseline/report.json
- 최종 평가: artifacts/benchmark/v1/runs/final/report.json
- 데이터 개수·분할 해시: artifacts/benchmark/v1/manifest.json
- 고정된 코드·사전·평가 설정: artifacts/benchmark/v1/release.json

상세 결과와 목표 판정은 sentiment-results.md에 기록합니다.
기존 엔진이 후보 하나이므로 선택셋은 사용하지 않습니다. 수정어 켬/끔을 모두
측정하되 켬을 최종 후보로 미리 고정합니다.

노출 목록은 이미 본 문장의 명단입니다. 생성기가 기존 감성 fixture, 테스트의
한국어 문자열, 공개 문서의 인용 예문, 공식 원본 README의 미리보기를 모읍니다.
대화 등 자동으로 수집되지 않는 예문은 manual-exposures.jsonl에 기록합니다.
문자열 수집에는 누락·과잉 등록 가능성이 있으므로 완전한 열람 이력이라고
부르지 않습니다. private 문서는 자동 복제하지 않습니다.

분할 후에는 exposures.jsonl과 protocol.md의 사본이 benchmark 안에 동결됩니다.
최종 결과를 보고 사전·규칙을 고치려면 이번 최종셋은 다음 버전의 개발 자료로
취급하고, 다음 독립평가에는 개발에 쓰지 않은 새 표본이 필요합니다.
플랜 2 재설계는 이 명령에 포함되지 않습니다.

원본과 상세 실행 파일은 Git에서 제외합니다. 분할 입력 원문을 임의로 출력하지
말고, 결과 확정 이후 분석할 오류만 확인하세요.
