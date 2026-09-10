"""평가용 정답 데이터 경로와 로딩."""
import json

from sentiment_engine.data import EVALUATION

DEFAULT_EXTRACTION_CASES_PATH = EVALUATION.joinpath("extraction_cases.json")
DEFAULT_SENTIMENT_CASES_PATH = EVALUATION.joinpath("sentiment_cases.json")


def load_extraction_cases():
    return json.loads(DEFAULT_EXTRACTION_CASES_PATH.read_text(encoding="utf-8"))["cases"]


def load_sentiment_cases():
    return json.loads(DEFAULT_SENTIMENT_CASES_PATH.read_text(encoding="utf-8"))["cases"]
