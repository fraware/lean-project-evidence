from __future__ import annotations

from lpe.models import ArtifactType, CandidateDescriptor, RiskClass


def classify_risk(candidate: CandidateDescriptor) -> RiskClass:
    if not candidate.changed_declarations:
        if any(
            path.endswith((".lean", "lakefile.lean", "lake-manifest.json"))
            for path in candidate.changed_paths
        ):
            return RiskClass.R4
        return RiskClass.R0

    risk = RiskClass.R0
    rank = {RiskClass.R0: 0, RiskClass.R1: 1, RiskClass.R2: 2, RiskClass.R3: 3, RiskClass.R4: 4}

    for declaration in candidate.changed_declarations:
        if declaration.foundational:
            candidate_risk = RiskClass.R4
        elif declaration.kind in {
            ArtifactType.DEFINITION,
            ArtifactType.STRUCTURE,
            ArtifactType.CLASS,
            ArtifactType.INSTANCE,
            ArtifactType.ABBREV,
        } and (declaration.signature_changed or declaration.public):
            candidate_risk = RiskClass.R3
        elif declaration.kind is ArtifactType.THEOREM and declaration.signature_changed:
            candidate_risk = RiskClass.R3
        elif declaration.public:
            candidate_risk = RiskClass.R2
        else:
            candidate_risk = RiskClass.R1

        if rank[candidate_risk] > rank[risk]:
            risk = candidate_risk

    if any(
        path.endswith(("lakefile.lean", "lake-manifest.json", "lean-toolchain"))
        for path in candidate.changed_paths
    ):
        risk = RiskClass.R4

    return risk
