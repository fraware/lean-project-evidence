"""Canonical NON_CLAIMS list — shared by CLI, pilot reports, and docs/28.

Software metrics from dry-runs / warehouse summaries are **not** causal TPPR,
§21 clearance, Mathlib elaborator truth, or R3/R4 production ACCEPT.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

# Stable ids — tests and doctors assert these remain present.
NON_CLAIMS_ITEMS: tuple[dict[str, str], ...] = (
    {
        "id": "section_21",
        "claim": "ENGINEERING_SPEC §21 scientific clearance",
        "status": "not passed",
        "detail": (
            "Shadow-pilot and learned-routing criteria in ENGINEERING_SPEC §21 "
            "are not met. Instrumentation and fixture dry-runs do not clear them."
        ),
    },
    {
        "id": "causal_tppr",
        "claim": "Causal utility / causal TPPR from dry-runs or warehouse metrics",
        "status": "not claimed",
        "detail": (
            "Automation rate, reproduction rate, overhead, and TPPR snapshots from "
            "pilot dry-run or `lpe pilot summary` are software-process metrics only. "
            "They do not prove LPE improves outcomes."
        ),
    },
    {
        "id": "r3_r4_accept",
        "claim": "R3/R4 auto-ACCEPT or single-reviewer production ACCEPT (ADR 0003)",
        "status": "refused",
        "detail": (
            "`lpe review record` refuses ACCEPT for R3/R4. Auto-accept remains "
            "impossible. Qualified human acceptance requires distinct dimension "
            "attestations via `lpe review attest` + `lpe review accept-quorum` "
            "(still not a §21 / causal claim)."
        ),
    },
    {
        "id": "mathlib_elaborator",
        "claim": "Mathlib-scale elaborator-complete kernel truth",
        "status": "not claimed",
        "detail": (
            "Fixture-scope toolchain extraction is not Mathlib-scale. Regex-stub "
            "findings are incomplete; empty axioms_used must never be treated as "
            "axiom closure."
        ),
    },
    {
        "id": "m6_m7_training",
        "claim": "M6 learned routing / M7 synthesis training (EPIC-039/040)",
        "status": "blocked until §21",
        "detail": (
            "Training entrypoints do not exist. Deterministic routing baseline and "
            "fixture synthesis harness are scaffolds only."
        ),
    },
    {
        "id": "dry_run_is_not_study",
        "claim": "Frozen-corpus dry-run as a prospective partner study",
        "status": "not a study",
        "detail": (
            "Synthetic / example corpora do not substitute for prospective human "
            "expert review under a frozen analysis plan."
        ),
    },
)

NON_CLAIMS_BANNER = "NON_CLAIMS"
NON_CLAIMS_DOC_PATH = "docs/NON_CLAIMS.md"

# CLI / payload keys that must never be True for honesty.
_FORBIDDEN_TRUE_KEYS = frozenset(
    {
        "section_21_cleared",
        "claim_section_21",
        "causal_claims",
        "claim_causal",
        "claim_causal_tppr",
        "mathlib_complete",
        "claim_mathlib",
        "r3_r4_auto_accept",
        "production_accept_r3",
        "production_accept_r4",
        "m6_training_enabled",
        "m7_training_enabled",
        "epic_039_cleared",
        "epic_040_cleared",
    }
)


class OversellClaimError(ValueError):
    """Raised when a caller attempts to assert a forbidden clearance/claim flag."""


def format_non_claims_block(*, as_markdown: bool = True) -> str:
    """Render the mandatory NON_CLAIMS block for CLI / report output."""
    lines: list[str] = []
    if as_markdown:
        lines.extend(
            [
                f"## {NON_CLAIMS_BANNER}",
                "",
                f"Canonical list: `{NON_CLAIMS_DOC_PATH}`.",
                "",
                "Software metrics ≠ causal utility. Dry-run / warehouse numbers do "
                "**not** clear §21.",
                "",
            ]
        )
        for item in NON_CLAIMS_ITEMS:
            lines.append(
                f"- **{item['id']}**: {item['claim']} — **{item['status']}**. {item['detail']}"
            )
        lines.append("")
    else:
        lines.append(f"{NON_CLAIMS_BANNER}:")
        for item in NON_CLAIMS_ITEMS:
            lines.append(f"  - [{item['id']}] {item['claim']}: {item['status']}")
        lines.append(f"  See {NON_CLAIMS_DOC_PATH}")
    return "\n".join(lines)


def non_claims_payload() -> dict[str, Any]:
    """Machine-readable NON_CLAIMS for JSON CLI / dry-run artifacts."""
    return {
        "banner": NON_CLAIMS_BANNER,
        "doc": NON_CLAIMS_DOC_PATH,
        "software_metrics_are_not_causal": True,
        "section_21_cleared": False,
        "causal_claims": False,
        "items": [
            {
                "id": item["id"],
                "claim": item["claim"],
                "status": item["status"],
            }
            for item in NON_CLAIMS_ITEMS
        ],
    }


def refuse_oversell_flags(
    flags: Mapping[str, Any] | None = None,
    /,
    **kwargs: Any,
) -> None:
    """Fail closed if any flag implies §21 / causal / Mathlib / R3-R4 clearance.

    Call from pilot summary, dry-run, and research entrypoints before emitting
    metrics. Accepts a mapping and/or keyword arguments.
    """
    merged: dict[str, Any] = {}
    if flags is not None:
        merged.update(dict(flags))
    merged.update(kwargs)
    offenders: list[str] = []
    for key, value in merged.items():
        norm = str(key).strip().lower().replace("-", "_")
        if norm in _FORBIDDEN_TRUE_KEYS and value is True:
            offenders.append(norm)
        # Also catch stringy "true" / "cleared" sneak-ins.
        if norm in _FORBIDDEN_TRUE_KEYS and isinstance(value, str):
            if value.strip().lower() in {"true", "yes", "1", "cleared", "passed"}:
                offenders.append(norm)
    if offenders:
        raise OversellClaimError(
            "Refusing oversell flags that imply §21 / causal / Mathlib / R3-R4 "
            f"clearance: {sorted(set(offenders))}. "
            f"See {NON_CLAIMS_DOC_PATH}."
        )


# Partner-scaffold markdown (kept in sync with docs/28).
NON_CLAIMS_MARKDOWN = """# Explicit non-claims

Canonical list: `docs/NON_CLAIMS.md`.

1. **ENGINEERING_SPEC §21 is not passed.** Instrumentation and dry-runs only.
2. **No causal utility / causal TPPR** from warehouse or dry-run software metrics.
3. **No R3/R4 auto-ACCEPT / single-reviewer ACCEPT** (ADR 0003). Quorum path only.
4. **No Mathlib-scale elaborator-complete kernel truth.** Regex-stub is incomplete;
   fixture toolchain is not Mathlib-scale.
5. **M6/M7 training (EPIC-039/040) blocked until §21.** No training entrypoints.
6. **Dry-run / warehouse tests are not a study.** Fixture corpora ≠ prospective review.
7. **Analysis plan is UNFROZEN** until the partner signs and archives a dated copy.
"""
