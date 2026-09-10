"""명령행 인자를 처리하고 분석·평가 결과를 출력한다."""
import argparse
import json
import sys
from pathlib import Path

from sentiment_engine.analysis import analyze_text
from sentiment_engine.evaluation import (
    compare_sentiment, evaluate_extraction, load_extraction_cases, load_sentiment_cases,
)
from sentiment_engine.reporting import save_artifacts
from sentiment_engine.reporting.terminal import terminal_report


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description='규칙 기반 정보 추출과 감성 분석')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--text', help='분석할 문장')
    mode.add_argument('--evaluate', choices=('extraction', 'sentiment', 'all'))
    output = parser.add_mutually_exclusive_group()
    output.add_argument('--output-dir', type=Path, default=Path('artifacts'),
                        help='자동 저장할 상위 디렉터리 (기본: ./artifacts)')
    output.add_argument('--no-save', action='store_true', help='파일 저장 없이 터미널에만 출력')
    parser.add_argument('--format', choices=('auto', 'text', 'json'), default='auto',
                        help='출력 형식 (기본: 터미널은 text, 파이프·리다이렉션은 json)')
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
    text_output = args.format == 'text' or (args.format == 'auto' and sys.stdout.isatty())
    if text_output:
        print(terminal_report(result, evaluation=args.evaluate is not None), flush=True)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    if not args.no_save:
        try:
            directory = save_artifacts(result, args.output_dir, evaluation=args.evaluate is not None)
        except (OSError, ImportError) as error:
            print(f'\n저장 실패: {error}', file=sys.stderr)
            if isinstance(error, ModuleNotFoundError) and error.name == 'matplotlib':
                print('해결: 실행 중인 Python 환경에 설치하세요: '
                      'python -m pip install "matplotlib>=3.7,<4"', file=sys.stderr)
            print('평가·분석 결과는 위에 출력되었습니다. '
                  '파일 저장이 필요 없으면 --no-save를 사용하세요.', file=sys.stderr)
            raise SystemExit(1) from error
        print(f'\n저장 완료  {directory}', file=sys.stderr)
        print('  ' + ' · '.join(path.name for path in sorted(directory.iterdir())),
              file=sys.stderr)
