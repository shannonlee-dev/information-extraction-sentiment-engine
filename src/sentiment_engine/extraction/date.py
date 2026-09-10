"""date 후보 탐색, 검증 및 정규화."""
import re
from datetime import date

from sentiment_engine.models import Diagnostic, ExtractionItem


DATE_CANDIDATE_PATTERNS = (
    # 한국어 연월일: 월/일은 한 자리 또는 두 자리이며 공백을 허용한다.
    re.compile(r"(?<!\d)(?P<year>\d{4})년\s*(?P<month>\d{1,2})월\s*(?P<day>\d{1,2})일(?!\d)"),
    # 슬래시 날짜: 이어지는 /숫자는 날짜의 일부를 잘라 추출하지 않도록 거부한다.
    re.compile(r"(?<!\d)(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})(?!\d|/\d)"),
    # 하이픈 날짜: 실제 달력에 있는 날짜인지는 date()로 검사한다.
    re.compile(r"(?<!\d)(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})(?!\d|-\d)"),
)


def extract_dates(text: str) -> tuple[list[ExtractionItem], list[Diagnostic]]:
    items: list[ExtractionItem] = []
    diagnostics: list[Diagnostic] = []
    for pattern in DATE_CANDIDATE_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group()
            try:
                normalized = date(
                    int(match["year"]), int(match["month"]), int(match["day"])
                ).isoformat()
            except ValueError:
                diagnostics.append(
                    Diagnostic("date", raw, match.start(), match.end(), "invalid_calendar_date")
                )
                continue
            items.append(ExtractionItem("date", raw, normalized, match.start(), match.end()))
    items.sort(key=lambda item: item.start)
    diagnostics.sort(key=lambda diagnostic: diagnostic.start)
    return items, diagnostics
