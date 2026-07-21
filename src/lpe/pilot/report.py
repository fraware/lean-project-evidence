"""Pilot summary reports (JSON + Markdown) with explicit non-claims."""

from __future__ import annotations

import json
from pathlib import Path

from lpe.honesty.non_claims import (
    format_non_claims_block,
    non_claims_payload,
    refuse_oversell_flags,
)
from lpe.pilot.summary import PilotSummary


def render_summary_json(summary: PilotSummary) -> str:
    refuse_oversell_flags(
        section_21_cleared=summary.section_21_cleared,
        causal_claims=summary.causal_claims,
    )
    payload = summary.to_dict()
    payload["NON_CLAIMS"] = non_claims_payload()
    return json.dumps(payload, indent=2) + "\n"


def render_summary_markdown(summary: PilotSummary) -> str:
    refuse_oversell_flags(
        section_21_cleared=summary.section_21_cleared,
        causal_claims=summary.causal_claims,
    )
    lines = [
        "# Pilot warehouse summary",
        "",
        f"**Project:** `{summary.project_id}`",
        f"**Metric class:** {summary.metric_class}",
        f"**Events (scoped):** {summary.event_count}",
        "",
        format_non_claims_block(as_markdown=True).rstrip(),
        "",
        "## Explicit non-claims (summary flags)",
        "",
        f"- section_21_cleared: **{summary.section_21_cleared}**",
        f"- causal_claims: **{summary.causal_claims}**",
        f"- {summary.note}",
        "",
        "## Software metrics",
        "",
        f"- Candidates: {summary.candidate_count}",
        f"- Automated packets: {summary.automated_count}",
        f"- Automation rate: {summary.automation_rate:.3f}",
        f"- Expert minutes (total): {summary.expert_minutes_total:.2f}",
        "",
        "### Expert minutes by category",
        "",
    ]
    if summary.expert_minutes_by_category:
        for cat, mins in sorted(summary.expert_minutes_by_category.items()):
            lines.append(f"- `{cat}`: {mins:.2f}")
    else:
        lines.append("- (none)")
    lines.extend(["", "### By condition tag", ""])
    if summary.conditions:
        for tag, bucket in sorted(summary.conditions.items()):
            lines.append(
                f"- `{tag}`: candidates={bucket.candidates}, "
                f"automated={bucket.automated}, "
                f"expert_minutes={bucket.expert_minutes:.2f}"
            )
            if bucket.outcomes:
                outcomes = ", ".join(f"{k}={v}" for k, v in sorted(bucket.outcomes.items()))
                lines.append(f"  - outcomes: {outcomes}")
    else:
        lines.append("- (none)")
    lines.extend(["", "### Overhead snapshots", ""])
    if summary.overhead_snapshots:
        for snap in summary.overhead_snapshots:
            lines.append(
                f"- artifact `{snap.get('artifact_id')}`: "
                f"fraction={snap.get('overhead_fraction')}, "
                f"within_budget={snap.get('within_budget')}"
            )
    else:
        lines.append("- (none)")
    lines.extend(
        [
            "",
            "### Reproduction (when recorded)",
            "",
            f"- Known: {summary.reproduction_known_count}",
            f"- Exact: {summary.reproduction_exact_count}",
            "",
            "## Causal / §21",
            "",
            "Not claimed. This report is durable instrumentation output only.",
            "",
        ]
    )
    return "\n".join(lines)


def write_summary_reports(
    summary: PilotSummary,
    output_dir: Path,
    *,
    stem: str = "pilot_summary",
) -> tuple[Path, Path]:
    """Write JSON and Markdown summary under ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(render_summary_json(summary), encoding="utf-8")
    md_path.write_text(render_summary_markdown(summary), encoding="utf-8")
    return json_path, md_path
