#!/usr/bin/env python3
"""Fail closed unless every named Lean theorem has only approved axioms.

Usage:
  python tools/lean_axiom_audit.py axioms.txt Namespace.theorem [...]

Unlike grep of the first line of '#print axioms', this inspects the COMPLETE
multiline bracketed list, including Lean 4.29+ native computation axioms.
"""

from __future__ import annotations

import sys
from pathlib import Path

APPROVED = frozenset({"propext", "Classical.choice", "Quot.sound"})


def extract_axioms(report: str, theorem: str) -> frozenset[str]:
    marker = f"'{theorem}' depends on axioms: ["
    occurrences = report.count(marker)
    if occurrences != 1:
        raise ValueError(
            f"{theorem}: expected exactly one complete axiom report; found {occurrences}"
        )
    suffix = report.split(marker, 1)[1]
    if "]" not in suffix:
        raise ValueError(f"{theorem}: unterminated axiom list")
    body = suffix.split("]", 1)[0]
    parts = [entry.strip() for entry in body.split(",")]
    if not parts or any(not entry for entry in parts):
        raise ValueError(f"{theorem}: empty or malformed axiom list")
    return frozenset(parts)


def validate_axioms(report: str, theorem: str) -> frozenset[str]:
    axioms = extract_axioms(report, theorem)
    unapproved = axioms - APPROVED
    if unapproved:
        raise ValueError(f"{theorem}: unapproved axioms: {', '.join(sorted(unapproved))}")
    return axioms


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: lean_axiom_audit.py REPORT THEOREM [THEOREM ...]", file=sys.stderr)
        return 2
    text = Path(argv[1]).read_text(encoding="utf-8")
    try:
        for theorem in argv[2:]:
            result = validate_axioms(text, theorem)
            print(f"{theorem}: checked; approved axioms: {', '.join(sorted(result))}")
    except ValueError as exc:
        print(f"axiom audit failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
