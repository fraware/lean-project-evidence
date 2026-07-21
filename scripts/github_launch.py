#!/usr/bin/env python3
"""GitHub launch helpers: labels, milestones, and backlog import."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def read_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def require_gh() -> str:
    gh = shutil.which("gh")
    if gh is None:
        print("GitHub CLI 'gh' is required for --apply operations.", file=sys.stderr)
        raise SystemExit(2)
    return gh


def run_gh_json(gh: str, args: Sequence[str]) -> object:
    completed = subprocess.run(
        [gh, *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def issue_body(row: dict[str, str]) -> str:
    depends_on = row.get("depends_on", "").strip()
    criteria = row.get("acceptance_criteria", "").strip()
    lines = [
        f"**Backlog ID:** {row['issue_id']}",
        f"**Milestone:** {row['milestone']}",
        "",
    ]
    if depends_on:
        lines.extend(
            [
                "## Depends on",
                "",
                depends_on.replace(",", ", "),
                "",
            ]
        )
    lines.extend(
        [
            "## Acceptance criteria",
            "",
            criteria,
            "",
            "---",
            (
                "Imported from `backlog/issues.csv`. "
                "Link pull requests to this issue and state the path to TPPR."
            ),
        ]
    )
    return "\n".join(lines)


def milestone_title(code: str) -> str:
    mapping = {
        "M0": "M0 Foundation",
        "M1": "M1 Deterministic Evidence",
        "M2": "M2 Review Operation",
        "M3": "M3 Lean-Aware Evidence",
        "M4": "M4 Semantic Evidence",
        "M5": "M5 Shadow Pilot",
        "M6": "M6 Learned Routing",
        "M7": "M7 Project-Targeted Synthesis",
    }
    return mapping.get(code, code)


def cmd_labels(args: argparse.Namespace) -> int:
    labels = read_lines(repo_root() / "backlog" / "github_labels.txt")
    if not args.apply:
        print("Dry run — labels to create:")
        for label in labels:
            print(f"  - {label}")
        return 0

    gh = require_gh()
    existing = {item["name"] for item in run_gh_json(gh, ["label", "list", "--json", "name"])}
    for label in labels:
        if label in existing:
            print(f"skip existing label: {label}")
            continue
        subprocess.run([gh, "label", "create", label], check=True)
        print(f"created label: {label}")
    return 0


def cmd_milestones(args: argparse.Namespace) -> int:
    titles = read_lines(repo_root() / "backlog" / "milestones.txt")
    if not args.apply:
        print("Dry run — milestones to create:")
        for title in titles:
            print(f"  - {title}")
        return 0

    gh = require_gh()
    milestones = run_gh_json(gh, ["api", "repos/{owner}/{repo}/milestones", "--paginate"])
    existing = {item["title"] for item in milestones} if isinstance(milestones, list) else set()
    for title in titles:
        if title in existing:
            print(f"skip existing milestone: {title}")
            continue
        subprocess.run(
            [gh, "api", "repos/{owner}/{repo}/milestones", "-f", f"title={title}"],
            check=True,
        )
        print(f"created milestone: {title}")
    return 0


def cmd_import_issues(args: argparse.Namespace) -> int:
    csv_path = repo_root() / "backlog" / "issues.csv"
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not args.apply:
        print(f"Dry run — {len(rows)} issues from {csv_path}:")
        for row in rows:
            print(
                f"  - [{row['issue_id']}] {row['title']} "
                f"({milestone_title(row['milestone'])}; {row['labels']})"
            )
        return 0

    gh = require_gh()
    milestones = run_gh_json(gh, ["api", "repos/{owner}/{repo}/milestones", "--paginate"])
    milestone_numbers = (
        {item["title"]: item["number"] for item in milestones}
        if isinstance(milestones, list)
        else {}
    )

    for row in rows:
        ms_title = milestone_title(row["milestone"])
        title = f"{row['issue_id']}: {row['title']}"
        command = [
            gh,
            "issue",
            "create",
            "--title",
            title,
            "--body",
            issue_body(row),
        ]
        for label in row["labels"].split(","):
            label = label.strip()
            if label:
                command.extend(["--label", label])
        if ms_title in milestone_numbers:
            command.extend(["--milestone", ms_title])

        subprocess.run(command, check=True)
        print(f"created issue: {title}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler in (
        ("labels", cmd_labels),
        ("milestones", cmd_milestones),
        ("import-issues", cmd_import_issues),
    ):
        sub = subparsers.add_parser(name)
        sub.add_argument(
            "--apply",
            action="store_true",
            help="Create resources on GitHub (requires authenticated gh). Default is dry-run.",
        )
        sub.set_defaults(func=handler)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
