# Directory Layout Plan

Goal: organize code, bundled datasets, tests, and historical documentation by their actual consumers.

- Bundle runtime lexicons under `src/sentiment_engine/data/lexicons/` and evaluation gold data under `src/sentiment_engine/data/evaluation/`.
- Resolve data from the installed package and include JSON files in wheel distributions. Preserve public analyzer/evaluation imports and data contents.
- Keep extraction, sentiment, and evaluation packages grouped by domain; retain `main.py` as a compatible launcher and add the package module launcher.
- Group behavior tests under `tests/unit/` and command-line tests under `tests/integration/`.
- Archive the legacy report under `docs/archive/`; store implementation records under `docs/plans/`.
- Update README and dependency metadata. Verify the full test suite, unchanged evaluation output, and CLI analysis/evaluation from a wheel installed outside the repository.

## Results

- Completed all moves, package resource loading, distribution metadata, and documentation updates.
- 125 tests passed against the installed wheel, including both the existing script and package module entry points.
- A clean virtual environment outside the repository ran CLI analysis and evaluation using only the wheel.
- All 165 complete analysis results and the full evaluation JSON matched the pre-refactor baseline.
- CI now uses a regular package installation so tests exercise bundled resources.
