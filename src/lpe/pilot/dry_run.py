"""Frozen corpus pilot dry-run — durable ledger events + summary report.

Instrumentation only. Does **not** clear §21 or authorize causal claims.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from lpe.honesty.non_claims import (
    format_non_claims_block,
    non_claims_payload,
    refuse_oversell_flags,
)
from lpe.ledger.store import LedgerStore
from lpe.models import EventType, UtilityEvent
from lpe.pilot.overhead import OverheadReport
from lpe.pilot.report import write_summary_reports
from lpe.pilot.summary import summarize_pilot
from lpe.pilot.warehouse import PilotWarehouse

# Explicit honesty: this module never clears §21.
SECTION_21_CLEARED = False


@dataclass(frozen=True)
class DryRunResult:
    corpus_size: int
    project_id: str
    ledger_path: Path
    report_json: Path
    report_md: Path
    summary_json: Path
    summary_md: Path
    automation_rate: float
    overhead_within_budget: bool


def load_example_candidates(repository_root: Path) -> list[Path]:
    return sorted((repository_root / "examples" / "candidates").glob("R*.json"))


def synthetic_candidates(tmp_path: Path, count: int) -> list[Path]:
    """Generate deterministic synthetic candidates beyond the example set."""
    out_dir = tmp_path / "synthetic-candidates"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    templates = [
        (
            "private",
            "theorem",
            False,
            "Example/Internal/Synth{n}.lean",
            "+theorem Example.Internal.synth{n} : True := by trivial\n",
        ),
        (
            "public",
            "theorem",
            True,
            "Example/Public/Synth{n}.lean",
            "+theorem Example.synth{n} : True := by trivial\n",
        ),
        (
            "definition",
            "definition",
            True,
            "Example/Public/Def{n}.lean",
            "+def Example.synthDef{n} : Nat := {n}\n",
        ),
    ]
    for i in range(count):
        kind, decl_kind, public, path_tmpl, patch_tmpl = templates[i % len(templates)]
        payload = {
            "schema_version": "0.1.0",
            "candidate_id": f"candidate-synth-{i:02d}",
            "project_id": "example-category-project",
            "obligation_ids": ["O-01"],
            "base_commit": "0000000000000000000000000000000000000000",
            "claimed_intent": f"Synthetic {kind} candidate {i} for pilot dry-run.",
            "changed_paths": [path_tmpl.format(n=i)],
            "changed_declarations": [
                {
                    "name": f"Example.synth{i}",
                    "kind": decl_kind,
                    "path": path_tmpl.format(n=i),
                    "signature_changed": decl_kind == "definition",
                    "public": public,
                    "foundational": False,
                }
            ],
            "patch_text": patch_tmpl.format(n=i),
            "generator": {
                "generator_type": "ai_assistant",
                "name": "pilot-dry-run-synth",
                "version": "0",
                "model": "none",
                "prompt_hash": f"synth-{i:02d}",
                "run_id": f"dry-run-{i:02d}",
            },
        }
        path = out_dir / f"synth-{i:02d}.json"
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def build_frozen_corpus(repository_root: Path, work_dir: Path) -> list[Path]:
    examples = load_example_candidates(repository_root)
    # 6 examples + 12 synthetic = 18 (within 10-20 target).
    synthetic = synthetic_candidates(work_dir, 12)
    corpus = examples + synthetic
    if not 10 <= len(corpus) <= 20:
        raise ValueError(f"frozen corpus size {len(corpus)} out of range")
    return corpus


def run_frozen_corpus_dry_run(
    *,
    example_project: Path,
    repository_root: Path,
    work_dir: Path,
    ledger_path: Path | None = None,
    actor_id: str = "pilot-dry-run-operator",
    cli_runner: CliRunner | None = None,
) -> DryRunResult:
    """Compile → review → durable warehouse → summary reports.

    Writes pilot events to the utility ledger so a new ``LedgerStore`` instance
    can reload them. Produces JSON/Markdown reports that separate software
    metrics from causal / §21 claims.
    """
    assert SECTION_21_CLEARED is False
    refuse_oversell_flags(section_21_cleared=SECTION_21_CLEARED, causal_claims=False)
    # Lazy import avoids circular dependency with ``lpe.cli`` (which mounts pilot).
    from lpe.cli import app

    runner = cli_runner or CliRunner()
    corpus = build_frozen_corpus(repository_root, work_dir)
    ledger = ledger_path or (work_dir / "pilot-dry-run.sqlite3")
    packets_dir = work_dir / "packets"
    packets_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = work_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    store = LedgerStore(ledger)
    store.initialize()

    project_id: str | None = None
    warehouse: PilotWarehouse | None = None
    compile_overhead_minutes = 0.0

    for index, candidate_path in enumerate(corpus):
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        candidate_id = candidate["candidate_id"]
        project_id = candidate["project_id"]
        condition = "instrumented" if index % 2 == 0 else "control"

        if warehouse is None:
            warehouse = PilotWarehouse(store, actor_id=actor_id, project_id=project_id)

        warehouse.register_candidate(
            candidate_id=candidate_id,
            obligation_ids=list(candidate["obligation_ids"]),
            condition_tag=condition,
        )

        packet_path = packets_dir / f"{candidate_id}.json"
        t0 = time.perf_counter()
        compile_result = runner.invoke(
            app,
            [
                "evidence",
                "compile",
                "--project",
                str(example_project),
                "--candidate",
                str(candidate_path),
                "--output",
                str(packet_path),
                "--skip-build",
            ],
        )
        compile_overhead_minutes += (time.perf_counter() - t0) / 60.0
        if compile_result.exit_code != 0:
            raise RuntimeError(f"compile failed for {candidate_id}: {compile_result.stdout}")

        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        if packet["recommendation"] not in {"ESCALATE", "REJECT", "ACCEPT"}:
            raise RuntimeError(f"unexpected recommendation for {candidate_id}")
        # skip_build + regex-stub ⇒ hard gate must not silently pass.
        if packet["hard_gate_passed"] is not False:
            raise RuntimeError(f"hard_gate_passed unexpectedly true for {candidate_id}")

        warehouse.mark_packet_automated(
            candidate_id=candidate_id,
            condition_tag=condition,
            recommendation=packet["recommendation"],
            risk_class=packet["risk_class"],
            hard_gate_passed=packet["hard_gate_passed"],
        )

        risk_class = packet["risk_class"]
        reviewer_by_risk = {
            "R0": "lean-engineer",
            "R1": "lean-engineer",
            "R2": "repository-maintainer",
            "R3": "r3-reviewer",
            "R4": "r4-reviewer",
        }
        reviewer_id = reviewer_by_risk[risk_class]
        review_minutes = 5.0 + (index % 3)
        decision_path = work_dir / f"decision-{candidate_id}.json"
        decision_path.write_text(
            json.dumps(
                {
                    "schema_version": "0.1.0",
                    "review_id": f"review-dry-run-{index:02d}",
                    "packet_id": packet["packet_id"],
                    "reviewer_id": reviewer_id,
                    "reviewer_roles": [],
                    "decision": "REQUEST_REPAIR",
                    "confidence": 75,
                    "rationale": ("Pilot dry-run escalate path only; not a §21 study outcome."),
                    "review_minutes": review_minutes,
                    "required_repair": "Dry-run: clarify candidate intent",
                }
            ),
            encoding="utf-8",
        )
        review_result = runner.invoke(
            app,
            [
                "review",
                "record",
                "--project",
                str(example_project),
                "--decision",
                str(decision_path),
                "--ledger",
                str(ledger),
                "--risk-class",
                risk_class,
            ],
        )
        if review_result.exit_code != 0:
            raise RuntimeError(
                "review failed: " + review_result.stdout + (review_result.stderr or "")
            )

        warehouse.record_expert_time(
            candidate_id=candidate_id,
            category="review",
            minutes=review_minutes,
            condition_tag=condition,
        )
        warehouse.record_outcome(
            candidate_id=candidate_id,
            condition_tag=condition,
            decision="REQUEST_REPAIR",
            notes="dry-run escalate path; not §21",
        )

    if project_id is None or warehouse is None:
        raise RuntimeError("dry-run corpus produced no candidates")

    # Fresh store instance proves durability across "process restart".
    reloaded = LedgerStore(ledger)
    reloaded.verify()
    events = reloaded.events(project_id)
    event_types = {e.event_type for e in events}
    if EventType.CANDIDATE_REGISTERED not in event_types:
        raise RuntimeError("expected durable CANDIDATE_REGISTERED events")
    if EventType.EXPERT_TIME_RECORDED not in event_types:
        raise RuntimeError("expected durable EXPERT_TIME_RECORDED events")

    reloaded.append(
        UtilityEvent(
            event_id="evt_obl_pilot_dry_run",
            event_type=EventType.OBLIGATION_REGISTERED,
            project_id=project_id,
            artifact_id="pilot-dry-run-corpus",
            obligation_id="O-01",
            occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
            actor_id=actor_id,
            payload={"weight": 3, "note": "dry-run only; not §21"},
        )
    )

    summary = summarize_pilot(reloaded, project_id=project_id)
    baseline_minutes = summary.expert_minutes_total
    instrumented_minutes = baseline_minutes + compile_overhead_minutes
    overhead = OverheadReport.compute(
        baseline_minutes=baseline_minutes if baseline_minutes > 0 else 1.0,
        instrumented_minutes=instrumented_minutes
        if baseline_minutes > 0
        else 1.0 + compile_overhead_minutes,
        budget_fraction=0.10,
    )
    warehouse.record_overhead_snapshot(
        artifact_id="pilot-dry-run-corpus",
        report=overhead,
        note=(
            "Dry-run wall-clock proxy (compile orchestration vs review minutes); "
            "not field expert-time measurement and not §21 clearance."
        ),
    )

    # Refresh summary after overhead append.
    summary = summarize_pilot(LedgerStore(ledger), project_id=project_id)
    summary_json, summary_md = write_summary_reports(summary, reports_dir, stem="pilot_summary")

    refuse_oversell_flags(
        section_21_cleared=summary.section_21_cleared,
        causal_claims=summary.causal_claims,
    )
    nc = non_claims_payload()
    artifact = {
        "kind": "pilot_dry_run",
        "section_21_cleared": False,
        "causal_claims": False,
        "metric_class": "software_instrumentation",
        "corpus_size": len(corpus),
        "durable": True,
        "ledger_path": str(ledger),
        "automation_rate": summary.automation_rate,
        "expert_minutes_total": summary.expert_minutes_total,
        "overhead": {
            "baseline_minutes": overhead.baseline_minutes,
            "instrumented_minutes": overhead.instrumented_minutes,
            "overhead_fraction": overhead.overhead_fraction,
            "within_budget": overhead.within_budget,
            "note": (
                "Dry-run wall-clock proxy (compile orchestration vs review minutes); "
                "not field expert-time measurement and not §21 clearance."
            ),
        },
        "summary": summary.to_dict(),
        "NON_CLAIMS": nc,
        "non_claims": {
            "section_21": "not passed",
            "causal_utility": "not claimed",
            "partner_shadow_pilot": "instrumentation path only",
            "software_metrics_are_not_causal": True,
        },
    }
    report_json = reports_dir / "pilot_dry_run_report.json"
    report_md = reports_dir / "pilot_dry_run_report.md"
    report_json.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    report_md.write_text(
        "\n".join(
            [
                "# Pilot dry-run report",
                "",
                format_non_claims_block(as_markdown=True).rstrip(),
                "",
                "## Classification",
                "",
                "| Field | Value |",
                "| --- | --- |",
                "| Metric class | **software_instrumentation** |",
                "| section_21_cleared | **false** |",
                "| causal_claims | **false** |",
                "| Durable ledger | true |",
                "",
                "## Software metrics (instrumentation only)",
                "",
                f"- Corpus size: {len(corpus)}",
                f"- Automation rate: {summary.automation_rate:.3f}",
                f"- Expert minutes (warehouse): {summary.expert_minutes_total:.2f}",
                f"- Overhead within budget: {overhead.within_budget}",
                f"- Ledger: `{ledger}`",
                "",
                "## Causal / §21",
                "",
                "Not claimed. Numbers above are software-process metrics from a",
                "synthetic frozen corpus — not causal utility, not a partner shadow",
                "pilot, and not ENGINEERING_SPEC §21 clearance.",
                "",
                "See `pilot_summary.md` for durable ledger aggregations.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    return DryRunResult(
        corpus_size=len(corpus),
        project_id=project_id,
        ledger_path=ledger,
        report_json=report_json,
        report_md=report_md,
        summary_json=summary_json,
        summary_md=summary_md,
        automation_rate=summary.automation_rate,
        overhead_within_budget=overhead.within_budget,
    )
