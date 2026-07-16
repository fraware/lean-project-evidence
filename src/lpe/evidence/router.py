from __future__ import annotations

from lpe.ids import new_id
from lpe.models import (
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    ReviewQuestion,
    RiskClass,
)
from lpe.routing.baseline import (
    DETERMINISTIC_BASELINE_ID,
    DeterministicRoutingBaseline,
)

_BASELINE = DeterministicRoutingBaseline()


def select_review_question(
    findings: list[EvidenceFinding],
    risk_class: RiskClass,
    required_roles: list[str],
    estimated_minutes: int,
) -> ReviewQuestion | None:
    """Select one structured review question using the deterministic baseline.

    ``baseline_id`` is always ``deterministic_baseline.v1`` (no learning). This
    wires the M6 comparison scaffold into production question selection so a
    future §21 held-out study can contrast against an explicit baseline id.
    """
    unresolved = [
        finding
        for finding in findings
        if finding.status in {FindingStatus.UNKNOWN, FindingStatus.WARN}
    ]
    if not unresolved and risk_class not in {RiskClass.R3, RiskClass.R4}:
        return None

    routing = _BASELINE.route(
        unresolved_dimensions=[finding.dimension.value for finding in unresolved]
    )
    priority_rank = {
        name: index for index, name in enumerate(routing.question_priority)
    }
    unresolved.sort(
        key=lambda finding: priority_rank.get(finding.dimension.value, 99)
    )
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
        baseline_id=routing.baseline_id or DETERMINISTIC_BASELINE_ID,
    )
