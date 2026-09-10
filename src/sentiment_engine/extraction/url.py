"""url 후보 탐색, 검증 및 정규화."""
import re
from urllib.parse import urlsplit, urlunsplit

from sentiment_engine.models import Diagnostic, ExtractionItem


# URL: HTTP(S)부터 공백 전까지 후보로 잡는다. 끝 문장부호를 정리한 뒤 호스트를 검사한다.
URL_CANDIDATE_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


def extract_urls(text: str) -> tuple[list[ExtractionItem], list[Diagnostic]]:
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
