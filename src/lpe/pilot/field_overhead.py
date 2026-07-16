"""Instrumentation overhead helpers for partner field recording.

Separates **wall-clock instrumentation overhead** from **expert review minutes**.
Overhead snapshots use category ``overhead_snapshot`` and are excluded from the
TPPR expert-hours denominator. This module never clears §21.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from lpe.pilot.overhead import OverheadReport
from lpe.pilot.warehouse import OVERHEAD_CATEGORY, PilotRecordResult, PilotWarehouse


@dataclass(frozen=True)
class FieldOverheadEntry:
    """Partner-facing overhead record (wall-clock, not review minutes)."""

    baseline_minutes: float
    wall_minutes: float
    overhead_fraction: float
    within_budget: bool
    budget_fraction: float
    category: str
    recorded_at: str
    note: str | None
    candidate_id: str | None
    condition_tag: str | None
    section_21_cleared: bool = False
    causal_claims: bool = False
    is_review_minutes: bool = False

    @classmethod
    def from_report(
        cls,
        report: OverheadReport,
        *,
        budget_fraction: float = 0.10,
        note: str | None = None,
        candidate_id: str | None = None,
        condition_tag: str | None = None,
        recorded_at: str | None = None,
    ) -> FieldOverheadEntry:
        return cls(
            baseline_minutes=report.baseline_minutes,
            wall_minutes=report.instrumented_minutes,
            overhead_fraction=report.overhead_fraction,
            within_budget=report.within_budget,
            budget_fraction=budget_fraction,
            category=OVERHEAD_CATEGORY,
            recorded_at=recorded_at
            or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            note=note,
            candidate_id=candidate_id,
            condition_tag=condition_tag,
            section_21_cleared=False,
            causal_claims=False,
            is_review_minutes=False,
        )


def compute_field_overhead(
    *,
    baseline_minutes: float,
    wall_minutes: float,
    budget_fraction: float = 0.10,
    note: str | None = None,
    candidate_id: str | None = None,
    condition_tag: str | None = None,
) -> tuple[OverheadReport, FieldOverheadEntry]:
    """Compute overhead from baseline vs instrumented **wall-clock** minutes."""
    if baseline_minutes < 0 or wall_minutes < 0:
        raise ValueError("baseline_minutes and wall_minutes must be non-negative")
    report = OverheadReport.compute(
        baseline_minutes=baseline_minutes,
        instrumented_minutes=wall_minutes,
        budget_fraction=budget_fraction,
    )
    entry = FieldOverheadEntry.from_report(
        report,
        budget_fraction=budget_fraction,
        note=note
        or (
            "Field wall-clock instrumentation overhead; not expert review minutes "
            "and not §21 clearance."
        ),
        candidate_id=candidate_id,
        condition_tag=condition_tag,
    )
    return report, entry


def record_field_overhead(
    warehouse: PilotWarehouse,
    *,
    baseline_minutes: float,
    wall_minutes: float,
    budget_fraction: float = 0.10,
    candidate_id: str | None = None,
    condition_tag: str | None = None,
    note: str | None = None,
    local_log: Path | None = None,
) -> tuple[PilotRecordResult, FieldOverheadEntry]:
    """Append overhead_snapshot to the ledger and optionally mirror to a JSONL log.

    Wall-clock minutes must not be recorded as ``expert-time`` review categories.
    """
    report, entry = compute_field_overhead(
        baseline_minutes=baseline_minutes,
        wall_minutes=wall_minutes,
        budget_fraction=budget_fraction,
        note=note,
        candidate_id=candidate_id,
        condition_tag=condition_tag,
    )
    result = warehouse.record_overhead_snapshot(
        artifact_id=candidate_id or "field-overhead",
        report=report,
        condition_tag=condition_tag,
        note=entry.note,
    )
    if local_log is not None:
        append_field_overhead_log(local_log, entry, event_id=result.event_id)
    return result, entry


def append_field_overhead_log(
    path: Path,
    entry: FieldOverheadEntry,
    *,
    event_id: str | None = None,
) -> None:
    """Append a partner-local JSONL mirror (optional; ledger remains authoritative)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    row = asdict(entry)
    if event_id is not None:
        row["event_id"] = event_id
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
