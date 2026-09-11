"""추출 입력 검증, 유형별 실행 및 결과 정렬."""

from sentiment_engine.models import Diagnostic, ExtractionItem, ExtractionResult

from .email import extract_emails
from .phone import extract_phones
from .date import extract_dates
from .money import extract_money
from .url import extract_urls


def _source_position(item: ExtractionItem | Diagnostic) -> tuple[int, int, str]:
    return item.start, item.end, item.type


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
    items = []
    diagnostics = []
    for extracted_items, extracted_diagnostics in extracted:
        items.extend(extracted_items)
        diagnostics.extend(extracted_diagnostics)
    sorted_items = sorted(items, key=_source_position)
    sorted_diagnostics = sorted(diagnostics, key=_source_position)
    return ExtractionResult(items=sorted_items, diagnostics=sorted_diagnostics)
