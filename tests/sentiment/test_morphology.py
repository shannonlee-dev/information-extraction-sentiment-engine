"""B1 qualification checks; an incompatible backend must not pass silently."""

import pytest

from scripts.probe_komoran import inspect_tokens, utf16_boundaries


def record(morph, pos, begin, end):
    return {"morph": morph, "pos": pos, "begin": begin, "end": end}


def test_utf16_map_has_no_surrogate_midpoint():
    assert utf16_boundaries("🙂 좋다") == {0: 0, 2: 1, 3: 2, 4: 3, 5: 4}


def test_repeated_words_require_distinct_exact_source_ranges():
    text = "좋다  좋다"
    tokens = [record("좋", "VA", 0, 1), record("좋", "VA", 4, 5)]
    result = inspect_tokens(text, tokens, expected=[("좋", "VA", 0, 1), ("좋", "VA", 4, 5)])
    assert result["passed"]
    assert [t["source"] for t in result["tokens"]] == ["좋", "좋"]
    assert [t["eojeol_index"] for t in result["tokens"]] == [0, 1]


def test_collapsed_space_offsets_fail_even_when_numerically_in_bounds():
    result = inspect_tokens("좋다  좋다", [record("좋", "VA", 0, 1), record("좋", "VA", 3, 4)],
                            expected=[("좋", "VA", 0, 1), ("좋", "VA", 4, 5)])
    assert not result["passed"]
    assert {v["kind"] for v in result["violations"]} == {"eojeol_boundary", "expected_spans"}


def test_offset_shift_inside_a_word_is_detected_by_expected_spans():
    result = inspect_tokens("  좋다", [record("좋", "VA", 2, 4)], expected=[("좋", "VA", 2, 3)])
    assert not result["passed"]
    assert result["violations"][-1]["kind"] == "expected_spans"


def test_surrogate_halves_are_reported_without_inventing_source_spans():
    result = inspect_tokens("🙂 좋다", [record(None, "SW", 0, 1), record(None, "SW", 1, 2),
                                       record("좋", "VA", 3, 4)])
    assert not result["passed"]
    assert result["tokens"][0]["python_span"] is None
    assert result["tokens"][1]["python_span"] is None
    assert result["tokens"][2]["python_span"] == [2, 3]
    assert sum(v["kind"] == "utf16_boundary" for v in result["violations"]) == 2


@pytest.mark.parametrize("begin,end", [(0, 0), (2, 1), (-1, 1), (0, 9)])
def test_zero_length_reversed_and_out_of_bounds_ranges_fail(begin, end):
    assert not inspect_tokens("좋다", [record("좋", "VA", begin, end)])["passed"]


def test_contracted_morphemes_may_overlap_without_being_raw_substrings():
    result = inspect_tokens("했다", [record("하", "VV", 0, 1), record("았", "EP", 0, 1),
                                    record("다", "EC", 1, 2)])
    assert result["passed"]
    assert [t["source"] for t in result["tokens"]] == ["했", "했", "다"]


def test_whitespace_tokens_cannot_be_attached_to_an_arbitrary_eojeol():
    result = inspect_tokens("좋다\t좋다", [record("\t", "SW", 2, 3)])
    assert not result["passed"]
    assert result["violations"][0]["kind"] == "eojeol_boundary"


def test_empty_input_is_distinguished_from_unanalyzable_nonempty_input():
    assert inspect_tokens(" \t\r\n", [])["passed"]
    result = inspect_tokens("좋다", [])
    assert not result["passed"]
    assert result["violations"][0]["kind"] == "empty_analysis"


@pytest.mark.parametrize("status,code", [("qualified", 0), ("ineligible", 1)])
def test_probe_cli_writes_report_and_preserves_gate_exit_status(tmp_path, monkeypatch, status, code):
    import json
    from scripts import probe_komoran

    monkeypatch.setattr(probe_komoran, "probe", lambda: {"status": status})
    output = tmp_path / "probe.json"
    assert probe_komoran.main(["--output", str(output)]) == code
    assert json.loads(output.read_text())["status"] == status


