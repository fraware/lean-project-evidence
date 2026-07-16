"""M6–M7 / EPIC-039–040 research gates — blocked until ENGINEERING_SPEC §21."""

from __future__ import annotations

from typing import Any


class ResearchGateBlocked(RuntimeError):
    """Raised when a research / training entrypoint is invoked before §21."""


# Gate matrix printed by ``lpe research status`` and doctor.
RESEARCH_GATE_MATRIX: tuple[dict[str, str], ...] = (
    {
        "id": "EPIC-039",
        "milestone": "M6",
        "title": "Learn review routing",
        "status": "BLOCKED",
        "until": "ENGINEERING_SPEC §21 utility gates",
        "shipped": "DeterministicRoutingBaseline scaffold only (no training)",
    },
    {
        "id": "EPIC-040",
        "milestone": "M7",
        "title": "Project-targeted synthesis",
        "status": "BLOCKED",
        "until": "ENGINEERING_SPEC §21 science gates (and M6)",
        "shipped": "SynthesisEvalHarness fixture comparison only (no training)",
    },
    {
        "id": "ADR-0003",
        "milestone": "review",
        "title": "R3/R4 human authority",
        "status": "ACTIVE",
        "until": "future multi-authority protocol (not §21 alone)",
        "shipped": "can_record_acceptance refuses R3/R4 ACCEPT",
    },
    {
        "id": "SECTION-21",
        "milestone": "science",
        "title": "Shadow-pilot + learned-routing clearance",
        "status": "NOT_PASSED",
        "until": "frozen analysis plan + field data + held-out gates",
        "shipped": "instrumentation path only",
    },
)

_BLOCKED_ENTRYPOINTS = frozenset(
    {
        "routing",
        "routing.train",
        "routing.learned",
        "synthesis",
        "synthesis.train",
        "m6",
        "m7",
        "epic-039",
        "epic-040",
        "train",
    }
)


def refuse_research_entrypoint(name: str) -> None:
    """Exit-path guard for CLI / module callers that imply M6–M7 training."""
    key = name.strip().lower().replace("_", ".")
    # Normalize common aliases.
    aliases = {
        "lpe.routing": "routing",
        "lpe.synthesis": "synthesis",
        "learned_routing": "routing.learned",
        "learn_routing": "routing.learned",
    }
    key = aliases.get(key, key)
    if key in _BLOCKED_ENTRYPOINTS or key.startswith("routing.") or key.startswith(
        "synthesis."
    ):
        epic = "EPIC-039/040"
        if "synthesis" in key or key in {"m7", "epic-040"}:
            epic = "EPIC-040"
        elif "routing" in key or key in {"m6", "epic-039"}:
            epic = "EPIC-039"
        raise ResearchGateBlocked(
            f"{epic} blocked until ENGINEERING_SPEC §21. "
            f"Entrypoint {name!r} is not available; training does not exist. "
            "Run `lpe research status` for the gate matrix. "
            "See docs/28_NON_CLAIMS.md."
        )


def format_research_status(*, as_markdown: bool = False) -> str:
    """Human-readable research gate matrix."""
    if as_markdown:
        lines = [
            "# Research gate status",
            "",
            "M6–M7 training entrypoints **do not exist**. EPIC-039/040 remain "
            "BLOCKED until §21.",
            "",
            "| ID | Milestone | Status | Until | Shipped |",
            "| --- | --- | --- | --- | --- |",
        ]
        for row in RESEARCH_GATE_MATRIX:
            lines.append(
                f"| {row['id']} | {row['milestone']} | **{row['status']}** | "
                f"{row['until']} | {row['shipped']} |"
            )
        lines.append("")
        return "\n".join(lines)

    lines = ["research_gate_matrix:"]
    for row in RESEARCH_GATE_MATRIX:
        lines.append(
            f"  - {row['id']} ({row['milestone']}): {row['status']} "
            f"until {row['until']}"
        )
    lines.append("training_entrypoints: none (blocked until §21)")
    return "\n".join(lines)


def research_status_payload() -> dict[str, Any]:
    return {
        "section_21_cleared": False,
        "training_entrypoints_exist": False,
        "m6_m7_blocked_until": "ENGINEERING_SPEC §21",
        "gates": list(RESEARCH_GATE_MATRIX),
        "non_claims_doc": "docs/28_NON_CLAIMS.md",
    }
