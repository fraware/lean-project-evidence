#!/usr/bin/env python3
"""Fail CI when CODEOWNERS still contains REPLACE_WITH placeholders (AUDIT-022).

Local development can set LPE_CODEOWNERS_PLACEHOLDERS_OK=1 to warn instead of fail.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEOWNERS = ROOT / ".github" / "CODEOWNERS"
PLACEHOLDER = "REPLACE_WITH"


def main() -> int:
    text = CODEOWNERS.read_text(encoding="utf-8")
    hits = [
        f"line {index}: {line.rstrip()}"
        for index, line in enumerate(text.splitlines(), start=1)
        if PLACEHOLDER in line and not line.lstrip().startswith("#")
    ]
    if not hits:
        print("CODEOWNERS: no REPLACE_WITH placeholders")
        return 0

    message = (
        "FAIL: .github/CODEOWNERS still contains REPLACE_WITH placeholders.\n"
        "Merge is blocked until real GitHub handles replace placeholders "
        "(see .github/CODEOWNERS).\n" + "\n".join(hits)
    )
    warn_only = os.environ.get("LPE_CODEOWNERS_PLACEHOLDERS_OK", "").strip() in {
        "1",
        "true",
        "TRUE",
        "yes",
        "YES",
    }
    if warn_only:
        print(message.replace("FAIL:", "WARN:", 1), file=sys.stderr)
        return 0
    print(message, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
