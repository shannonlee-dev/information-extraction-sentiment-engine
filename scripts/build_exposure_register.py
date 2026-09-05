"""Build a deterministic register of Korean examples already seen in the project."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable


HANGUL = re.compile(r"[가-힣]")
QUOTED_TEXT = re.compile(r"""(?P<quote>["'`])(?P<text>.*?)(?P=quote)""")


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).split())


def _source_name(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _add(registry: dict[str, set[str]], text: str, source: str) -> None:
    normalized = _normalize(text)
    if normalized and HANGUL.search(normalized):
        registry.setdefault(normalized, set()).add(source)


def _json_texts(value: Any, pointer: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key in sorted(value):
            child = value[key]
            child_pointer = f"{pointer}.{key}"
            if key in {"text", "sentence"} and isinstance(child, str):
                yield child, child_pointer
            else:
                yield from _json_texts(child, child_pointer)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _json_texts(child, f"{pointer}[{index}]")


def _python_texts(path: Path) -> Iterable[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and HANGUL.search(node.value):
            yield node.value, node.lineno


def _markdown_texts(path: Path) -> Iterable[tuple[str, int]]:
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        preview = re.match(r"^[0-5](?:\t| {2,})(.+)$", line)
        if preview and HANGUL.search(preview.group(1)):
            yield preview.group(1), line_number
        for match in QUOTED_TEXT.finditer(line):
            text = match.group("text")
            if match.group("quote") == "`":
                nested = [
                    inner.group("text")
                    for inner in QUOTED_TEXT.finditer(text)
                    if inner.group("quote") != "`" and HANGUL.search(inner.group("text"))
                ]
                if nested:
                    for value in nested:
                        yield value, line_number
                    continue
            if HANGUL.search(text):
                yield text, line_number


def build_register(
    fixture_paths: Iterable[Path],
    python_paths: Iterable[Path],
    markdown_paths: Iterable[Path],
    manual_path: Path | None,
) -> list[dict[str, Any]]:
    """Collect, normalize, and deduplicate known Korean examples."""
    registry: dict[str, set[str]] = {}
    for path in sorted(map(Path, fixture_paths), key=lambda value: value.as_posix()):
        data = json.loads(path.read_text(encoding="utf-8"))
        for text, pointer in _json_texts(data):
            _add(registry, text, f"{_source_name(path)}:{pointer}")
    for path in sorted(map(Path, python_paths), key=lambda value: value.as_posix()):
        for text, line_number in _python_texts(path):
            _add(registry, text, f"{_source_name(path)}:{line_number}")
    for path in sorted(map(Path, markdown_paths), key=lambda value: value.as_posix()):
        for text, line_number in _markdown_texts(path):
            _add(registry, text, f"{_source_name(path)}:{line_number}")
    if manual_path is not None and Path(manual_path).is_file():
        path = Path(manual_path)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict) or not isinstance(record.get("text"), str):
                raise ValueError(f"invalid manual exposure line {line_number}")
            source = str(record.get("source") or f"{_source_name(path)}:{line_number}")
            _add(registry, record["text"], source)
    return [
        {
            "id": f"exposure:{hashlib.sha256(text.encode('utf-8')).hexdigest()}",
            "text": text,
            "sources": sorted(sources),
        }
        for text, sources in sorted(registry.items())
    ]


def _default_paths(root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    fixtures = sorted((root / "tests" / "fixtures").glob("sentiment*.json"))
    python_tests = sorted((root / "tests").rglob("*.py"))
    markdown = [root / "README.md"] if (root / "README.md").is_file() else []
    markdown.extend(
        path
        for path in sorted((root / "docs").rglob("*.md"))
        if "private" not in path.relative_to(root / "docs").parts
    )
    return fixtures, python_tests, markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--source-readme", type=Path)
    parser.add_argument(
        "--manual",
        type=Path,
        default=Path("docs/evaluation/manual-exposures.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/evaluation/exposure-register.jsonl"),
    )
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    fixtures, python_tests, markdown = _default_paths(root)
    if arguments.source_readme is not None:
        markdown.append(arguments.source_readme)
    records = build_register(fixtures, python_tests, markdown, arguments.manual)
    output = arguments.output
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )
    temporary.replace(output)
    print(json.dumps({"output": str(output), "count": len(records)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
