from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from lpe.models import EvidencePacket, Recommendation

EscalateConclusion = Literal["failure", "neutral", "action_required"]


@dataclass(frozen=True)
class GitHubCheckOutput:
    name: str
    title: str
    summary: str
    text: str
    conclusion: str
    annotations: list[dict[str, str | int]]
    head_sha: str | None = None


def recommendation_to_conclusion(
    recommendation: Recommendation | str,
    *,
    escalate_as: EscalateConclusion = "failure",
) -> str:
    """Map LPE recommendation to GitHub Check conclusion (AUDIT-018).

    Default ``escalate_as=\"failure\"`` is fail-closed for required merge checks.
    Projects that want non-blocking escalate can pass ``escalate_as=\"neutral\"``.
    """
    value = (
        recommendation.value if isinstance(recommendation, Recommendation) else str(recommendation)
    )
    if value == "ACCEPT":
        return "success"
    if value == "REJECT":
        return "failure"
    if value == "ESCALATE":
        return escalate_as
    return "neutral"


def packet_to_github_check(
    packet: EvidencePacket,
    *,
    escalate_as: EscalateConclusion = "failure",
) -> GitHubCheckOutput:
    conclusion = recommendation_to_conclusion(packet.recommendation, escalate_as=escalate_as)

    finding_lines = [f"- [{f.status.value}] {f.check_id}: {f.summary}" for f in packet.findings]
    summary = (
        f"Risk {packet.risk_class.value}; recommendation {packet.recommendation.value}. "
        f"{len(packet.unresolved_uncertainty)} unresolved uncertainties."
    )
    text_parts = [
        f"Packet `{packet.packet_id}` for candidate `{packet.candidate.candidate_id}`",
        "",
        "## Recommendation",
        "",
        *packet.recommendation_reasons,
        "",
        "## Findings",
        "",
        *finding_lines,
    ]
    if packet.review_question:
        text_parts.extend(
            [
                "",
                "## Review question",
                "",
                packet.review_question.question,
            ]
        )

    annotations = [
        {
            "path": str(f.details.get("path", "EVIDENCE.md")),
            "start_line": 1,
            "end_line": 1,
            "annotation_level": "failure" if f.status.value == "FAIL" else "notice",
            "message": f"{f.check_id}: {f.summary}",
        }
        for f in packet.findings
        if f.status.value in {"FAIL", "UNKNOWN", "WARN"}
    ]

    head_sha = packet.candidate.head_commit

    return GitHubCheckOutput(
        name="lean-project-evidence",
        title=f"Evidence: {packet.recommendation.value}",
        summary=summary,
        text="\n".join(text_parts),
        conclusion=conclusion,
        annotations=annotations,
        head_sha=head_sha,
    )


def render_check_payload(
    check: GitHubCheckOutput,
    *,
    head_sha: str | None = None,
) -> dict[str, Any]:
    """Render a GitHub Checks API-shaped payload.

    Prefer an explicit ``head_sha``, then the check's candidate SHA, else a
    clearly labeled unavailable sentinel (never a fake commit that looks real).
    """
    resolved = head_sha or check.head_sha
    if not resolved:
        resolved = "unavailable-sha"
    return {
        "name": check.name,
        "head_sha": resolved,
        "status": "completed",
        "conclusion": check.conclusion,
        "output": {
            "title": check.title,
            "summary": check.summary,
            "text": check.text,
            "annotations": check.annotations,
        },
    }
