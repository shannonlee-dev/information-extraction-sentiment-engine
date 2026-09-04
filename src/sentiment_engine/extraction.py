import re

from sentiment_engine.models import Diagnostic, ExtractionItem


EMAIL_CANDIDATE_PATTERN = re.compile(
    r"""
    (?<![A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])
    (?P<local>
        # The local part permits common RFC-style atom characters; semantic checks reject bad dots.
        [A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+
    )
    @
    (?P<domain>
        # Repeated dotted domain labels are captured broadly for semantic label validation.
        [A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*
    )
    # The terminal domain must be a 2--63 character alphabetic label during validation.
    (?![A-Za-z0-9-])
    """,
    re.VERBOSE,
)

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


def _extract_emails(text: str) -> tuple[list[ExtractionItem], list[Diagnostic]]:
    items: list[ExtractionItem] = []
    diagnostics: list[Diagnostic] = []
    for match in EMAIL_CANDIDATE_PATTERN.finditer(text):
        local = match["local"]
        domain = match["domain"]
        raw = match.group()
        reason = _invalid_email_reason(local, domain)
        if reason:
            diagnostics.append(Diagnostic("email", raw, match.start(), match.end(), reason))
            continue
        items.append(
            ExtractionItem(
                "email", raw, f"{local}@{domain.lower()}", match.start(), match.end()
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
