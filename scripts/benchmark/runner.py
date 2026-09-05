"""Controller for gold-free, isolated candidate prediction workers."""

from __future__ import annotations

import json
import selectors
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.benchmark.artifacts import verify_manifest


def validate_input_record(record: dict[str, Any]) -> dict[str, str]:
    if not isinstance(record, dict) or set(record) != {"id", "text"}:
        raise ValueError("worker inputs must contain only id/text")
    if not isinstance(record["id"], str) or not record["id"] or not isinstance(record["text"], str):
        raise ValueError("worker inputs require nonempty id/text strings")
    return {"id": record["id"], "text": record["text"]}


def _readline(process: subprocess.Popen[str], timeout: float) -> str | None:
    if process.stdout is None:
        return None
    selector = selectors.DefaultSelector()
    try:
        selector.register(process.stdout, selectors.EVENT_READ)
        if not selector.select(timeout):
            return None
        return process.stdout.readline()
    finally:
        selector.close()


def _stop(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.kill()
    process.wait(timeout=5)


def _worker_command(manifest: Path, modifiers: bool) -> list[str]:
    script = Path(__file__).resolve().parents[1] / "predict_sentiment_benchmark.py"
    return [sys.executable, "-s", str(script), "--candidate-manifest", str(manifest),
            "--modifiers", "on" if modifiers else "off"]


def _start_worker(manifest: Path, modifiers: bool) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        _worker_command(manifest, modifiers),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        cwd=str(Path(__file__).resolve().parents[2]),
        bufsize=1,
    )
    ready = _readline(process, 120.0)
    if ready is None:
        _stop(process)
        raise RuntimeError("worker initialization timeout")
    try:
        message = json.loads(ready)
    except json.JSONDecodeError as error:
        _stop(process)
        raise RuntimeError("worker initialization returned invalid JSON") from error
    if message != {"type": "ready"}:
        _stop(process)
        raise RuntimeError("worker initialization failed")
    return process


def _error_prediction(record_id: str, error_type: str) -> dict[str, Any]:
    return {"id": record_id, "predicted": "analysis_error", "score": None,
            "match_count": 0, "neutral_reason": None, "error_type": error_type}


def run_predictions(inputs: Path, candidate_manifest: Path, output: Path, *, modifiers: bool) -> dict[str, Any]:
    """Run every input exactly once, isolating candidate imports in a worker."""
    verify_manifest(candidate_manifest)
    records = []
    for line_number, line in enumerate(Path(inputs).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(validate_input_record(json.loads(line)))
        except (json.JSONDecodeError, ValueError, TypeError) as error:
            raise ValueError(f"invalid input line {line_number}: {error}") from error
    if not records:
        raise ValueError("prediction input must not be empty")
    if len({record["id"] for record in records}) != len(records):
        raise ValueError("prediction input IDs must be unique")

    process: subprocess.Popen[str] | None = None
    predictions: list[dict[str, Any]] = []
    error_counts: Counter[str] = Counter()
    try:
        process = _start_worker(Path(candidate_manifest), modifiers)
        for record in records:
            if process.stdin is None:
                raise RuntimeError("worker stdin unavailable")
            process.stdin.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            process.stdin.flush()
            line = _readline(process, 10.0)
            if line is None:
                prediction = _error_prediction(record["id"], "timeout")
                error_counts["timeout"] += 1
                _stop(process)
                process = _start_worker(Path(candidate_manifest), modifiers)
            else:
                try:
                    prediction = json.loads(line)
                    if not isinstance(prediction, dict) or prediction.get("id") != record["id"]:
                        raise ValueError("response ID mismatch")
                    allowed = {"id", "predicted", "score", "match_count", "neutral_reason", "error_type"}
                    if set(prediction) != allowed:
                        raise ValueError("response shape mismatch")
                    if prediction["predicted"] not in {"positive", "negative", "neutral", "analysis_error"}:
                        raise ValueError("response label invalid")
                    if prediction["error_type"] is not None:
                        error_counts[prediction["error_type"]] += 1
                except (json.JSONDecodeError, ValueError, TypeError):
                    prediction = _error_prediction(record["id"], "invalid_prediction")
                    error_counts["invalid_prediction"] += 1
            predictions.append(prediction)
    finally:
        _stop(process)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in predictions), encoding="utf-8")
    return {"n": len(predictions), "error_counts": dict(error_counts), "output": str(output)}
