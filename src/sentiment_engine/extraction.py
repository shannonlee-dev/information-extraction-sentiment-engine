import re
from datetime import date
from urllib.parse import urlsplit, urlunsplit

from sentiment_engine.models import Diagnostic, ExtractionItem, ExtractionResult, MoneyValue


EMAIL_CANDIDATE_PATTERN = re.compile(
    r"""
    # The left lookbehind prevents matching from the middle of a larger email-like token.
    (?<![A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])
    (?P<local>
        # The local part permits common RFC-style atom characters; semantic checks reject bad dots.
        [A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+
    )
    @
    (?P<domain>
        # Repeated dotted domain labels include empty labels so semantic validation can reject them.
        [A-Za-z0-9-]+(?:\.[A-Za-z0-9-]*)*
    )
    # The terminal domain must be a 2--63 character alphabetic label during validation.
    # The right lookahead prevents matching only a prefix of an alphanumeric or hyphenated label.
    (?![A-Za-z0-9-])
    """,
    re.VERBOSE,
)

PHONE_CANDIDATE_PATTERN = re.compile(
    r"""
    # These digit lookarounds prevent matching a phone number inside a longer digit sequence.
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

DATE_CANDIDATE_PATTERNS = (
    re.compile(r"(?<!\d)(?P<year>\d{4})년\s*(?P<month>\d{1,2})월\s*(?P<day>\d{1,2})일(?!\d)"),
    re.compile(r"(?<!\d)(?P<year>\d{4})/(?P<month>\d{1,2})/(?P<day>\d{1,2})(?!\d|/\d)"),
    re.compile(r"(?<!\d)(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})(?!\d|-\d)"),
)

USD_CANDIDATE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])\$(?P<number>\d[\d,]*(?:\.\d[\d,]*)?)(?![\d,]|\.\d)"
)
KRW_CANDIDATE_PATTERN = re.compile(
    r"(?<![\d,])(?P<body>\d[\d,]*(?:\s*(?:억|천만|만|천)\s*\d[\d,]*)*(?:\s*(?:억|천만|만|천)\s*)?)원(?![A-Za-z0-9_])"
)
MONEY_TOKEN_PATTERN = re.compile(r"(?P<number>\d[\d,]*)(?:\s*(?P<unit>억|천만|만|천))?\s*")
INTEGER_PATTERN = re.compile(r"(?:\d+|\d{1,3}(?:,\d{3})+)")
UNIT_VALUES = {
    "억": 100_000_000,
    "천만": 10_000_000,
    "만": 10_000,
    "천": 1_000,
}

URL_CANDIDATE_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


def _extract_emails(text: str) -> tuple[list[ExtractionItem], list[Diagnostic]]:
    items: list[ExtractionItem] = []
    diagnostics: list[Diagnostic] = []
    for match in EMAIL_CANDIDATE_PATTERN.finditer(text):
        local = match["local"]
        domain = match["domain"]
        raw = match.group()
        end = match.end()
        if domain.endswith(".") and not domain.endswith(".."):
            domain = domain[:-1]
            raw = raw[:-1]
            end -= 1
        reason = _invalid_email_reason(local, domain)
        if reason:
            diagnostics.append(Diagnostic("email", raw, match.start(), end, reason))
            continue
        items.append(
            ExtractionItem(
                "email", raw, f"{local}@{domain.lower()}", match.start(), end
            )
        )
    return items, diagnostics


def _invalid_email_reason(local: str, domain: str) -> str | None:
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return "invalid_email_local"
    labels = domain.split(".")
    if (
        len(labels) < 2
        or any(not label or label.startswith("-") or label.endswith("-") for label in labels)
        or not 2 <= len(labels[-1]) <= 63
        or not labels[-1].isalpha()
    ):
        return "invalid_email_domain"
    return None


def _extract_dates(text: str) -> tuple[list[ExtractionItem], list[Diagnostic]]:
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


def _extract_money(text: str) -> tuple[list[ExtractionItem], list[Diagnostic]]:
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


def _extract_phones(text: str) -> tuple[list[ExtractionItem], list[Diagnostic]]:
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


def _extract_urls(text: str) -> tuple[list[ExtractionItem], list[Diagnostic]]:
    items: list[ExtractionItem] = []
    diagnostics: list[Diagnostic] = []
    for match in URL_CANDIDATE_PATTERN.finditer(text):
        raw = _trim_url_candidate(match.group())
        if not raw:
            continue
        try:
            parsed = urlsplit(raw)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError:
            diagnostics.append(Diagnostic("url", raw, match.start(), match.start() + len(raw), "invalid_url"))
            continue
        if parsed.scheme.lower() not in {"http", "https"}:
            continue
        if not hostname:
            diagnostics.append(Diagnostic("url", raw, match.start(), match.start() + len(raw), "missing_url_host"))
            continue
        netloc = _normalized_netloc(parsed.netloc, hostname, port)
        normalized = urlunsplit(
            (parsed.scheme.lower(), netloc, parsed.path, parsed.query, parsed.fragment)
        )
        items.append(ExtractionItem("url", raw, normalized, match.start(), match.start() + len(raw)))
    return items, diagnostics


def _trim_url_candidate(candidate: str) -> str:
    while candidate:
        trimmed = candidate.rstrip(".,!?")
        if trimmed != candidate:
            candidate = trimmed
            continue
        closing = candidate[-1]
        pairs = {")": "(", "]": "[", "}": "{", ">": "<"}
        if closing in pairs and candidate.count(closing) > candidate.count(pairs[closing]):
            candidate = candidate[:-1]
            continue
        break
    return candidate


def _normalized_netloc(netloc: str, hostname: str, port: int | None) -> str:
    userinfo, separator, _ = netloc.rpartition("@")
    prefix = f"{userinfo}{separator}" if separator else ""
    normalized_host = f"[{hostname.lower()}]" if ":" in hostname else hostname.lower()
    if port is not None:
        return f"{prefix}{normalized_host}:{port}"
    return f"{prefix}{normalized_host}"


def extract_information(text: str) -> ExtractionResult:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text.strip():
        raise ValueError("text must not be blank")

    extracted = (
        _extract_emails(text),
        _extract_phones(text),
        _extract_dates(text),
        _extract_money(text),
        _extract_urls(text),
    )
    items = [item for extracted_items, _ in extracted for item in extracted_items]
    diagnostics = [diagnostic for _, extracted_diagnostics in extracted for diagnostic in extracted_diagnostics]
    unique_items = {(item.type, item.start, item.end): item for item in items}
    unique_diagnostics = {
        (diagnostic.type, diagnostic.start, diagnostic.end, diagnostic.reason): diagnostic
        for diagnostic in diagnostics
    }
    return ExtractionResult(
        items=sorted(unique_items.values(), key=lambda item: (item.start, item.end, item.type)),
        diagnostics=sorted(
            unique_diagnostics.values(),
            key=lambda diagnostic: (diagnostic.start, diagnostic.end, diagnostic.type),
        ),
    )
