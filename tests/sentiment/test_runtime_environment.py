"""Environment failures stay explicit and the probe exercises the adapter."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import probe_komoran
from sentiment_engine import korean
from sentiment_engine.models import MorphologyAdjustment, MorphToken


def test_probe_uses_adapter_offsets_and_adjustments(monkeypatch):
    monkeypatch.setattr(probe_komoran, "analyze_morphology_with_trace", lambda text: (
        (MorphToken("🙂", "SW", 0, 1, 0), MorphToken("좋", "VA", 2, 3, 1)),
        (MorphologyAdjustment("surrogate_pair", 0, 1),),
    ))
    result = probe_komoran._analyze_case("emoji", "🙂 좋다", (("좋", "VA", 2, 3),))
    assert result["passed"]
    assert result["tokens"][1]["python_span"] == [2, 3]
    assert result["adjustments"] == [{"kind": "surrogate_pair", "start": 0, "end": 1}]


def test_missing_dependencies_give_install_diagnostic():
    # -S excludes installed dependencies, while PYTHONPATH exposes the checkout.
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-S", "-c",
         "from sentiment_engine.korean import analyze_morphology; analyze_morphology('좋다')"],
        env={**os.environ, "PYTHONPATH": str(root / "src")},
        capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0
    assert "MorphologyError" in result.stderr
    assert "requirements-runtime.lock" in result.stderr
    assert "JDK 17" in result.stderr


def test_missing_jvm_gives_actionable_value_error(monkeypatch):
    from konlpy import tag

    def missing_jvm(**kwargs):
        raise OSError("JVM shared library unavailable")

    monkeypatch.setattr(tag, "Komoran", missing_jvm)
    korean._get_backend.cache_clear()
    try:
        with pytest.raises(korean.MorphologyError, match="JDK 17.*JAVA_HOME") as error:
            korean._get_backend()
        assert isinstance(error.value, ValueError)
        assert isinstance(error.value.__cause__, OSError)
    finally:
        korean._get_backend.cache_clear()
