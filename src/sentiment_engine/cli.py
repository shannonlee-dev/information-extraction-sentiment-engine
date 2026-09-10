"""명령행 인자를 처리하고 분석·평가 결과를 JSON으로 출력한다."""
import argparse
import json

from sentiment_engine.analysis import analyze_text
from sentiment_engine.evaluation import (
    compare_sentiment, evaluate_extraction, load_extraction_cases, load_sentiment_cases,
)


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description='규칙 기반 정보 추출과 감성 분석')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--text', help='분석할 문장')
    mode.add_argument('--evaluate', choices=('extraction', 'sentiment', 'all'))
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
