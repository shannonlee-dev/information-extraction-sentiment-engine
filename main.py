"""한 문장을 분석하거나, 미션 평가 데이터 전체를 실행한다."""

import sys
from pathlib import Path

# 패키지를 설치하지 않아도 이 저장소의 소스로 실행한다.
source_directory = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(source_directory))

from sentiment_engine.cli import main

if __name__ == "__main__":
    main()
