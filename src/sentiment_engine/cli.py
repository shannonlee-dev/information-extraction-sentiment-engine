"""Command-line interface for the integrated analysis API."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any, Sequence

from sentiment_engine import analyze
from sentiment_engine.evaluation import (
    compare_sentiment,
    evaluate_extraction,
    load_extraction_cases,
    load_sentiment_cases,
)
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
        help="run extraction and/or sentiment evaluation",
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


def _print_metrics(label: str, metrics: dict[str, Any]) -> None:
    print(
        f"- {label}: precision={metrics['precision']:.6f}, "
        f"recall={metrics['recall']:.6f}, f1={metrics['f1']:.6f} "
        f"(tp={metrics['tp']}, fp={metrics['fp']}, fn={metrics['fn']})"
    )


def _run_evaluation(mode: str, output_format: str) -> int:
    results = {}
    try:
        if mode in ("extraction", "all"):
            results["extraction"] = evaluate_extraction(load_extraction_cases())
        if mode in ("sentiment", "all"):
            results["sentiment"] = compare_sentiment(load_sentiment_cases())
    except (OSError, UnicodeError, ValueError) as error:
        print(f"evaluation configuration error: {error}", file=sys.stderr)
        return 2

    if output_format == "json":
        payload = results if mode == "all" else results[mode]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if "extraction" in results:
        extraction = results["extraction"]
        print("Extraction evaluation:")
        for kind, metrics in extraction["per_type"].items():
            _print_metrics(kind, metrics)
        _print_metrics("micro", extraction["micro"])
        print(f"- error entries: {len(extraction['errors'])}")
    if "sentiment" in results:
        sentiment = results["sentiment"]
        print("Sentiment evaluation:")
        for setting in ("without_modifiers", "with_modifiers"):
            metrics = sentiment[setting]
            print(f"{setting}:")
            print(f"- accuracy={metrics['accuracy']:.6f}, macro_f1={metrics['macro_f1']:.6f}, "
                  f"positive_f1={metrics['positive_f1']:.6f}")
            for label, values in metrics["per_class"].items():
                _print_metrics(label, values)
            print(f"- misclassified cases: {len(metrics['errors'])}")
        print("delta: " + ", ".join(f"{name}={value:+.6f}" for name, value in sentiment["delta"].items()))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return its process exit code."""
    arguments = _parser().parse_args(argv)
    if arguments.evaluate is not None:
        return _run_evaluation(arguments.evaluate, arguments.format)
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
