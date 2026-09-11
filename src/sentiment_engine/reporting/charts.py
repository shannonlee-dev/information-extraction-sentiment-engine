"""GUI 없이 공유 가능한 PNG 성능 그래프를 생성한다."""

from pathlib import Path

from .comparison import DATA_NOTE, comparison_rows, sample_count


def save_comparison_charts(comparison: dict, directory: Path) -> None:
    # 텍스트 분석이나 터미널 전용 실행에는 그래프 라이브러리를 로딩하지 않는다.
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    rows = comparison_rows(comparison)
    figure = Figure(figsize=(9, 5.5), dpi=160, facecolor="white")
    FigureCanvasAgg(figure)
    axes = figure.subplots()
    positions = list(range(len(rows)))
    width = 0.32
    for column, offset, color, label in (
        (1, -width / 2, "#64748b", "Modifiers OFF"),
        (2, width / 2, "#2563eb", "Modifiers ON"),
    ):
        bar_positions = [position + offset for position in positions]
        values = [row[column] for row in rows]
        value_labels = [f"{value:.4f}" for value in values]
        bars = axes.bar(bar_positions, values, width, label=label, color=color)
        axes.bar_label(bars, labels=value_labels, padding=4)
    axes.set_xticks(positions, [row[0] for row in rows])
    axes.set_ylim(0, 1.12)
    axes.set_yticks([i / 5 for i in range(6)])
    axes.set_ylabel("Score (0–1)")
    axes.set_title(
        f"Sentiment performance — synthetic evaluation (n={sample_count(comparison)})",
        pad=18,
    )
    axes.set_axisbelow(True)
    axes.grid(axis="y", alpha=0.2)
    axes.spines[["top", "right"]].set_visible(False)
    axes.legend(loc="upper left", frameon=False)
    delta_labels = []
    for metric_label, off, on, delta in rows:
        delta_labels.append(f"{metric_label} delta: {delta:+.6f}")
    deltas = "   |   ".join(delta_labels)
    figure.text(0.5, 0.09, deltas, ha="center", fontsize=10)
    figure.text(0.5, 0.04, DATA_NOTE, ha="center", fontsize=9, color="#475569")
    figure.subplots_adjust(left=0.1, right=0.97, top=0.86, bottom=0.22)
    figure.savefig(directory / "comparison.png")
