"""Evidence packet / finding migration 0.1.0 → 0.2.0 (CLOSURE-016).

Never invents acceptance or persistence. Ambiguous records are marked
``LEGACY_UNRESOLVED``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from lpe.models import (
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    EvidenceBasis,
    EvidenceCoverage,
    EvidenceFinding,
    EvidencePacket,
    FindingStatus,
    validate_supported_schema_version,
)

LEGACY_UNRESOLVED = "LEGACY_UNRESOLVED"


def migrate_finding_0_1_to_0_2(raw: dict[str, Any]) -> dict[str, Any]:
    """Upgrade a finding dict from 0.1.0 shape to 0.2.0 fields.

    Does not invent PASS/acceptance. Missing basis/coverage → explicit legacy markers.
    """
    out = deepcopy(raw)
    status = out.get("status")
    if "basis" not in out or out["basis"] is None:
        out["basis"] = None
        out.setdefault("details", {})
        if isinstance(out["details"], dict):
            out["details"].setdefault("migration", {})
            out["details"]["migration"]["basis"] = LEGACY_UNRESOLVED
    if "coverage" not in out or out["coverage"] is None:
        # Incomplete coverage must not silent-PASS after migration.
        complete = status in {
            FindingStatus.NOT_APPLICABLE.value,
            FindingStatus.FAIL.value,
            FindingStatus.WARN.value,
            FindingStatus.UNKNOWN.value,
        }
        if status == FindingStatus.PASS.value:
            # Historical PASS without coverage becomes UNKNOWN rather than invented completeness.
            out["status"] = FindingStatus.UNKNOWN.value
            out.setdefault("details", {})
            if isinstance(out["details"], dict):
                out["details"].setdefault("migration", {})
                out["details"]["migration"]["pass_without_coverage"] = LEGACY_UNRESOLVED
            complete = False
        out["coverage"] = EvidenceCoverage(
            requested_subject_count=0,
            evaluated_subject_count=0,
            complete_for_declared_scope=complete,
            exclusion_reasons=[LEGACY_UNRESOLVED] if not complete else [],
            allows_partial_pass=False,
        ).model_dump()
    out.setdefault("subject_refs", [])
    out.setdefault("artifact_refs", [])
    out.setdefault("payload", out.get("details"))
    out.setdefault("required_basis", None)
    # ProvenanceV2 fields remain optional; do not invent digests.
    prov = out.get("provenance")
    if isinstance(prov, dict):
        prov.setdefault("producer_id", prov.get("tool"))
        prov.setdefault("producer_version", prov.get("tool_version"))
        for key in (
            "run_manifest_hash",
            "image_digest",
            "toolchain_hash",
            "random_seed",
        ):
            prov.setdefault(key, None)
        prov.setdefault("environment_keys_forwarded", [])
        prov.setdefault("input_artifact_hashes", [])
        prov.setdefault("output_artifact_hashes", [])
    return out


def migrate_packet_0_1_to_0_2(raw: dict[str, Any]) -> dict[str, Any]:
    """Migrate a golden 0.1.0 evidence packet dict to 0.2.0.

    Never invents acceptance/persistence events. Marks unresolved fields explicitly.
    """
    out = deepcopy(raw)
    from_version = str(out.get("schema_version") or "")
    if from_version not in SUPPORTED_SCHEMA_VERSIONS and from_version != "0.1.0":
        raise ValueError(f"cannot migrate unsupported schema_version {from_version!r}")
    validate_supported_schema_version("0.1.0")

    out["schema_version"] = SCHEMA_VERSION
    findings = out.get("findings")
    if isinstance(findings, list):
        out["findings"] = [
            migrate_finding_0_1_to_0_2(f) if isinstance(f, dict) else f for f in findings
        ]

    # Do not invent acceptance / persistence — only mark absence.
    out.setdefault("recommendation_policy_id", LEGACY_UNRESOLVED)
    details_note = {
        "migration": {
            "from": from_version or "0.1.0",
            "to": SCHEMA_VERSION,
            "acceptance": LEGACY_UNRESOLVED,
            "persistence": LEGACY_UNRESOLVED,
            "note": "migration never invents acceptance or persistence records",
        }
    }
    # Attach migration note on unresolved_uncertainty without inventing gate outcomes.
    uncertainty = list(out.get("unresolved_uncertainty") or [])
    marker = f"migration:{LEGACY_UNRESOLVED}:acceptance+persistence"
    if marker not in uncertainty:
        uncertainty.append(marker)
    out["unresolved_uncertainty"] = uncertainty
    out.setdefault("_migration", details_note["migration"])
    # Strip private helper before validation if present — keep in details via uncertainty only.
    out.pop("_migration", None)
    return out


def load_packet_migrating(raw: dict[str, Any]) -> EvidencePacket:
    """Validate a packet, migrating 0.1.0 payloads to 0.2.0 when needed."""
    version = str(raw.get("schema_version") or "")
    if version == "0.1.0":
        raw = migrate_packet_0_1_to_0_2(raw)
    elif version == SCHEMA_VERSION:
        pass
    else:
        validate_supported_schema_version(version)
    return EvidencePacket.model_validate(raw)


def assert_finding_pass_rules(finding: EvidenceFinding) -> None:
    """Runtime guard mirroring model validators for provider tests."""
    if finding.status is FindingStatus.PASS:
        if finding.coverage is not None and not finding.coverage.complete_for_declared_scope:
            if not finding.coverage.allows_partial_pass:
                raise ValueError("incomplete coverage cannot silent-PASS")
        if (
            finding.basis is not None
            and finding.required_basis is not None
            and finding.basis is not EvidenceBasis.HUMAN_ATTESTED
        ):
            from lpe.models import basis_satisfies

            if not basis_satisfies(finding.basis, finding.required_basis):
                raise ValueError("weaker basis cannot satisfy stronger required basis")
