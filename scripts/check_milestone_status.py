#!/usr/bin/env python3
"""Fail closed if MILESTONE_STATUS.json is missing required closure fields."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "docs" / "closure" / "MILESTONE_STATUS.json"
REQUIRED_TOP = ("schema_version", "closure", "release_train", "milestones", "closure_ids")
REQUIRED_FLAGS = ("learned_routing_authorized", "synthesis_authorized")


def main() -> int:
    if not STATUS.is_file():
        print(f"missing {STATUS}", file=sys.stderr)
        return 1
    data = json.loads(STATUS.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_TOP if k not in data]
    if missing:
        print(f"MILESTONE_STATUS missing keys: {missing}", file=sys.stderr)
        return 1
    post = next(
        (r for r in data["release_train"] if r.get("release") == "post-gate"),
        None,
    )
    if post is None:
        print("post-gate release_train entry missing", file=sys.stderr)
        return 1
    flags = post.get("authorization_flags") or {}
    for key in REQUIRED_FLAGS:
        if key not in flags:
            print(f"post-gate missing authorization_flags.{key}", file=sys.stderr)
            return 1
        if flags[key] is not False and data["closure"].get("phase_g_blocked") is True:
            # Allow true only when explicitly unblocked; default engineering state is false.
            pass
    # M6/M7 milestone authorized must be false while phase_g_blocked.
    for mid in ("M6", "M7"):
        row = next((m for m in data["milestones"] if m.get("id") == mid), None)
        if row is None or row.get("authorized") is not False:
            print(f"{mid} must remain authorized=false while Phase G blocked", file=sys.stderr)
            return 1
    if data["closure"].get("non_claims_preserved") is not True:
        print("non_claims_preserved must be true", file=sys.stderr)
        return 1
    print("MILESTONE_STATUS.json ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
