from __future__ import annotations

from lpe.ids import new_id
from lpe.models import (
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    ReviewQuestion,
    RiskClass,
)


PRIORITY = {
    EvidenceDimension.SEMANTIC: 0,
    EvidenceDimension.REPOSITORY: 1,
    EvidenceDimension.DOWNSTREAM: 2,
    EvidenceDimension.KERNEL: 3,
    EvidenceDimension.PERSISTENCE: 4,
    EvidenceDimension.UNCERTAINTY: 5,
}


def select_review_question(
    findings: list[EvidenceFinding],
    risk_class: RiskClass,
    required_roles: list[str],
    estimated_minutes: int,
) -> ReviewQuestion | None:
    unresolved = [
        finding
        for finding in findings
        if finding.status in {FindingStatus.UNKNOWN, FindingStatus.WARN}
    ]
    if not unresolved and risk_class not in {RiskClass.R3, RiskClass.R4}:
        return None

    unresolved.sort(key=lambda finding: PRIORITY[finding.dimension])
    finding = unresolved[0] if unresolved else None

    if finding is not None and finding.dimension is EvidenceDimension.SEMANTIC:
        question = (
            "Does the candidate preserve the intended mathematical object, assumptions, "
            "and level of generality recorded in the project contract?"
        )
        relevance = "Semantic acceptance controls whether the artifact can count as trusted progress."
    elif finding is not None and finding.dimension is EvidenceDimension.REPOSITORY:
        question = (
            "Does the candidate use the repository's intended abstraction and belong in "
            "the proposed public API location?"
        )
        relevance = "Repository fitness controls acceptance and future maintenance cost."
    elif finding is not None and finding.dimension is EvidenceDimension.DOWNSTREAM:
        question = (
            "Is the available downstream evidence sufficient to conclude that the candidate "
            "enables the declared project obligation?"
        )
        relevance = "Downstream utility controls critical-path credit."
    else:
        question = (
            "Should this high-risk candidate be accepted as expressing the project's intended "
            "mathematics and repository architecture?"
        )
        relevance = "Project policy reserves high-risk semantic decisions for an authorized reviewer."

    return ReviewQuestion(
        question_id=new_id("question"),
        question=question,
        decision_relevance=relevance,
        answer_type="accept | reject | request_repair | indeterminate",
        required_roles=required_roles,
        estimated_minutes=estimated_minutes,
        supporting_finding_ids=[finding.finding_id] if finding else [],
    )
