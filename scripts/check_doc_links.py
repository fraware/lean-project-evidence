#!/usr/bin/env python3
"""Fail-closed check for relative markdown links under docs/ and top-level *.md (§19.1).

Does not fetch HTTP(S) URLs (network-optional). Verifies that relative targets
exist on disk.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _iter_markdown(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.glob("*.md"):
        files.append(path)
    docs = root / "docs"
    if docs.is_dir():
        files.extend(sorted(docs.rglob("*.md")))
    return files


def _normalize_target(raw: str) -> str | None:
    target = raw.strip().strip("<>").split("#", 1)[0].strip()
    if not target:
        return None  # pure fragment
    if target.startswith(("http://", "https://", "mailto:", "data:")):
        return None
    return target


def check_file(path: Path, repo: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    for match in LINK_RE.finditer(text):
        target = _normalize_target(match.group(2))
        if target is None:
            continue
        resolved = (path.parent / target).resolve()
        try:
            resolved.relative_to(repo.resolve())
        except ValueError:
            errors.append(f"{path}: link escapes repo: {target}")
            continue
        if not resolved.exists():
            errors.append(f"{path}: missing relative link target: {target}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Repository root (default: parent of scripts/)",
    )
    args = parser.parse_args(argv)
    repo = args.root or _repo_root()
    errors: list[str] = []
    for path in _iter_markdown(repo):
        errors.extend(check_file(path, repo))
    if errors:
        print(f"doc-link check failed ({len(errors)}):", file=sys.stderr)
        for err in errors[:50]:
            print(f"  {err}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more", file=sys.stderr)
        return 1
    print("doc-link check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
