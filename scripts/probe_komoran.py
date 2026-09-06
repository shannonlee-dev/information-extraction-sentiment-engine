"""Qualify the production KOMORAN adapter against the amended B1 contract.

Run in a separate environment: python -m scripts.probe_komoran --output report.json.
Exit 0 means all source-position checks passed, 1 means ineligible, 2 means the
environment could not initialize. Source restoration is owned by korean.py.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import platform
import re
import resource
import sys
import time
from pathlib import Path

from sentiment_engine.korean import (
    _get_backend,
    analyze_morphology_with_trace,
    analyzer_fingerprint,
    utf16_boundaries,
)


def inspect_tokens(text: str, records: list[dict], *, expected=()) -> dict:
    """Check source UTF-16 offsets against untouched text, including raw fixtures."""
    boundaries = utf16_boundaries(text)
    eojeols = list(re.finditer(r"\S+", text))
    tokens, violations = [], []
    if text.strip() and not records:
        violations.append({"kind": "empty_analysis"})
    for index, record in enumerate(records):
        token = {**record, "python_span": None, "source": None, "eojeol_index": None}
        begin, end = record["begin"], record["end"]
        if begin not in boundaries or end not in boundaries:
            violations.append({"kind": "utf16_boundary", "token_index": index})
        elif begin >= end:
            violations.append({"kind": "nonpositive_span", "token_index": index})
        else:
            start, stop = boundaries[begin], boundaries[end]
            token.update(python_span=[start, stop], source=text[start:stop])
            owners = [i for i, word in enumerate(eojeols)
                      if word.start() <= start < word.end()]
            if len(owners) != 1 or not any(word.start() < stop <= word.end() for word in eojeols):
                violations.append({"kind": "eojeol_boundary", "token_index": index})
            else:
                token["eojeol_index"] = owners[0]
        if record["morph"] is None:
            violations.append({"kind": "morph_decode_error", "token_index": index})
        tokens.append(token)
    # Exact spans are independent expectations, not assertions that a morph
    # must equal its source (contractions legitimately share syllables).
    for key in sorted({(morph, pos) for morph, pos, _, _ in expected}):
        wanted = [[start, end] for morph, pos, start, end in expected if (morph, pos) == key]
        actual = [t["python_span"] for t in tokens if (t["morph"], t["pos"]) == key]
        if actual != wanted:
            violations.append({"kind": "expected_spans", "key": list(key),
                               "expected": wanted, "actual": actual})
    return {"text": text, "tokens": tokens, "violations": violations, "passed": not violations}


CASES = (
    ("plain", "좋다", (("좋", "VA", 0, 1),)),
    ("repeated_spaces", "좋다  좋다", (("좋", "VA", 0, 1), ("좋", "VA", 4, 5))),
    ("leading_spaces", "  좋다", (("좋", "VA", 2, 3),)),
    ("past_polite", "친절했습니다", (("친절", "NNG", 0, 2), ("하", "XSV", 2, 3))),
    ("past", "좋았어요", (("좋", "VA", 0, 1),)),
    ("contraction", "했다", (("하", "VV", 0, 1), ("았", "EP", 0, 1))),
    ("irregular", "예뻤습니다", (("예쁘", "VA", 0, 2),)),
    ("honorific", "좋으셨습니다", (("좋", "VA", 0, 1),)),
    ("emoji", "🙂 좋다", (("좋", "VA", 2, 3),)),
    ("emoji_only", "🙂", ()),
    ("tab", "좋다\t좋다", (("좋", "VA", 0, 1), ("좋", "VA", 3, 4))),
    ("spaces_tab", "좋다  \t나쁘다", (("나쁘", "VA", 5, 7),)),
    ("crlf_blank_line", "좋다\r\n\r\n좋다", (("좋", "VA", 0, 1), ("좋", "VA", 6, 7))),
    ("lf", "좋다\n좋다", (("좋", "VA", 0, 1), ("좋", "VA", 3, 4))),
    ("empty", "", ()),
    ("whitespace", "  \t\r\n", ()),
)


def _analyze_case(name: str, text: str, expected) -> dict:
    records, errors, adjustments = [], [], ()
    try:
        tokens, adjustments = analyze_morphology_with_trace(text)
        python_to_java = {p: j for j, p in utf16_boundaries(text).items()}
        for token in tokens:
            records.append({"morph": token.morph, "pos": token.pos,
                            "begin": python_to_java[token.start],
                            "end": python_to_java[token.end],
                            "adapter_eojeol_index": token.eojeol_index})
    except Exception as error:
        errors.append({"kind": "analyzer_error", "error_type": type(error).__name__,
                       "message": str(error)})
    result = inspect_tokens(text, records, expected=expected)
    for index, token in enumerate(result["tokens"]):
        if token["eojeol_index"] != token["adapter_eojeol_index"]:
            errors.append({"kind": "adapter_eojeol_index", "token_index": index})
    result["violations"].extend(errors)
    result.update(name=name, passed=not result["violations"],
                  adjustments=[asdict(adjustment) for adjustment in adjustments])
    return result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe() -> dict:
    import jpype

    if jpype.isJVMStarted():
        raise RuntimeError("Run the probe in a fresh process to measure JVM initialization")
    if importlib.metadata.version("konlpy") != "0.6.0":
        raise RuntimeError("B1 requires KoNLPy 0.6.0 and its bundled KOMORAN")
    started = time.perf_counter()
    analyze_morphology_with_trace.cache_clear()
    _get_backend()
    first = _analyze_case(*CASES[0])
    cold_seconds = time.perf_counter() - started
    fingerprint = analyzer_fingerprint()
    system = jpype.JClass("java.lang.System")
    runtime = jpype.JClass("java.lang.Runtime").getRuntime()
    java_home = Path(str(system.getProperty("java.home")))
    cases = [first, *[_analyze_case(*case) for case in CASES[1:]]]
    # Measure uncached adapter calls, including any incompatible inputs. These
    # are technical fixtures, not the development review length distribution.
    timings = []
    warm_cases = [case for case in CASES if case[1].strip()]
    for _ in range(10):
        for case in warm_cases:
            analyze_morphology_with_trace.cache_clear()
            start = time.perf_counter()
            _analyze_case(*case)
            timings.append(1000 * (time.perf_counter() - start))
    timings.sort()
    return {
        "schema_version": 2,
        "gate": "B1",
        "subject": "production_adapter",
        "token_offset_unit": "original_source_utf16",
        "status": "qualified" if all(c["passed"] for c in cases) else "ineligible",
        "environment": {
            "python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
            "packages": {name: importlib.metadata.version(name)
                         for name in ("konlpy", "JPype1", "numpy", "lxml", "packaging")},
            "java": {key: str(system.getProperty(key)) for key in
                     ("java.version", "java.vendor", "java.vm.name", "os.name", "os.arch")},
            "jdk_release_sha256": _sha256(java_home / "release"),
            "libjvm_sha256": _sha256(Path(jpype.getDefaultJVMPath())),
        },
        "artifacts": fingerprint["files"],
        "adapter": {key: value for key, value in fingerprint.items() if key != "files"},
        "measurements": {
            "cold_seconds": cold_seconds, "warm_calls": len(timings),
            "warm_subject": "adapter analysis and probe source-invariant checks",
            "warm_cache_policy": "clear analysis cache before each call; JVM remains warm",
            "warm_p50_ms": timings[(len(timings) - 1) // 2],
            "warm_p95_ms": timings[(95 * len(timings) + 99) // 100 - 1],
            "warm_input_codepoints": [len(case[1]) for case in warm_cases],
            "heap_max_bytes": int(runtime.maxMemory()),
            "heap_used_bytes": int(runtime.totalMemory() - runtime.freeMemory()),
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                              * (1 if sys.platform == "darwin" else 1024),
        },
        "cases": cases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args(argv)
    try:
        report = probe()
        code = 0 if report["status"] == "qualified" else 1
    except Exception as error:
        report = {"schema_version": 2, "gate": "B1", "status": "environment_error",
                  "error_type": type(error).__name__, "message": str(error),
                  "hint": "Install requirements-runtime.lock and set JAVA_HOME to JDK 17."}
        code = 2
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gate": "B1", "status": report["status"], "report": str(arguments.output)}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
