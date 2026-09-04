from sentiment_engine.extraction import extract_information
from sentiment_engine.models import AnalysisResult
from sentiment_engine.sentiment import analyze_sentiment


def analyze(text: str) -> AnalysisResult:
    """Run information extraction and sentiment analysis for one text."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text.strip():
        raise ValueError("text must not be blank")

    extraction_result = extract_information(text)
    sentiment_result = analyze_sentiment(text)
    return AnalysisResult(
        text=text,
        extractions=extraction_result.items,
        sentiment=sentiment_result,
        diagnostics=extraction_result.diagnostics,
    )


__all__ = ["analyze", "analyze_sentiment", "extract_information"]
