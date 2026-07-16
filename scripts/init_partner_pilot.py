#!/usr/bin/env python3
"""Scaffold a partner shadow-pilot working directory.

Thin wrapper around ``lpe.pilot.partner_scaffold.init_partner_pilot``.
Prefer ``lpe pilot init-partner`` when the package is installed.

Does not clear §21 or authorize causal claims.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lpe.pilot.partner_scaffold import init_partner_pilot, validate_partner_scaffold


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Create or validate a partner pilot working directory "
            "(instrumentation only; not §21)."
        )
    )
    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="Partner working directory path",
    )
    parser.add_argument("--project-id", default="partner-project")
    parser.add_argument("--ledger-name", default="partner-pilot.sqlite3")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate an existing scaffold instead of creating one",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow scaffolding into a non-empty directory",
    )
    args = parser.parse_args(argv)

    if args.validate:
        result = validate_partner_scaffold(args.dir)
        print(
            json.dumps(
                {
                    "ok": result.ok,
                    "root": str(result.root),
                    "missing": list(result.missing),
                    "errors": list(result.errors),
                    "condition_tags": list(result.condition_tags),
                    "analysis_plan_status": result.analysis_plan_status,
                    "section_21_cleared": False,
                    "ready_to_instrument": result.ready_to_instrument,
                    "ready_to_claim": False,
                },
                indent=2,
            )
        )
        return 0 if result.ok else 1

    try:
        created = init_partner_pilot(
            args.dir,
            project_id=args.project_id,
            ledger_name=args.ledger_name,
            force=args.force,
        )
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    check = validate_partner_scaffold(created.root)
    print(
        json.dumps(
            {
                "root": str(created.root),
                "ledger_path": str(created.ledger_path),
                "scaffold_version": created.scaffold_version,
                "validated": check.ok,
                "section_21_cleared": False,
                "ready_to_instrument": check.ok,
                "ready_to_claim": False,
            },
            indent=2,
        )
    )
    return 0 if check.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
