"""Evidence migration fail-closed guards (CLOSURE-016)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from lpe.evidence.migration import (
    assert_finding_pass_rules,
    load_packet_migrating,
    migrate_packet_0_1_to_0_2,
)
from lpe.models import (
    EvidenceBasis,
    EvidenceCoverage,
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    Provenance,
    Severity,
)


def test_assert_finding_pass_rules_incomplete_coverage() -> None:
    now = datetime(2026, 7, 21, tzinfo=UTC)
    prov = Provenance(
        tool="t",
        tool_version="1",
        input_hash="a" * 64,
        started_at=now,
        finished_at=now,
        elapsed_ms=1,
    )
    bypassed = EvidenceFinding.model_construct(
        finding_id="f1",
        check_id="c1",
        check_version="0.2.0",
        dimension=EvidenceDimension.KERNEL,
        status=FindingStatus.PASS,
        severity=Severity.INFO,
        summary="x",
        details={},
        provenance=prov,
        basis=EvidenceBasis.HEURISTIC_RETRIEVAL,
        coverage=EvidenceCoverage(
            requested_subject_count=2,
            evaluated_subject_count=1,
            complete_for_declared_scope=False,
            allows_partial_pass=False,
        ),
        subject_refs=[],
        payload=None,
        artifact_refs=[],
        required_basis=EvidenceBasis.KERNEL_CHECKED,
        snapshot_fingerprint=None,
    )
    with pytest.raises(ValueError, match="incomplete coverage"):
        assert_finding_pass_rules(bypassed)
    with pytest.raises(ValueError, match="weaker basis|cannot satisfy"):
        bypassed2 = bypassed.model_copy(
            update={
                "coverage": EvidenceCoverage(
                    requested_subject_count=1,
                    evaluated_subject_count=1,
                    complete_for_declared_scope=True,
                )
            }
        )
        assert_finding_pass_rules(bypassed2)


def test_migrate_packet_rejects_unsupported_and_load_paths() -> None:
    with pytest.raises(ValueError, match="cannot migrate unsupported"):
        migrate_packet_0_1_to_0_2({"schema_version": "9.9.9", "findings": []})
    with pytest.raises(ValueError):
        load_packet_migrating({"schema_version": "9.9.9"})
