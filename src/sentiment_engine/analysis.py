"""정보 추출과 감성 분석을 하나의 응답으로 제공한다."""
from sentiment_engine.extraction import extract_information
from sentiment_engine.sentiment import analyze_sentiment


def analyze_text(text: str) -> dict:
    return {
        'text': text,
        **extract_information(text).to_dict(),
        'sentiment': analyze_sentiment(text).to_dict(),
    }
