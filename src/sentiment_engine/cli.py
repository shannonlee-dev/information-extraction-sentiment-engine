"""Command-line interface for the integrated analysis API."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Sequence

from sentiment_engine import analyze
from sentiment_engine.models import AnalysisResult


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract structured information and analyze Korean sentiment."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--text", help="text to analyze")
    mode.add_argument(
        "--evaluate",
        choices=("extraction", "sentiment", "all"),
        help="run a Task 9 evaluation",
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def _print_text(result: AnalysisResult) -> None:
    print("Extractions:")
    for item in result.extractions:
        normalized = asdict(item)["normalized"]
        print(f"- {item.type}: {item.raw} -> {normalized}")

    print("Sentiment:")
    print(
        f"- label: {result.sentiment.label}, score: {result.sentiment.score}, "
        f"mixed: {result.sentiment.mixed}"
    )

    print("Diagnostics:")
    for diagnostic in result.diagnostics:
        print(f"- {diagnostic.type}: {diagnostic.raw} ({diagnostic.reason})")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its process exit code."""
    arguments = _parser().parse_args(argv)
    if arguments.evaluate is not None:
        print("evaluation support is not installed", file=sys.stderr)
        return 2
    if not arguments.text.strip():
        print("error: text must not be blank", file=sys.stderr)
        return 2

    try:
        result = analyze(arguments.text)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"analysis configuration error: {error}", file=sys.stderr)
        return 2

    if arguments.format == "json":
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        _print_text(result)
    return 0
