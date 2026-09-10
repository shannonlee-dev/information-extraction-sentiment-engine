# Responsibility-based Modularization Implementation Plan

**Goal:** Separate extraction, sentiment, and evaluation responsibilities while preserving existing public calls and serialized output.

**Architecture:** Convert the three mixed-responsibility modules to packages with explicit public exports. Keep each extraction rule with its validation and normalization; separate sentiment tokenization, lexicon matching, modifier rules, and orchestration. Separate evaluation dataset loading, shared metrics, and domain evaluators. Retain the small CLI, analysis facade, and result models.

**Tech Stack:** Python >=3.10, standard library, pytest >=8,<9.

**Spec:** User request to modularize the project and reduce responsibilities per file.

## Constraints

- Preserve `sentiment_engine` exports and the public functions imported from extraction, sentiment, and evaluation.
- Preserve rules, score arithmetic, diagnostics, output ordering, fixture data, and CLI JSON.
- Preserve repository-relative resource resolution after moving modules into packages.
- No new runtime dependencies.

## Tasks

- [x] Capture complete analysis output for all 165 fixture sentences and full CLI evaluation before editing; establish existing test baseline.
- [x] Create extraction/{email,phone,date,money,url}.py with each existing regex and its corresponding functions. Put validation, dispatch, and sorting in extraction/pipeline.py and export extract_information from __init__.py.
- [x] Create sentiment/tokenization.py, lexicon.py, modifiers.py, and analyzer.py. Keep longest-first matching and dictionary collision order in lexicon; keep emphasis and negation in modifiers; export analyze_sentiment from __init__.py.
- [x] Create evaluation/datasets.py, metrics.py, extraction.py, and sentiment.py. Export existing public evaluation and dataset functions from __init__.py. Adjust resource paths to the new depth.
- [x] Separate CLI tests from evaluation tests; add focused coverage for extraction ordering/diagnostics, longest expression matching, modifier boundaries, and public input validation.
- [x] Update README architecture and extension guidance; run full pytest, compare pre/post fixture analyses and CLI evaluation JSON, and inspect diff for unintended behavior changes.

## Verification results

- Baseline: 104 tests passed. Final: 123 tests passed with `PYTHONPATH="$PWD/src" .venv/bin/python -m pytest -q`.
- Complete serialized analyses of all 165 fixture texts unchanged; CLI evaluation output byte-identical.
- Independent review: no actionable findings; 1,000 seeded mixed-input comparisons matched the original implementation, including both sentiment modifier modes.
- Documented public API imports preserved. Internal helpers and undocumented globals now reside in their owning modules.
