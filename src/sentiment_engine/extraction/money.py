"""money 후보 탐색, 검증 및 정규화."""
import re

from sentiment_engine.models import Diagnostic, ExtractionItem, MoneyValue


# 달러 금액: $ 뒤 숫자와 쉼표를 잡는다. 소수까지 후보에 포함하되 정수 검사에서 거부한다.
USD_CANDIDATE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])\$(?P<number>\d[\d,]*(?:\.\d[\d,]*)?)(?![\d,]|\.\d)"
)
# 원화: 숫자와 억/천만/만/천 조합 뒤에 '원'이 붙는 형식. 예: 1억 2천만원.
KRW_CANDIDATE_PATTERN = re.compile(
    r"(?<![\d,])(?P<body>\d[\d,]*(?:\s*(?:억|천만|만|천)\s*\d[\d,]*)*(?:\s*(?:억|천만|만|천)\s*)?)원(?![A-Za-z0-9_])"
)
# 원화 후보를 숫자와 단위로 순서대로 분해한다. 단위의 내림차순 여부도 검사한다.
MONEY_TOKEN_PATTERN = re.compile(r"(?P<number>\d[\d,]*)(?:\s*(?P<unit>억|천만|만|천))?\s*")
# 정수는 쉼표 없는 숫자 또는 세 자리씩 쉼표로 나눈 숫자만 허용한다.
INTEGER_PATTERN = re.compile(r"(?:\d+|\d{1,3}(?:,\d{3})+)")
UNIT_VALUES = {"억": 100_000_000, "천만": 10_000_000, "만": 10_000, "천": 1_000}


def extract_money(text: str) -> tuple[list[ExtractionItem], list[Diagnostic]]:
    items: list[ExtractionItem] = []
    diagnostics: list[Diagnostic] = []
    for match in USD_CANDIDATE_PATTERN.finditer(text):
        raw = match.group()
        number = match["number"]
        if not INTEGER_PATTERN.fullmatch(number):
            diagnostics.append(
                Diagnostic("money", raw, match.start(), match.end(), "invalid_money_number")
            )
            continue
        items.append(
            ExtractionItem("money", raw, MoneyValue(int(number.replace(",", "")), "USD"), match.start(), match.end())
        )
    for match in KRW_CANDIDATE_PATTERN.finditer(text):
        raw = match.group()
        value, reason = _parse_krw_amount(match["body"])
        if reason:
            diagnostics.append(Diagnostic("money", raw, match.start(), match.end(), reason))
            continue
        items.append(ExtractionItem("money", raw, MoneyValue(value, "KRW"), match.start(), match.end()))
    items.sort(key=lambda item: item.start)
    diagnostics.sort(key=lambda diagnostic: diagnostic.start)
    return items, diagnostics



def _parse_krw_amount(body: str) -> tuple[int, str | None]:
    total = 0
    previous_multiplier = float("inf")
    position = 0
    while position < len(body):
        match = MONEY_TOKEN_PATTERN.match(body, position)
        if not match:
            return 0, "invalid_money_number"
        number = match["number"]
        unit = match["unit"]
        if not INTEGER_PATTERN.fullmatch(number):
            return 0, "invalid_money_number"
        coefficient = int(number.replace(",", ""))
        if unit is None:
            if body[match.end() :].strip():
                return 0, "invalid_money_number"
            total += coefficient
        else:
            multiplier = UNIT_VALUES[unit]
            if multiplier >= previous_multiplier:
                return 0, "invalid_money_unit_order"
            total += coefficient * multiplier
            previous_multiplier = multiplier
        position = match.end()
    return total, None
