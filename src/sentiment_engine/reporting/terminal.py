"""터미널에서 읽기 쉬운 분석·평가 요약."""
from .comparison import comparison_rows, sample_count


def terminal_report(result: dict, *, evaluation: bool) -> str:
    lines = ['정보 추출 · 감성 분석', '─' * 58]
    if not evaluation:
        sentiment = result['sentiment']
        label = {'positive': '긍정', 'negative': '부정', 'neutral': '중립'}[sentiment['label']]
        lines += [f"입력  {result['text']}", '',
                  f"감성  {label}  ·  점수 {sentiment['score']:+g}",
                  f"추출  {len(result['extractions'])}건"]
        for item in result['extractions']:
            value = item['normalized']
            if isinstance(value, dict):
                value = f"{value['amount']:,} {value['currency']}"
            lines.append(f"  {item['type']:<8} {value}")
        if result['diagnostics']:
            lines.append(f"확인 필요  {len(result['diagnostics'])}건 (상세 내용은 JSON 참조)")
    else:
        if 'extraction' in result:
            report = result['extraction']
            lines += ['', '정보 추출',
                      f"  {'Type':<10} {'Precision':>10} {'Recall':>10} {'F1':>10}"]
            for kind, scores in [*report['per_type'].items(), ('micro', report['micro'])]:
                lines.append(f"  {kind:<10} {scores['precision']:>10.4f} "
                             f"{scores['recall']:>10.4f} {scores['f1']:>10.4f}")
            lines.append(f"  누락·추가 추출 오류: {len(report['errors'])}건")
        if 'sentiment' in result:
            comparison = result['sentiment']
            lines += ['', f'감성 분석 · {sample_count(comparison)}문장',
                      f"  {'Metric':<10} {'OFF':>10} {'ON':>10} {'Delta':>10}"]
            for label, off, on, delta in comparison_rows(comparison):
                lines.append(f'  {label:<10} {off:>10.4f} {on:>10.4f} {delta:>+10.4f}')
            lines += ['', '  ON: 강조·부정 적용 / OFF: 모두 해제',
                      '  지표: 0–1 척도 · Macro F1: 정답에 있는 클래스의 평균']
        lines += ['', '참고:  프로젝트 작성 평가 데이터입니다.']
    return '\n'.join(lines)
