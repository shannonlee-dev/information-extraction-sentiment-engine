"""평가 결과를 수식어 OFF/ON 비교표로 표현한다."""

import csv
from pathlib import Path

METRICS = (("Accuracy", "accuracy"), ("Macro F1", "macro_f1"))
DATA_NOTE = "Project-authored synthetic data; not an independent real-world benchmark."


def comparison_rows(comparison: dict) -> list[tuple[str, float, float, float]]:
    rows = []
    for label, key in METRICS:
        off = comparison["without_modifiers"][key]
        on = comparison["with_modifiers"][key]
        delta = comparison["delta"][key]
        rows.append((label, off, on, delta))
    return rows


def sample_count(comparison: dict) -> int:
    confusion = comparison["with_modifiers"]["confusion_matrix"]
    total = 0
    for row in confusion.values():
        total += sum(row.values())
    return total


def comparison_table(comparison: dict) -> str:
    lines = [
        "# Sentiment modifier comparison",
        "",
        f"Samples: {sample_count(comparison)}. {DATA_NOTE}",
        "",
        "| Metric | OFF | ON | Delta (ON - OFF) |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label, off, on, delta in comparison_rows(comparison):
        lines.append(f"| {label} | {off:.6f} | {on:.6f} | {delta:+.6f} |")
    lines += [
        "",
        "Scores use a 0–1 scale; an accuracy delta of +0.18 is +18 percentage points.",
        "Macro F1 averages classes present in the gold labels.",
        "ON enables both emphasis and negation; OFF disables both.",
    ]
    return "\n".join(lines) + "\n"


def save_comparison_csv(comparison: dict, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("metric", "off", "on", "delta"))
        for label, off, on, delta in comparison_rows(comparison):
            writer.writerow((label, f"{off:.6f}", f"{on:.6f}", f"{delta:.6f}"))
