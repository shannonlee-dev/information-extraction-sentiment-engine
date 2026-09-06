"""Single locked KOMORAN adapter with original Python source positions."""

from functools import lru_cache

import hashlib
import importlib.metadata
import re
from pathlib import Path
from threading import RLock

from sentiment_engine.models import MorphToken, MorphologyAdjustment


class MorphologyError(ValueError):
    """An explicit environment or source-position error; never a fallback."""


_LOCK = RLock()


def utf16_boundaries(text: str) -> dict[int, int]:
    boundaries = {0: 0}
    offset = 0
    for index, character in enumerate(text, 1):
        if 0xD800 <= ord(character) <= 0xDFFF:
            raise MorphologyError('input contains an unpaired surrogate')
        offset += 2 if ord(character) > 0xFFFF else 1
        boundaries[offset] = index
    return boundaries


@lru_cache(maxsize=1)
def analyzer_fingerprint() -> dict:
    try:
        import konlpy
        versions = {name: importlib.metadata.version(name) for name in ('konlpy', 'JPype1')}
        if versions['konlpy'] != '0.6.0' or versions['JPype1'] != '1.6.0':
            raise MorphologyError('KOMORAN requires KoNLPy 0.6.0 / JPype1 1.6.0; install requirements-runtime.lock')
        root = Path(konlpy.__file__).resolve().parent
        files = [root/'tag/_komoran.py', root/'jvm.py', *sorted((root/'java').glob('*.jar')),
                 *sorted(p for p in (root/'java/data/models').rglob('*') if p.is_file())]
        if (not (root/'java/komoran-3.0.jar').is_file() or
                {p.name for p in files if p.parent == root/'java/data/models'} !=
                {'irregular.model', 'observation.model', 'pos.table', 'transition.model'}):
            raise MorphologyError('bundled KOMORAN jar/model missing')
        hashes = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        return {'versions': versions, 'files': hashes, 'adapter_contract': 2, 'heap_mib': 1024,
                'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    except (ImportError, OSError) as error:
        raise MorphologyError('KOMORAN resources unavailable; install requirements-runtime.lock and JDK 17') from error


@lru_cache(maxsize=1)
def _get_backend():
    analyzer_fingerprint()
    try:
        import jpype
        from konlpy.tag import Komoran
        backend = Komoran(max_heap_size=1024)
        version = str(jpype.JClass('java.lang.System').getProperty('java.specification.version'))
        if version != '17':
            raise MorphologyError('KOMORAN runtime requires JDK 17; set JAVA_HOME')
        return backend
    except Exception as error:
        raise MorphologyError('KOMORAN initialization failed; install JDK 17 and set JAVA_HOME') from error


def _source_map(text: str):
    """Mirror only bundled Java [ ]+ collapse and String.trim (U+0000..20)."""
    chars = []
    for match in re.finditer(r' +|[^ ]', text):
        chars.append((' ' if match.group()[0] == ' ' else match.group(), match.start(), match.end()))
    while chars and ord(chars[0][0]) <= 32:
        chars.pop(0)
    while chars and ord(chars[-1][0]) <= 32:
        chars.pop()
    normalized = ''.join(c for c, _, _ in chars)
    boundaries = utf16_boundaries(normalized)
    starts = {j: chars[p][1] for j,p in boundaries.items() if p < len(chars)}
    ends = {j: chars[p-1][2] for j,p in boundaries.items() if p > 0}
    return normalized, starts, ends


@lru_cache(maxsize=512)
def analyze_morphology_with_trace(text: str) -> tuple[tuple[MorphToken, ...], tuple[MorphologyAdjustment, ...]]:
    if not isinstance(text, str):
        raise TypeError('text must be a string')
    utf16_boundaries(text)
    if not text.strip():
        return (), ()
    words = list(re.finditer(r'\S+', text))
    tokens, trace = [], []
    offset = 0
    with _LOCK:
        backend = _get_backend()
        for line in text.splitlines(keepends=True):
            sentence = line.rstrip('\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029')
            if not sentence.strip():
                offset += len(line)
                continue
            normalized, starts, ends = _source_map(sentence)
            try:
                raw = list(backend.jki.analyze(sentence).getTokenList())
                expected_length = len(normalized.encode('utf-16-le')) // 2
                if (not raw or min(int(t.getBeginIndex()) for t in raw) != 0
                        or max(int(t.getEndIndex()) for t in raw) != expected_length):
                    raise MorphologyError('KOMORAN did not preserve complete source coverage')
                i = 0
                while i < len(raw):
                    token = raw[i]
                    begin, end, pos = int(token.getBeginIndex()), int(token.getEndIndex()), str(token.getPos())
                    if begin not in starts or end not in ends:
                        # Only two adjacent SW halves of this exact supplementary
                        # source character can be reassembled; no arbitrary repair.
                        next_token = raw[i+1] if i+1 < len(raw) else None
                        if (begin in starts and end == begin+1 and end not in ends
                                and next_token is not None and pos == str(next_token.getPos()) == 'SW'
                                and int(next_token.getBeginIndex()) == end
                                and int(next_token.getEndIndex()) == begin+2 and begin+2 in ends):
                            end = begin+2
                            morph = sentence[starts[begin]:ends[end]]
                            if len(morph) != 1 or ord(morph) <= 0xFFFF:
                                raise MorphologyError('invalid surrogate source pair')
                            encoded = morph.encode('utf-16-le')
                            expected_units = [int.from_bytes(encoded[n:n+2], 'little') for n in (0, 2)]
                            actual_units = []
                            for half in (token, next_token):
                                # Reflection retains java.lang.String as Object,
                                # avoiding JPype's lone-surrogate str conversion.
                                value = half.getClass().getMethod('getMorph').invoke(half)
                                if value.length() != 1:
                                    raise MorphologyError('invalid surrogate source pair')
                                actual_units.append(int(value.charAt(0)))
                            if actual_units != expected_units:
                                raise MorphologyError('invalid surrogate source pair')
                            trace.append(MorphologyAdjustment('surrogate_pair', offset+starts[begin], offset+ends[end]))
                            i += 1
                        else:
                            raise MorphologyError('KOMORAN returned a non-source UTF-16 boundary')
                    else:
                        morph = str(token.getMorph())
                    if begin >= end:
                        raise MorphologyError('KOMORAN returned a nonpositive source span')
                    start, stop = offset+starts[begin], offset+ends[end]
                    source = text[start:stop]
                    if source.isspace() and pos == 'SW':
                        trace.append(MorphologyAdjustment('whitespace', start, stop))
                    else:
                        owners = [n for n,w in enumerate(words) if w.start() <= start < w.end()]
                        if len(owners) != 1 or not any(w.start() < stop <= w.end() for w in words):
                            raise MorphologyError('KOMORAN token endpoints are not in original eojeols')
                        # A dictionary proper noun can span several eojeols.
                        # Preserve it whole and identify the starting eojeol.
                        tokens.append(MorphToken(morph, pos, start, stop, owners[0]))
                    i += 1
            except MorphologyError:
                raise
            except Exception as error:
                raise MorphologyError(f'KOMORAN analysis failed: {type(error).__name__}') from error
            offset += len(line)
    if not tokens:
        raise MorphologyError('KOMORAN produced no analysis for nonempty input')
    return tuple(tokens), tuple(trace)


def analyze_morphology(text: str) -> tuple[MorphToken, ...]:
    return analyze_morphology_with_trace(text)[0]
