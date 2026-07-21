"""§19 coverage gates: overall lines, critical packages, and branch hard-capable.

Usage:
  pytest ... --cov=lpe --cov-branch --cov-report=json:coverage.json ...
  python scripts/check_coverage_gates.py coverage.json

Exit 0 when overall *line* coverage meets ``--fail-under`` (default 90).
Critical-package ≥95% and branch ≥85% are measured and printed; pass
``--require-critical`` / ``--require-branch`` to hard-fail those as well
(CI enables both once §19 thresholds are met).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def norm(key: str) -> str:
    return key.replace("\\", "/")


def rel_lpe(path: str) -> str:
    p = norm(path)
    if "src/lpe/" in p:
        return p.split("src/lpe/")[-1]
    if "/lpe/" in p:
        return p.split("/lpe/")[-1]
    return p


def match(path: str, patterns: list[str]) -> bool:
    p = rel_lpe(path)
    for pat in patterns:
        if pat.endswith("/") and p.startswith(pat):
            return True
        if p == pat or p.endswith("/" + pat) or p.endswith(pat):
            return True
    return False


# Spec §19.3: policy, gate, review, ledger, TPPR, protocol ≥95%
GROUPS: dict[str, list[str]] = {
    "policy": [
        "evidence/gates.py",
        "evidence/synthesis.py",
        "execution/allowlist.py",
    ],
    "gate": ["gate/", "honesty/research_gates.py", "evidence/gates.py"],
    "review": ["review/"],
    "ledger": ["ledger/"],
    "tppr": ["metrics/"],
    "protocol": ["pilot/protocol.py", "execution/protocol.py"],
}


def group_line_pct(data: dict[str, object], patterns: list[str]) -> tuple[float, int, int]:
    files = data["files"]  # type: ignore[index]
    stmts = miss = 0
    for key, file_data in files.items():  # type: ignore[union-attr]
        if not match(str(key), patterns):
            continue
        summary = file_data["summary"]  # type: ignore[index]
        stmts += int(summary["num_statements"])  # type: ignore[index]
        miss += int(summary["missing_lines"])  # type: ignore[index]
    if stmts == 0:
        return 100.0, 0, 0
    covered = stmts - miss
    return 100.0 * covered / stmts, covered, stmts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "coverage_json",
        nargs="?",
        default="coverage.json",
        help="coverage.py JSON report path",
    )
    parser.add_argument("--fail-under", type=float, default=90.0)
    parser.add_argument("--critical-under", type=float, default=95.0)
    parser.add_argument("--branch-under", type=float, default=85.0)
    parser.add_argument(
        "--require-critical",
        action="store_true",
        help="exit non-zero when any critical group is below --critical-under",
    )
    parser.add_argument(
        "--require-branch",
        action="store_true",
        help="exit non-zero when overall branch coverage is below --branch-under",
    )
    args = parser.parse_args()

    path = Path(args.coverage_json)
    if not path.is_file():
        print(f"coverage JSON not found: {path}", file=sys.stderr)
        return 2

    data = json.loads(path.read_text(encoding="utf-8"))
    totals = data["totals"]
    stmts = int(totals["num_statements"])
    covered = int(totals["covered_lines"])
    line_pct = 100.0 * covered / stmts if stmts else 0.0
    br_tot = int(totals.get("num_branches", 0))
    br_cov = int(totals.get("covered_branches", 0))
    branch_pct = 100.0 * br_cov / br_tot if br_tot else 100.0

    print("=== §19 coverage gate ===")
    print(f"LINE overall:   {line_pct:.2f}% ({covered}/{stmts})")
    print(f"BRANCH overall: {branch_pct:.2f}% ({br_cov}/{br_tot})")
    print(f"COMBINED:       {float(totals['percent_covered']):.2f}%")

    print("\n=== Critical packages (line) ===")
    critical_ok = True
    for name, patterns in GROUPS.items():
        pct, g_cov, g_stmts = group_line_pct(data, patterns)
        met = pct >= args.critical_under
        critical_ok = critical_ok and met
        flag = "OK" if met else "BELOW"
        print(f"  {name:10s} {pct:6.2f}%  ({g_cov}/{g_stmts})  [{flag}]")

    rc = 0
    if line_pct + 1e-9 < args.fail_under:
        print(
            f"\nFAIL: overall line coverage {line_pct:.2f}% < {args.fail_under}",
            file=sys.stderr,
        )
        rc = 1
    else:
        print(f"\nPASS: overall line coverage >= {args.fail_under}")

    if args.require_branch and branch_pct + 1e-9 < args.branch_under:
        print(
            f"FAIL: branch coverage {branch_pct:.2f}% < {args.branch_under}",
            file=sys.stderr,
        )
        rc = 1
    elif branch_pct + 1e-9 < args.branch_under:
        print(
            f"NOTE: branch coverage {branch_pct:.2f}% < {args.branch_under} "
            "(soft; enable --require-branch when met)"
        )
    else:
        print(f"PASS: branch coverage >= {args.branch_under}")

    if args.require_critical and not critical_ok:
        print(
            f"FAIL: one or more critical packages < {args.critical_under}%",
            file=sys.stderr,
        )
        rc = 1
    elif not critical_ok:
        print(
            f"NOTE: critical-package {args.critical_under}% not fully met "
            "(soft; enable --require-critical when met)"
        )
    else:
        print(f"PASS: critical packages >= {args.critical_under}%")

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
