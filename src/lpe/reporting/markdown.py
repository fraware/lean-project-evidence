from __future__ import annotations

from typing import Any

from lpe.lean.extractor import REGEX_STUB_EXTRACTOR
from lpe.models import EvidencePacket

# Build logs belong in evidence JSON / side log files; embedding full stdout/stderr
# in Markdown balloons review-packet size without aiding decision review.
_LOG_DETAIL_KEYS = frozenset({"stdout", "stderr"})

REGEX_STUB_PACKET_BANNER = (
    "> **EXTRACTOR HONESTY:** This packet used the **regex-stub** extractor "
    "(lexical AST-lite). Kernel / axiom / impact findings are **incomplete** and "
    "must not be treated as elaborator axiom closure or Mathlib-scale truth. "
    "See `docs/NON_CLAIMS.md`."
)


def _details_for_markdown(details: dict[str, Any]) -> dict[str, Any]:
    """Omit raw build logs; keep hashes and scalar metadata."""
    rendered: dict[str, Any] = {}
    for key, value in details.items():
        if key in _LOG_DETAIL_KEYS and isinstance(value, str):
            rendered[key] = f"<{len(value.encode('utf-8'))} bytes omitted; see hash fields>"
        else:
            rendered[key] = value
    return rendered


def _packet_uses_regex_stub(packet: EvidencePacket) -> bool:
    """True when any finding provenance/details reports the regex-stub extractor."""
    for finding in packet.findings:
        extractor = finding.details.get("extractor")
        if extractor is None:
            extractor = finding.provenance.provider_metadata.get("extractor")
        if extractor is None:
            continue
        text = str(extractor).lower()
        if text == REGEX_STUB_EXTRACTOR or "regex" in text:
            return True
    return False


def render_packet(packet: EvidencePacket) -> str:
    lines = [
        f"# Evidence packet {packet.packet_id}",
        "",
    ]
    if _packet_uses_regex_stub(packet):
        lines.extend([REGEX_STUB_PACKET_BANNER, ""])
    identity = [
        f"- Project: `{packet.project_id}`",
        f"- Run: `{packet.run_id}`",
        f"- Contract hash: `{packet.contract_hash}`",
        f"- Candidate: `{packet.candidate.candidate_id}`",
    ]
    if packet.evidence_fingerprint:
        identity.append(f"- Evidence fingerprint: `{packet.evidence_fingerprint}`")
    if packet.ledger_seal_tip:
        identity.append(f"- Ledger seal tip: `{packet.ledger_seal_tip}`")
    identity.extend(
        [
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
    )
    lines.extend(identity)
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
                f"- Routing baseline_id: `{packet.review_question.baseline_id}`",
            ]
        )
    return "\n".join(lines) + "\n"
