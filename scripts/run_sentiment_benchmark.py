"""Resume source preparation, baseline evaluation and one frozen final run."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen

from scripts.benchmark.release import verify_benchmark, verify_release

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "62f3097b6c6974cecda5571f2cd2b64aa3b7f01e"


def _run(module, *args):
    print(f"Running {module}", flush=True)
    subprocess.run([sys.executable, "-m", module, *map(str, args)], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", type=Path, default=ROOT / "artifacts/benchmark/v1")
    args = parser.parse_args()
    benchmark = args.benchmark.resolve()
    raw = benchmark / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    source, source_manifest, readme = raw / "naver_shopping.txt", benchmark / "source.json", raw / "source-readme.md"
    if not source_manifest.exists():
        if source.exists():
            raise ValueError("existing source lacks provenance; refusing to assign an invented origin")
        url = f"https://raw.githubusercontent.com/bab2min/corpus/{SOURCE_COMMIT}/sentiment/naver_shopping.txt"
        with urlopen(url, timeout=60) as response:
            content = response.read()
        source.write_bytes(content)
        source_manifest.write_text(json.dumps({
            "source_url": f"https://github.com/bab2min/corpus/blob/{SOURCE_COMMIT}/sentiment/naver_shopping.txt",
            "commit_sha": SOURCE_COMMIT, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content),
        }, indent=2) + "\n")
    provenance = json.loads(source_manifest.read_text())
    if hashlib.sha256(source.read_bytes()).hexdigest() != provenance["sha256"]:
        raise ValueError("source bytes differ from source manifest")
    if not readme.exists():
        commit = provenance["commit_sha"]
        with urlopen(f"https://raw.githubusercontent.com/bab2min/corpus/{commit}/sentiment/README.md", timeout=60) as response:
            readme.write_bytes(response.read())
    if not (benchmark / "manifest.json").exists():
        _run("scripts.build_exposure_register", "--root", ROOT, "--source-readme", readme)
        _run("scripts.prepare_sentiment_benchmark", "--source", source, "--source-manifest", source_manifest,
             "--protocol", ROOT / "docs/evaluation/sentiment-protocol.md",
             "--exposures", ROOT / "docs/evaluation/exposure-register.jsonl", "--output", benchmark, "--seed", "20260905")
    verify_benchmark(benchmark)
    baseline = benchmark / "baseline.json"
    if not baseline.exists():
        _run("scripts.benchmark.artifacts", "snapshot", "--root", ROOT, "--output", benchmark / "baseline")
    development = benchmark / "runs/development-baseline"
    if not (development / "report.json").exists():
        _run("scripts.evaluate_sentiment_benchmark", "--benchmark", benchmark, "--split", "development",
             "--candidate-manifest", baseline, "--modifiers", "both", "--output", development)
    release = benchmark / "release.json"
    if not release.exists():
        _run("scripts.benchmark.release", "--benchmark", benchmark, "--candidate-manifest", baseline, "--output", release)
    verify_release(release, benchmark)
    final = benchmark / "runs/final"
    if (final / "report.json").exists():
        print(f"Final already complete; existing result: {final / 'report.json'}", flush=True)
    elif (benchmark / "final-attempt.json").exists():
        raise ValueError("an interrupted final attempt exists; inspect it before making any new independent claim")
    else:
        _run("scripts.evaluate_sentiment_benchmark", "--benchmark", benchmark, "--split", "final",
             "--release-manifest", release, "--output", final)
    print(json.dumps({"development": str(development / "report.json"), "final": str(final / "report.json")}, indent=2))


if __name__ == "__main__":
    main()
