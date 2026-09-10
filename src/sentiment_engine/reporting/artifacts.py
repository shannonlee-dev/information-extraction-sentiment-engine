"""분석은 실행별로 보관하고 평가는 종류별 최신 결과를 저장한다."""
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkdtemp

from .comparison import save_comparison_csv
from .summary import summary_markdown


def save_artifacts(result: dict, output_dir: Path, *, evaluation: bool) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    if evaluation:
        mode = 'all' if 'extraction' in result and 'sentiment' in result else (
            'sentiment' if 'sentiment' in result else 'extraction'
        )
        directory = (output_dir / 'evaluation' / mode).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        # 재생성 실패 시 이전 그래프가 최신 결과처럼 남지 않게 한다.
        (directory / 'comparison.png').unlink(missing_ok=True)
    else:
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        directory = Path(mkdtemp(prefix=f'analysis-{timestamp}-', dir=output_dir)).resolve()
    (directory / 'result.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )
    summary = directory / 'summary.md'
    summary.write_text(summary_markdown(result, evaluation=evaluation), encoding='utf-8')
    if evaluation and 'sentiment' in result:
        from .charts import save_comparison_charts

        comparison = result['sentiment']
        save_comparison_csv(comparison, directory / 'comparison.csv')
        save_comparison_charts(comparison, directory)
        summary.write_text(summary_markdown(result, evaluation=True, chart=True), encoding='utf-8')
    return directory