def test_probe_cli_reports_environment_failure_instead_of_qualifying(tmp_path, monkeypatch):
    import json
    from scripts import probe_komoran

    def missing_jvm():
        raise RuntimeError("JVM not found")

    monkeypatch.setattr(probe_komoran, "probe", missing_jvm)
    output = tmp_path / "probe.json"
    assert probe_komoran.main(["--output", str(output)]) == 2
    report = json.loads(output.read_text())
    assert report["status"] == "environment_error"
    assert report["message"] == "JVM not found"

@pytest.mark.parametrize('text,spans', [
    ('좋다  좋다', [(0, 1), (4, 5)]), ('  좋다  ', [(2, 3)]),
    ('\t 좋다\t\t좋다\t', [(2, 3), (6, 7)]),
    ('🙂🙂 좋다', [(3, 4)]), ('좋다\r\n\r\n좋다', [(0, 1), (6, 7)]),
    ('좋다  \t좋다', [(0, 1), (5, 6)]),
])
def test_adapter_restores_original_positions(text, spans):
    from sentiment_engine.korean import analyze_morphology
    tokens = analyze_morphology(text)
    assert [(t.start, t.end) for t in tokens if (t.morph, t.pos) == ('좋', 'VA')] == spans
    assert all(0 <= t.start < t.end <= len(text) for t in tokens)
    assert all(not text[t.start:t.end].isspace() for t in tokens)


def test_adapter_reconstructs_emoji_and_records_boundary_adjustments():
    from sentiment_engine.korean import analyze_morphology_with_trace
    tokens, trace = analyze_morphology_with_trace('🙂\t좋다')
    assert [(t.morph, t.start, t.end) for t in tokens if t.pos == 'SW'] == [('🙂', 0, 1)]
    assert {a.kind for a in trace} == {'surrogate_pair', 'whitespace'}


def test_adapter_keeps_contracted_overlap_and_empty_contract():
    from sentiment_engine.korean import analyze_morphology
    tokens = analyze_morphology('했다')
    assert [(t.start,t.end) for t in tokens[:2]] == [(0,1),(0,1)]
    assert analyze_morphology(' \t\r\n') == ()


def test_adapter_rejects_surrogate_pair_with_mismatched_morph_units(monkeypatch):
    from types import SimpleNamespace as NS
    from sentiment_engine import korean

    def token(start, unit):
        value=NS(length=lambda:1,charAt=lambda index:unit)
        method=NS(invoke=lambda token:value)
        return NS(getBeginIndex=lambda:start,getEndIndex=lambda:start+1,getPos=lambda:'SW',
                  getClass=lambda:NS(getMethod=lambda name:method))
    backend=NS(jki=NS(analyze=lambda text:NS(getTokenList=lambda:[token(0,88),token(1,89)])))
    monkeypatch.setattr(korean,'_get_backend',lambda:backend)
    korean.analyze_morphology_with_trace.cache_clear()
    with pytest.raises(korean.MorphologyError,match='surrogate source pair'):
        korean.analyze_morphology('🙂')


def test_fingerprint_rejects_missing_model_files(monkeypatch):
    from pathlib import Path
    from sentiment_engine import korean
    original=Path.rglob
    monkeypatch.setattr(Path,'rglob',lambda path,pattern: iter(()) if path.name=='models' else original(path,pattern))
    korean.analyzer_fingerprint.cache_clear()
    try:
        with pytest.raises(korean.MorphologyError,match='model missing'):
            korean.analyzer_fingerprint()
    finally:
        korean.analyzer_fingerprint.cache_clear()


def test_multiword_dictionary_token_keeps_whole_source_and_start_eojeol():
    from sentiment_engine.korean import analyze_morphology
    text='2024년 3월 15일 정말 좋다'
    tokens=analyze_morphology(text)
    date=next(t for t in tokens if t.morph=='3월 15일')
    assert (date.start,date.end,date.eojeol_index)==(6,12,1)
    assert text[date.start:date.end]=='3월 15일'


@pytest.mark.parametrize('text',['좋아요ㅎ좋다','좋다ㅋㅋ나쁘다'])
def test_adapter_rejects_analyzer_source_shortening_even_when_ranges_are_in_bounds(text):
    from sentiment_engine.korean import analyze_morphology, MorphologyError
    with pytest.raises(MorphologyError,match='complete source coverage'):
        analyze_morphology(text)
