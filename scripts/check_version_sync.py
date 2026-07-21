"""Version / docs / milestone drift check (CLOSURE-032).

Single source of truth:
- package version: ``pyproject.toml`` / ``lpe.__version__``
- CHANGELOG must mention that version
- ``docs/closure/MILESTONE_STATUS.json`` ``closure.current_release`` must match
- VALIDATION_REPORT.md must mention the package version
- M6/M7 remain unauthorized while Phase G is blocked

CI fails on drift. Does not invent pilot study claims.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _package_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _init_version() -> str:
    text = (ROOT / "src" / "lpe" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise ValueError("lpe.__version__ not found")
    return match.group(1)


def check_sync() -> list[str]:
    errors: list[str] = []
    pkg = _package_version()
    init_v = _init_version()
    if pkg != init_v:
        errors.append(f"pyproject version {pkg} != lpe.__version__ {init_v}")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if not re.search(rf"^## {re.escape(pkg)}\b", changelog, re.MULTILINE):
        errors.append(f"CHANGELOG.md missing heading for {pkg}")

    validation = ROOT / "VALIDATION_REPORT.md"
    if not validation.is_file():
        errors.append("VALIDATION_REPORT.md missing")
    else:
        vr = validation.read_text(encoding="utf-8")
        if pkg not in vr:
            errors.append(f"VALIDATION_REPORT.md does not mention package version {pkg}")

    milestone_path = ROOT / "docs" / "closure" / "MILESTONE_STATUS.json"
    if milestone_path.is_file():
        status = json.loads(milestone_path.read_text(encoding="utf-8"))
        current = status.get("closure", {}).get("current_release")
        if current != pkg:
            errors.append(f"MILESTONE_STATUS.json current_release {current!r} != package {pkg}")
        # Honesty: do not claim formal acceptance while flags are false.
        formal_020 = status.get("closure", {}).get("formal_0_2_0_acceptance_checklist_complete")
        if pkg == "0.2.0" and formal_020 is not False and formal_020 is not True:
            errors.append("MILESTONE_STATUS must set formal_0_2_0_acceptance_checklist_complete")
        if pkg in {"0.3.0", "0.4.0"}:
            if pkg == "0.3.0" and not status.get("closure", {}).get(
                "formal_0_3_0_acceptance_checklist_complete"
            ):
                errors.append(
                    "package 0.3.0 requires formal_0_3_0_acceptance_checklist_complete=true "
                    "or keep package at 0.2.0 (see docs/closure/REMAINING_ACCEPTANCE.md)"
                )
        # Phase G must stay blocked without authorization.
        for mid in ("M6", "M7"):
            row = next(
                (m for m in status.get("milestones", []) if m.get("id") == mid),
                None,
            )
            if row is None:
                errors.append(f"MILESTONE_STATUS missing {mid}")
                continue
            if row.get("authorized") is True:
                errors.append(
                    f"{mid} marked authorized in MILESTONE_STATUS without gate evidence "
                    "(CLOSURE-037/038 must remain blocked until Section21GateReport)"
                )
            if mid in {"M6", "M7"} and row.get("status") != "blocked":
                errors.append(f"{mid} status must be blocked until §21 authorization")
    else:
        errors.append("docs/closure/MILESTONE_STATUS.json missing")

    remaining = ROOT / "docs" / "closure" / "REMAINING_ACCEPTANCE.md"
    if not remaining.is_file():
        errors.append("docs/closure/REMAINING_ACCEPTANCE.md missing")

    # Non-claims file must exist.
    if not (ROOT / "docs" / "28_NON_CLAIMS.md").is_file():
        errors.append("docs/28_NON_CLAIMS.md missing")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check LPE version/docs sync")
    parser.add_argument(
        "--print-version",
        action="store_true",
        help="Print package version and exit 0",
    )
    args = parser.parse_args(argv)
    if args.print_version:
        print(_package_version())
        return 0
    errors = check_sync()
    if errors:
        print("version/docs sync drift:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"version/docs sync ok ({_package_version()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
