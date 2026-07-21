"""Shadow pilot instrumentation.

Primary path: ``PilotWarehouse`` appends to the utility ledger (durable across
process restart). ``PilotInstrumentation`` remains an in-memory helper for
unit tests and ephemeral scratch; prefer the warehouse for partner pilots.
"""

from __future__ import annotations

from lpe.pilot.dry_run import DryRunResult, run_frozen_corpus_dry_run
from lpe.pilot.field_overhead import (
    FieldOverheadEntry,
    compute_field_overhead,
    record_field_overhead,
)
from lpe.pilot.instrumentation import ExpertTimeEvent, PilotCandidate, PilotInstrumentation
from lpe.pilot.overhead import OverheadReport
from lpe.pilot.partner_scaffold import (
    PARTNER_CONDITION_TAGS,
    ScaffoldResult,
    ScaffoldValidation,
    init_partner_pilot,
    validate_partner_scaffold,
)
from lpe.pilot.report import render_summary_json, render_summary_markdown, write_summary_reports
from lpe.pilot.summary import PilotSummary, summarize_pilot
from lpe.pilot.warehouse import PilotRecordResult, PilotWarehouse

__all__ = [
    "PARTNER_CONDITION_TAGS",
    "DryRunResult",
    "ExpertTimeEvent",
    "FieldOverheadEntry",
    "OverheadReport",
    "PilotCandidate",
    "PilotInstrumentation",
    "PilotRecordResult",
    "PilotSummary",
    "PilotWarehouse",
    "ScaffoldResult",
    "ScaffoldValidation",
    "compute_field_overhead",
    "init_partner_pilot",
    "record_field_overhead",
    "render_summary_json",
    "render_summary_markdown",
    "run_frozen_corpus_dry_run",
    "summarize_pilot",
    "validate_partner_scaffold",
    "write_summary_reports",
]
