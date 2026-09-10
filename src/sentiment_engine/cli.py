"""명령행 인자를 처리하고 분석·평가 결과를 JSON으로 출력한다."""
import argparse
import json
import sys
from pathlib import Path

from sentiment_engine.analysis import analyze_text
from sentiment_engine.evaluation import (
    compare_sentiment, evaluate_extraction, load_extraction_cases, load_sentiment_cases,
)
from sentiment_engine.reporting import comparison_table, save_artifacts


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description='규칙 기반 정보 추출과 감성 분석')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--text', help='분석할 문장')
    mode.add_argument('--evaluate', choices=('extraction', 'sentiment', 'all'))
    output = parser.add_mutually_exclusive_group()
    output.add_argument('--output-dir', type=Path, default=Path('artifacts'),
                        help='자동 저장할 상위 디렉터리 (기본: ./artifacts)')
    output.add_argument('--no-save', action='store_true', help='파일 저장 없이 터미널에만 출력')
    args = parser.parse_args(argv)

    if args.text is not None:
        if not args.text.strip():
            parser.error('text must not be blank')
        result = analyze_text(args.text)
    else:
        result = {}
        if args.evaluate in ('extraction', 'all'):
            result['extraction'] = evaluate_extraction(load_extraction_cases())
        if args.evaluate in ('sentiment', 'all'):
            result['sentiment'] = compare_sentiment(load_sentiment_cases())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.evaluate and 'sentiment' in result:
        print(comparison_table(result['sentiment']), file=sys.stderr)
    if not args.no_save:
        try:
            directory = save_artifacts(result, args.output_dir, evaluation=args.evaluate is not None)
        except (OSError, ImportError) as error:
            print(f'Could not save artifacts: {error}', file=sys.stderr)
            raise SystemExit(1) from error
        print(f'Artifacts: {directory}', file=sys.stderr)
        for path in sorted(directory.iterdir()):
            print(f'  {path.name}', file=sys.stderr)
