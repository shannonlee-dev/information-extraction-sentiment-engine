"""전체 JSON에서 읽기 쉬운 Markdown 실행 요약을 만든다."""

import html

from .comparison import sample_count

LABELS = {"positive": "긍정", "negative": "부정", "neutral": "중립"}


def _text(value: object) -> str:
    # 입력 문장이 Markdown 표나 HTML로 해석되지 않게 한다.
    text = " ".join(str(value).split())
    escaped_characters = []
    for char in text:
        if char in r"\`*_{}[]()#+-.!|>":
            escaped_characters.append(f"&#{ord(char)};")
        else:
            escaped_characters.append(html.escape(char))
    return "".join(escaped_characters)


def summary_markdown(result: dict, *, evaluation: bool, chart: bool = False) -> str:
    lines = ["# 실행 결과 요약", "", "[전체 데이터 보기](result.json)", ""]
    if not evaluation:
        sentiment = result["sentiment"]
        lines += [
            f"> {_text(result['text'])}",
            "",
            f"**{LABELS[sentiment['label']]} · 점수 {sentiment['score']:+g}** "
            f"/ 정보 추출 {len(result['extractions'])}건",
            "",
            "## 추출 정보",
            "",
            "| 유형 | 추출 값 |",
            "| --- | --- |",
        ]
        for item in result["extractions"]:
            value = item["normalized"]
            if isinstance(value, dict):
                value = f"{value['amount']:,} {value['currency']}"
            lines.append(f"| {_text(item['type'])} | {_text(value)} |")
        if not result["extractions"]:
            lines.append("| — | 추출된 정보가 없습니다. |")
        if sentiment["matches"]:
            lines += [
                "",
                "## 감성 판단 근거",
                "",
                "| 감성 표현 | 점수 기여 |",
                "| --- | ---: |",
            ]
            for match in sentiment["matches"][:5]:
                lines.append(f"| {_text(match['raw'])} | {match['contribution']:+g} |")
            lines += [
                "",
                "매칭 순서대로 최대 5개를 표시합니다. 점수는 확률이 아닙니다.",
            ]
        if result["diagnostics"]:
            lines += [
                "",
                f"유효성 검사에서 제외된 후보: {len(result['diagnostics'])}건. "
                "상세 사유는 전체 데이터를 확인하세요.",
            ]
    else:
        if "sentiment" in result:
            comparison = result["sentiment"]
            off = comparison["without_modifiers"]
            on = comparison["with_modifiers"]
            total_count = sample_count(comparison)
            correct_count = total_count - len(on["errors"])
            lines += [
                "## 감성 분석",
                "",
                f"**{total_count}문장 중 "
                f"{correct_count}문장 정답** · "
                f"오분류 {len(on['errors'])}건 (강조·부정 적용)",
                "",
                "| 지표 | 적용 전 | 적용 후 | 변화 |",
                "| --- | ---: | ---: | ---: |",
                f"| 정확도 | {off['accuracy']:.1%} | {on['accuracy']:.1%} | "
                f"{comparison['delta']['accuracy'] * 100:+.1f}%p |",
                f"| Macro F1 | {off['macro_f1']:.4f} | {on['macro_f1']:.4f} | "
                f"{comparison['delta']['macro_f1']:+.4f} |",
                "",
                "적용 전후는 강조·부정을 함께 끄고 켠 비교입니다. "
                "Macro F1은 정답에 등장한 클래스별 F1의 평균입니다.",
            ]
            if chart:
                lines += ["", "![강조·부정 적용 전후 감성 분석 성능](comparison.png)"]
            lines += _errors(on["errors"], sentiment=True)
        if "extraction" in result:
            report = result["extraction"]
            micro = report["micro"]
            lines += [
                "",
                "## 정보 추출",
                "",
                f"**종합 F1 {micro['f1']:.4f}** · "
                f"정확히 추출 {micro['tp']}건 / 추가 추출 {micro['fp']}건 / 누락 {micro['fn']}건",
                "",
                "| 유형 | 정밀도 | 재현율 | F1 |",
                "| --- | ---: | ---: | ---: |",
            ]
            for kind, scores in report["per_type"].items():
                lines.append(
                    f"| {_text(kind)} | {scores['precision']:.1%} | "
                    f"{scores['recall']:.1%} | {scores['f1']:.4f} |"
                )
            lines += _errors(report["errors"], sentiment=False)
        lines += [
            "",
            "> 프로젝트 작성 평가 데이터의 결과입니다. "
            "독립적인 실서비스 성능으로 해석하지 마세요.",
        ]
    return "\n".join(lines) + "\n"


def _errors(errors: list[dict], *, sentiment: bool) -> list[str]:
    if not errors:
        return ["", "오류 사례가 없습니다."]
    lines = [
        "",
        "### 오류 사례",
        "",
        f"전체 {len(errors)}건 중 데이터 순서대로 최대 3건을 표시합니다. "
        "전체 사례는 `result.json`에서 확인할 수 있습니다.",
        "",
        "| ID | 문장 | 결과 |",
        "| --- | --- | --- |",
    ]
    for error in errors[:3]:
        if sentiment:
            expected_label = LABELS[error["expected"]]
            predicted_label = LABELS[error["predicted"]]
            detail = f"{expected_label} → {predicted_label}"
        else:
            error_labels = {"fn": "누락", "fp": "추가 추출"}
            detail = error_labels[error["kind"]]
        lines.append(
            f"| {_text(error['case_id'])} | {_text(error['text'])} | {detail} |"
        )
    return lines
