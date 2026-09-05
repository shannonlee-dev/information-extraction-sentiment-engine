"""Gold-free worker process used by the benchmark runner."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# This helper is intentionally loaded from the repository; only the candidate
# engine itself is imported from the immutable snapshot below.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.benchmark.artifacts import verify_manifest


def _load_engine(manifest_path: Path):
    verified = verify_manifest(manifest_path)
    root = Path(verified["manifest"]["snapshot_root"]).resolve()
    source = (root / "src").resolve()
    if not source.is_dir():
        raise RuntimeError("candidate src directory missing")
    sys.path[:] = [str(source)] + [entry for entry in sys.path if Path(entry or ".").resolve() not in {source, root}]
    import sentiment_engine

    module_path = Path(sentiment_engine.__file__).resolve()
    if source not in module_path.parents:
        raise RuntimeError("candidate import escaped snapshot")
    return sentiment_engine.analyze_sentiment


def _neutral_reason(result) -> str | None:
    if result.label != "neutral":
        return None
    if not result.matches:
        return "no_match"
    signs = {match.contribution > 0 for match in result.matches if match.contribution != 0}
    return "cancellation" if signs == {True, False} or result.score == 0 else "other_zero"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-manifest", required=True, type=Path)
    parser.add_argument("--modifiers", choices=("on", "off"), required=True)
    arguments = parser.parse_args(argv)
    try:
        analyze_sentiment = _load_engine(arguments.candidate_manifest)
    except Exception:
        print(json.dumps({"type": "error", "error_type": "initialization_error"}), flush=True)
        return 1
    print(json.dumps({"type": "ready"}), flush=True)
    for line in sys.stdin:
        try:
            record = json.loads(line)
            if not isinstance(record, dict) or set(record) != {"id", "text"}:
                raise ValueError("worker input must contain only id/text")
            result = analyze_sentiment(record["text"], apply_modifiers=arguments.modifiers == "on")
            if not math.isfinite(result.score):
                raise ValueError("non-finite score")
            print(json.dumps({
                "id": record["id"],
                "predicted": result.label,
                "score": result.score,
                "match_count": len(result.matches),
                "neutral_reason": _neutral_reason(result),
                "error_type": None,
            }, ensure_ascii=False, separators=(",", ":")), flush=True)
        except Exception:
            record_id = record.get("id") if isinstance(record, dict) and isinstance(record.get("id"), str) else ""
            print(json.dumps({
                "id": record_id,
                "predicted": "analysis_error",
                "score": None,
                "match_count": 0,
                "neutral_reason": None,
                "error_type": "analysis_error",
            }), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
