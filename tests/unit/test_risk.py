from __future__ import annotations

from lpe.evidence.risk import classify_risk
from lpe.models import (
    ArtifactType,
    CandidateDescriptor,
    ChangedDeclaration,
    GeneratorProvenance,
    RiskClass,
)


def make_candidate(declaration: ChangedDeclaration) -> CandidateDescriptor:
    return CandidateDescriptor(
        candidate_id="candidate-risk-test",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="base",
        patch_text="+example",
        claimed_intent="Test risk",
        changed_paths=[declaration.path],
        changed_declarations=[declaration],
        generator=GeneratorProvenance(
            generator_type="human",
            name="test",
        ),
    )


def test_public_definition_signature_change_is_r3() -> None:
    candidate = make_candidate(
        ChangedDeclaration(
            name="Example.x",
            kind=ArtifactType.DEFINITION,
            path="Example/Public.lean",
            signature_changed=True,
            public=True,
        )
    )
    assert classify_risk(candidate) is RiskClass.R3


def test_foundational_change_is_r4() -> None:
    candidate = make_candidate(
        ChangedDeclaration(
            name="Example.Foundation",
            kind=ArtifactType.STRUCTURE,
            path="Example/Foundation.lean",
            signature_changed=True,
            public=True,
            foundational=True,
        )
    )
    assert classify_risk(candidate) is RiskClass.R4


def test_private_helper_is_r1() -> None:
    candidate = make_candidate(
        ChangedDeclaration(
            name="Example.helper",
            kind=ArtifactType.THEOREM,
            path="Example/Internal.lean",
            signature_changed=False,
            public=False,
        )
    )
    assert classify_risk(candidate) is RiskClass.R1
