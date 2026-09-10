"""실행별 디렉터리에 JSON과 평가 보고서를 저장한다."""
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkdtemp

from .comparison import save_comparison_csv


def save_artifacts(result: dict, output_dir: Path, *, evaluation: bool) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    kind = 'evaluation' if evaluation else 'analysis'
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory = Path(mkdtemp(prefix=f'{kind}-{timestamp}-', dir=output_dir)).resolve()
    (directory / 'result.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )
    if evaluation and 'sentiment' in result:
        from .charts import save_comparison_charts

        comparison = result['sentiment']
        save_comparison_csv(comparison, directory / 'comparison.csv')
        save_comparison_charts(comparison, directory)
    return directory
