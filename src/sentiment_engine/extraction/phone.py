"""phone 후보 탐색, 검증 및 정규화."""
import re

from sentiment_engine.models import Diagnostic, ExtractionItem


# 전화번호: 0으로 시작하며 하이픈, 공백, 구분자 없는 형식을 허용한다.
# 앞뒤 숫자 경계로 긴 숫자의 일부를 피하고, 지역번호와 자릿수는 아래에서 검사한다.
PHONE_CANDIDATE_PATTERN = re.compile(
    r"""
    (?<!\d)
    (?P<area>0\d{1,2})
    (?P<first_separator>[- ]?)
    (?P<exchange>\d{2,4})
    (?P<second_separator>[- ]?)
    (?P<subscriber>\d{4})
    (?!\d)
    """,
    re.VERBOSE,
)
AREA_CODES = (
    "010", "02", "031", "032", "033", "041", "042", "043", "044",
    "051", "052", "053", "054", "055", "061", "062", "063", "064",
)


def extract_phones(text: str) -> tuple[list[ExtractionItem], list[Diagnostic]]:
    items: list[ExtractionItem] = []
    diagnostics: list[Diagnostic] = []
    for match in PHONE_CANDIDATE_PATTERN.finditer(text):
        area = match["area"]
        exchange = match["exchange"]
        subscriber = match["subscriber"]
        first_separator = match["first_separator"]
        second_separator = match["second_separator"]
        raw = match.group()
        if not first_separator and not second_separator:
            area = next((code for code in AREA_CODES if raw.startswith(code)), area)
            exchange = raw[len(area) : -4]
            subscriber = raw[-4:]
        if area not in AREA_CODES:
            reason = "invalid_phone_prefix"
        elif len(exchange) not in (3, 4) or first_separator != second_separator:
            reason = "invalid_phone_format"
        else:
            items.append(
                ExtractionItem(
                    "phone", raw, f"{area}-{exchange}-{subscriber}", match.start(), match.end()
                )
            )
            continue
        diagnostics.append(Diagnostic("phone", raw, match.start(), match.end(), reason))
    return items, diagnostics
