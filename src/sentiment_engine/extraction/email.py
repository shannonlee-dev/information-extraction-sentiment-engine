"""email 후보 탐색, 검증 및 정규화."""

import re

from sentiment_engine.models import Diagnostic, ExtractionItem

# 이메일: 영문/숫자와 흔한 특수문자를 포함한 로컬 부분, 점으로 나뉜 도메인.
# 연속된 점이나 잘못된 도메인은 후보 전체를 잡은 뒤 유효성 검사에서 거른다.
EMAIL_CANDIDATE_PATTERN = re.compile(
    r"""
    (?<![A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])  # 다른 이메일 토큰 중간에서 시작하지 않음
    (?P<local>[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+)
    @
    (?P<domain>[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]*)*)
    (?![A-Za-z0-9-])                      # 도메인 일부만 매칭하지 않음
    """,
    re.VERBOSE,
)


def extract_emails(text: str) -> tuple[list[ExtractionItem], list[Diagnostic]]:
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
    if len(labels) < 2:
        return "invalid_email_domain"
    for label in labels:
        if not label or label.startswith("-") or label.endswith("-"):
            return "invalid_email_domain"
    top_level_domain = labels[-1]
    if len(top_level_domain) < 2 or len(top_level_domain) > 63:
        return "invalid_email_domain"
    if not top_level_domain.isalpha():
        return "invalid_email_domain"
    return None
