"""Immutable candidate snapshots and manifest integrity checks."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import sysconfig
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as resource:
        for chunk in iter(lambda: resource.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for directory in (root / "src", root / "data"):
        if directory.exists():
            files.extend(
                path for path in directory.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
            )
    for name in ("main.py", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"):
        path = root / name
        if path.is_file():
            files.append(path)
    files.extend(sorted(root.glob("requirements-*.txt")))
    return sorted(set(files), key=lambda path: str(path.relative_to(root)))


def snapshot(root: Path, destination: Path) -> dict[str, Any]:
    """Copy the executable allowlist and write a sibling JSON manifest."""
    root = Path(root).resolve()
    destination = Path(destination).resolve()
    if not root.is_dir():
        raise ValueError("snapshot root does not exist")
    if destination == root:
        raise ValueError("snapshot destination must differ from source root")
    destination.mkdir(parents=True, exist_ok=True)
    files: list[dict[str, Any]] = []
    for source in _relative_files(root):
        relative = source.relative_to(root)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files.append({"path": relative.as_posix(), "sha256": _sha256(target), "size": target.stat().st_size})
    manifest = {
        "format": 1,
        "snapshot_root": str(destination),
        "files": files,
        "python": sys.executable,
        "runtime": {
            "implementation": sys.implementation.name,
            "version": ".".join(str(part) for part in sys.version_info[:3]),
            "stdlib": sysconfig.get_paths().get("stdlib"),
        },
        "source": {"root": str(root), "git_diff": None},
    }
    manifest_path = destination.with_suffix(".json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid manifest: {error}") from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get("snapshot_root"), str) or not isinstance(manifest.get("files"), list):
        raise ValueError("invalid manifest shape")
    return manifest


def verify_manifest(path: Path) -> dict[str, Any]:
    """Verify every snapshotted file is present and byte-identical."""
    manifest = load_manifest(path)
    snapshot_root = Path(manifest["snapshot_root"])
    if not snapshot_root.is_dir():
        raise ValueError("snapshot root does not exist")
    manifest_paths = {
        item.get("path") for item in manifest["files"] if isinstance(item, dict)
    }
    required = {"data/sentiment_lexicon.json", "data/modifiers.json"}
    if not any(str(value).startswith("src/sentiment_engine/") for value in manifest_paths):
        raise ValueError("snapshot is missing candidate src")
    if not required.issubset(manifest_paths):
        raise ValueError("snapshot is missing candidate data")
    for item in manifest["files"]:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str):
            raise ValueError("invalid manifest file entry")
        target = (snapshot_root / item["path"]).resolve()
        if snapshot_root.resolve() not in target.parents:
            raise ValueError(f"snapshot path escapes root: {item['path']}")
        if not target.is_file():
            raise ValueError(f"snapshot file missing: {item['path']}")
        if _sha256(target) != item["sha256"]:
            raise ValueError(f"snapshot file hash mismatch: {item['path']}")
        if target.stat().st_size != item.get("size", target.stat().st_size):
            raise ValueError(f"snapshot file size mismatch: {item['path']}")
    return {"valid": True, "manifest": manifest, "manifest_path": str(Path(path).resolve())}


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--root", required=True, type=Path)
    snapshot_parser.add_argument("--output", required=True, type=Path)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("manifest", type=Path)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "snapshot":
            result = snapshot(arguments.root, arguments.output)
            print(result["manifest_path"])
        else:
            print(json.dumps(verify_manifest(arguments.manifest), ensure_ascii=False, indent=2))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
