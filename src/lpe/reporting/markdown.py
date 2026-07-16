from __future__ import annotations

from typing import Any

from lpe.models import EvidencePacket

# Build logs belong in evidence JSON / side log files; embedding full stdout/stderr
# in Markdown balloons review-packet size without aiding decision review.
_LOG_DETAIL_KEYS = frozenset({"stdout", "stderr"})


def _details_for_markdown(details: dict[str, Any]) -> dict[str, Any]:
    """Omit raw build logs; keep hashes and scalar metadata."""
    rendered: dict[str, Any] = {}
    for key, value in details.items():
        if key in _LOG_DETAIL_KEYS and isinstance(value, str):
            rendered[key] = f"<{len(value.encode('utf-8'))} bytes omitted; see hash fields>"
        else:
            rendered[key] = value
    return rendered


def render_packet(packet: EvidencePacket) -> str:
    lines = [
        f"# Evidence packet {packet.packet_id}",
        "",
        f"- Project: `{packet.project_id}`",
        f"- Run: `{packet.run_id}`",
        f"- Contract hash: `{packet.contract_hash}`",
        f"- Candidate: `{packet.candidate.candidate_id}`",
        f"- Risk: `{packet.risk_class.value}`",
        f"- Hard gate passed: `{packet.hard_gate_passed}`",
        (
            "  - Note: `hard_gate_passed` is true only when every hard-relevant check "
            "is PASS; UNKNOWN on axioms/placeholders/build does **not** mean axiom-safe."
        ),
        f"- Recommendation: **{packet.recommendation.value}**",
        "",
        "## Recommendation reasons",
        "",
    ]
    for reason in packet.recommendation_reasons:
        lines.append(f"- {reason}")

    if packet.unresolved_uncertainty:
        lines.extend(["", "## Unresolved uncertainty", ""])
        for item in packet.unresolved_uncertainty:
            lines.append(f"- {item}")

    lines.extend(["", "## Findings", ""])
    for finding in packet.findings:
        lines.append(
            f"### `{finding.check_id}` ({finding.status.value})",
        )
        lines.append("")
        lines.append(f"- Dimension: `{finding.dimension.value}`")
        lines.append(f"- Severity: `{finding.severity.value}`")
        lines.append(f"- Summary: {finding.summary}")
        lines.append(f"- Finding ID: `{finding.finding_id}`")
        if finding.provenance.command:
            lines.append(f"- Command: `{' '.join(finding.provenance.command)}`")
        lines.append(f"- Input hash: `{finding.provenance.input_hash}`")
        if finding.provenance.output_hash:
            lines.append(f"- Output hash: `{finding.provenance.output_hash}`")
        lines.append(f"- Elapsed ms: `{finding.provenance.elapsed_ms}`")
        if finding.details:
            lines.append(f"- Details: `{_details_for_markdown(finding.details)}`")
        lines.append("")

    if packet.review_question:
        lines.extend(
            [
                "## Review question",
                "",
                f"**{packet.review_question.question}**",
                "",
                packet.review_question.decision_relevance,
                "",
                f"- Required roles: {', '.join(packet.review_question.required_roles)}",
                f"- Estimated minutes: {packet.review_question.estimated_minutes}",
                f"- Answer type: {packet.review_question.answer_type}",
            ]
        )
    return "\n".join(lines) + "\n"
