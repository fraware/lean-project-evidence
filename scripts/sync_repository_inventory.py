#!/usr/bin/env python3
"""Regenerate / check REPOSITORY_TREE.txt and MANIFEST.sha256 (CLOSURE-032).

Inventory source: ``git ls-files`` (tracked paths only). Local untracked files
are excluded so CI matches a clean checkout. After adding or removing tracked
files, run ``python scripts/sync_repository_inventory.py --write`` (or
``make inventory``) before pushing.

``MANIFEST.sha256`` is listed in the tree but is never hashed into itself.

Usage:
  python scripts/sync_repository_inventory.py --write
  python scripts/sync_repository_inventory.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREE_PATH = ROOT / "REPOSITORY_TREE.txt"
MANIFEST_PATH = ROOT / "MANIFEST.sha256"

# Never hash the manifest into itself; never invent paths outside the inventory.
_SKIP_HASH = frozenset({"MANIFEST.sha256"})


def _git_inventory() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    raw = completed.stdout.split(b"\0")
    paths: list[str] = []
    for item in raw:
        if not item:
            continue
        # Normalize to POSIX paths for stable cross-platform manifests.
        text = item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
        if text.endswith("/"):
            continue
        paths.append(text)
    return sorted(set(paths))


def _sha256_file(rel: str) -> str:
    path = ROOT / rel
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_tree(paths: list[str]) -> str:
    lines = list(paths)
    if "MANIFEST.sha256" not in lines:
        lines.append("MANIFEST.sha256")
    if "REPOSITORY_TREE.txt" not in lines:
        lines.append("REPOSITORY_TREE.txt")
    return "\n".join(sorted(set(lines))) + "\n"


def render_manifest(paths: list[str]) -> str:
    # Hash the tree content we are about to write (deterministic).
    tree_body = render_tree(paths)
    entries: list[tuple[str, str]] = []
    for rel in sorted(set(paths) | {"REPOSITORY_TREE.txt"}):
        if rel in _SKIP_HASH:
            continue
        if rel == "REPOSITORY_TREE.txt":
            digest = hashlib.sha256(tree_body.encode("utf-8")).hexdigest()
        else:
            if not (ROOT / rel).is_file():
                raise FileNotFoundError(f"inventory path missing on disk: {rel}")
            digest = _sha256_file(rel)
        entries.append((digest, rel))
    return "".join(f"{digest}  {rel}\n" for digest, rel in entries)


def write_inventory() -> None:
    paths = _git_inventory()
    # Ensure self-referential inventory files exist for the next check cycle.
    tree_body = render_tree(paths)
    TREE_PATH.write_text(tree_body, encoding="utf-8", newline="\n")
    # Recompute after writing tree so MANIFEST matches on-disk TREE bytes.
    MANIFEST_PATH.write_text(render_manifest(paths), encoding="utf-8", newline="\n")
    # Tree should list MANIFEST; rewrite tree once more if needed (paths already include both).
    final_paths = _git_inventory()
    TREE_PATH.write_text(render_tree(final_paths), encoding="utf-8", newline="\n")
    MANIFEST_PATH.write_text(render_manifest(final_paths), encoding="utf-8", newline="\n")
    print(f"wrote {TREE_PATH.relative_to(ROOT)} and {MANIFEST_PATH.relative_to(ROOT)}")
    print(f"  {len(final_paths)} inventory paths")


def check_inventory() -> list[str]:
    errors: list[str] = []
    if not TREE_PATH.is_file():
        errors.append("REPOSITORY_TREE.txt missing")
    if not MANIFEST_PATH.is_file():
        errors.append("MANIFEST.sha256 missing")
    if errors:
        return errors

    paths = _git_inventory()
    expected_tree = render_tree(paths)
    expected_manifest = render_manifest(paths)
    actual_tree = TREE_PATH.read_text(encoding="utf-8")
    actual_manifest = MANIFEST_PATH.read_text(encoding="utf-8")

    if actual_tree != expected_tree:
        errors.append(
            "REPOSITORY_TREE.txt drift — run: python scripts/sync_repository_inventory.py --write"
        )
    if actual_manifest != expected_manifest:
        errors.append(
            "MANIFEST.sha256 drift — run: python scripts/sync_repository_inventory.py --write"
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="Regenerate tree + manifest")
    mode.add_argument("--check", action="store_true", help="Fail on drift")
    args = parser.parse_args(argv)

    try:
        if args.write:
            write_inventory()
            return 0
        errors = check_inventory()
        if errors:
            print("repository inventory drift:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        print("repository inventory ok (REPOSITORY_TREE.txt + MANIFEST.sha256)")
        return 0
    except (OSError, subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"sync_repository_inventory failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
