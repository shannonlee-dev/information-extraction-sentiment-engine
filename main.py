"""한 문장을 분석하거나, 미션 평가 데이터 전체를 실행한다."""
import argparse
import json
from dataclasses import asdict

from sentiment_engine import analyze_sentiment, extract_information
from sentiment_engine.evaluation import (
    compare_sentiment, evaluate_extraction, load_extraction_cases, load_sentiment_cases,
)


def main():
    parser = argparse.ArgumentParser(description='규칙 기반 정보 추출과 감성 분석')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--text', help='분석할 문장')
    mode.add_argument('--evaluate', choices=('extraction', 'sentiment', 'all'))
    args = parser.parse_args()

    if args.text is not None:
        if not args.text.strip():
            parser.error('text must not be blank')
        extraction = extract_information(args.text)
        result = {
            'text': args.text,
            'extractions': [asdict(item) for item in extraction.items],
            'diagnostics': [asdict(item) for item in extraction.diagnostics],
            'sentiment': asdict(analyze_sentiment(args.text)),
        }
    else:
        result = {}
        if args.evaluate in ('extraction', 'all'):
            result['extraction'] = evaluate_extraction(load_extraction_cases())
        if args.evaluate in ('sentiment', 'all'):
            result['sentiment'] = compare_sentiment(load_sentiment_cases())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
