"""추출 입력 검증, 유형별 실행 및 결과 정렬."""
from sentiment_engine.models import ExtractionResult

from .email import extract_emails
from .phone import extract_phones
from .date import extract_dates
from .money import extract_money
from .url import extract_urls


def extract_information(text: str) -> ExtractionResult:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text.strip():
        raise ValueError("text must not be blank")

    extracted = (
        extract_emails(text),
        extract_phones(text),
        extract_dates(text),
        extract_money(text),
        extract_urls(text),
    )
    items = [item for extracted_items, _ in extracted for item in extracted_items]
    diagnostics = [diagnostic for _, extracted_diagnostics in extracted for diagnostic in extracted_diagnostics]
    return ExtractionResult(
        items=sorted(items, key=lambda item: (item.start, item.end, item.type)),
        diagnostics=sorted(diagnostics, key=lambda item: (item.start, item.end, item.type)),
    )
