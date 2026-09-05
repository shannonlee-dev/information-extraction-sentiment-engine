#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv-eval/bin/python ]]; then
    python3 -m venv .venv-eval
fi
.venv-eval/bin/python -m pip install --require-hashes -r requirements-eval.lock
.venv-eval/bin/python -m pip check
exec .venv-eval/bin/python -m scripts.run_sentiment_benchmark "$@"
