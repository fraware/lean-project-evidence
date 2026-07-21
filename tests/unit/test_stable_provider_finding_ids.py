"""Stable finding IDs from semantic/downstream providers (CLOSURE-011 polish)."""

from __future__ import annotations

from datetime import datetime, timezone

from lpe.models import EvidenceBasis, EvidenceCoverage, EvidenceDimension, FindingStatus, Severity
from lpe.providers import downstream as downstream_mod
from lpe.providers import semantic as semantic_mod
from lpe.workspace.manager import make_stable_finding_id


def test_semantic_provider_finding_id_is_stable() -> None:
    now = datetime.now(timezone.utc)
    details = {"subject": "Foo.bar", "kind": "unit-test"}
    first = semantic_mod._finding(
        check_id="semantic.statement_diff",
        dimension=EvidenceDimension.SEMANTIC,
        status=FindingStatus.PASS,
        severity=Severity.INFO,
        summary="stable id",
        details=details,
        started=now,
        finished=now,
    )
    second = semantic_mod._finding(
        check_id="semantic.statement_diff",
        dimension=EvidenceDimension.SEMANTIC,
        status=FindingStatus.PASS,
        severity=Severity.INFO,
        summary="stable id",
        details=details,
        started=now,
        finished=now,
    )
    expected = make_stable_finding_id(
        check_id="semantic.statement_diff",
        dimension=EvidenceDimension.SEMANTIC,
        details=details,
        check_version="0.2.0",
    )
    assert first.finding_id == second.finding_id == expected
    assert first.finding_id.startswith("finding_semantic_statement_diff_")
    assert first.finding_id.endswith("_0_2_0")


def test_downstream_provider_finding_id_is_stable() -> None:
    now = datetime.now(timezone.utc)
    details = {"suite": "successors", "case": "a"}
    finding = downstream_mod._finding(
        check_id="downstream.successor_suite",
        status=FindingStatus.UNKNOWN,
        severity=Severity.L1,
        summary="stable id",
        details=details,
        started=now,
        finished=now,
        basis=EvidenceBasis.EXECUTED_TEST,
        coverage=EvidenceCoverage(
            requested_subject_count=1,
            evaluated_subject_count=1,
            complete_for_declared_scope=True,
        ),
    )
    expected = make_stable_finding_id(
        check_id="downstream.successor_suite",
        dimension=EvidenceDimension.DOWNSTREAM,
        details=details,
        check_version="0.2.0",
    )
    assert finding.finding_id == expected
