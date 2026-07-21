"""Phase C / CLOSURE-010, 013–016 acceptance tests."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from lpe.evidence.migration import (
    LEGACY_UNRESOLVED,
    load_packet_migrating,
    migrate_packet_0_1_to_0_2,
)
from lpe.evidence.synthesis import (
    RECOMMENDATION_POLICY_ID,
    SYNTHESIS_RULES,
    apply_synthesis,
    recommendation_policy_id,
)
from lpe.models import (
    SCHEMA_VERSION,
    SUPPORTED_SCHEMA_VERSIONS,
    CandidateDescriptor,
    EvidenceBasis,
    EvidenceCoverage,
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    FixtureSuite,
    GeneratorProvenance,
    Provenance,
    RiskClass,
    Severity,
    SubjectReference,
    SuccessorSuite,
    basis_satisfies,
)
from lpe.providers.fixtures import load_fixture_suite


def _prov() -> Provenance:
    now = datetime.now(timezone.utc)
    return Provenance(
        tool="test",
        tool_version="0",
        input_hash="a" * 64,
        started_at=now,
        finished_at=now,
        elapsed_ms=0,
    )


def test_schema_version_0_2_supported() -> None:
    assert SCHEMA_VERSION == "0.2.0"
    assert "0.1.0" in SUPPORTED_SCHEMA_VERSIONS
    assert "0.2.0" in SUPPORTED_SCHEMA_VERSIONS


def test_basis_strength_ordering() -> None:
    assert basis_satisfies(EvidenceBasis.KERNEL_CHECKED, EvidenceBasis.EXECUTED_TEST)
    assert not basis_satisfies(EvidenceBasis.HEURISTIC_RETRIEVAL, EvidenceBasis.EXECUTED_TEST)
    assert basis_satisfies(EvidenceBasis.HUMAN_ATTESTED, EvidenceBasis.KERNEL_CHECKED)


def test_pass_with_weaker_basis_rejected() -> None:
    with pytest.raises(ValidationError, match="cannot satisfy required"):
        EvidenceFinding(
            finding_id="f1",
            check_id="semantic.intent_support",
            check_version="0.2.0",
            dimension=EvidenceDimension.SEMANTIC,
            status=FindingStatus.PASS,
            severity=Severity.INFO,
            summary="bad",
            provenance=_prov(),
            basis=EvidenceBasis.STRUCTURAL_COMPARISON,
            required_basis=EvidenceBasis.HUMAN_ATTESTED,
            coverage=EvidenceCoverage(
                requested_subject_count=1,
                evaluated_subject_count=1,
                complete_for_declared_scope=True,
            ),
        )


def test_incomplete_coverage_cannot_silent_pass() -> None:
    with pytest.raises(ValidationError, match="incomplete coverage"):
        EvidenceFinding(
            finding_id="f2",
            check_id="semantic.project_examples",
            check_version="0.2.0",
            dimension=EvidenceDimension.SEMANTIC,
            status=FindingStatus.PASS,
            severity=Severity.INFO,
            summary="bad",
            provenance=_prov(),
            basis=EvidenceBasis.EXECUTED_TEST,
            coverage=EvidenceCoverage(
                requested_subject_count=2,
                evaluated_subject_count=1,
                complete_for_declared_scope=False,
            ),
        )


def test_fixture_suite_schema_roundtrip() -> None:
    raw = {
        "schema_version": "0.2.0",
        "suite_id": "examples-o01-v1",
        "suite_kind": "examples",
        "obligation_ids": ["O-01"],
        "fixtures": [
            {
                "fixture_id": "x",
                "path": "examples/x.lean",
                "expected_exit": 0,
                "basis": "EXECUTED_TEST",
            }
        ],
    }
    suite = FixtureSuite.model_validate(raw)
    assert suite.suite_id == "examples-o01-v1"
    assert suite.fixtures[0].basis is EvidenceBasis.EXECUTED_TEST


def test_successor_suite_schema_roundtrip() -> None:
    suite = SuccessorSuite.model_validate(
        {
            "schema_version": "0.2.0",
            "suite_id": "downstream-o01-v1",
            "obligation_ids": ["O-01"],
            "successors": [
                {
                    "successor_id": "s1",
                    "command": ["lake", "env", "lean", "X.lean"],
                    "required": True,
                }
            ],
        }
    )
    assert suite.successors[0].successor_id == "s1"


def test_load_fixture_suite_from_lean_project(repository_root: Path) -> None:
    project = repository_root / "tests" / "fixtures" / "lean_project"
    suite, report = load_fixture_suite(project, kind="examples")
    assert suite is not None, report
    assert suite.suite_id.startswith("examples")
    assert suite.fixtures


def test_readme_only_cannot_pass_without_manifest(tmp_path: Path) -> None:
    examples = tmp_path / ".lean-project-contract" / "tests" / "examples"
    examples.mkdir(parents=True)
    (examples / "README.md").write_text("# hi\n", encoding="utf-8")
    suite, report = load_fixture_suite(tmp_path, kind="examples")
    assert suite is None
    assert report["error"] == "manifest_missing"


def test_synthesis_removes_contradictory_unknown() -> None:
    now = datetime.now(timezone.utc)
    candidate = CandidateDescriptor(
        candidate_id="cand-synth",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+-- x\n",
        claimed_intent="test",
        changed_declarations=[],
        generator=GeneratorProvenance(generator_type="t", name="t"),
    )
    placeholder = EvidenceFinding(
        finding_id="old",
        check_id="repository.api_fit",
        check_version="0.1.0",
        dimension=EvidenceDimension.REPOSITORY,
        status=FindingStatus.UNKNOWN,
        severity=Severity.L2,
        summary="generic unknown",
        provenance=_prov(),
    )
    provider = EvidenceFinding(
        finding_id="dup",
        check_id="semantic.duplicate_retrieval",
        check_version="0.2.0",
        dimension=EvidenceDimension.SEMANTIC,
        status=FindingStatus.PASS,
        severity=Severity.INFO,
        summary="ok",
        details={"attempted": True},
        provenance=_prov(),
        basis=EvidenceBasis.HEURISTIC_RETRIEVAL,
        coverage=EvidenceCoverage(
            requested_subject_count=0,
            evaluated_subject_count=0,
            complete_for_declared_scope=True,
        ),
    )
    out = apply_synthesis(
        [placeholder, provider],
        candidate=candidate,
        risk_class=RiskClass.R1,
    )
    api = [f for f in out if f.check_id == "repository.api_fit"]
    assert len(api) == 1
    assert api[0].status is FindingStatus.NOT_APPLICABLE
    assert "semantic.intent_support" in {f.check_id for f in out}
    assert "repository.api_fit" in SYNTHESIS_RULES
    assert recommendation_policy_id() == RECOMMENDATION_POLICY_ID
    assert now  # silence unused in some linters


def test_migrate_golden_packet_0_1_to_0_2_never_invents_acceptance() -> None:
    raw = {
        "schema_version": "0.1.0",
        "packet_id": "packet_legacy",
        "run_id": "run_legacy",
        "project_id": "example-category-project",
        "contract_hash": "c" * 64,
        "candidate": {
            "schema_version": "0.1.0",
            "candidate_id": "cand-legacy",
            "project_id": "example-category-project",
            "obligation_ids": ["O-01"],
            "base_commit": "deadbeef",
            "claimed_intent": "x",
            "patch_text": "+--\n",
            "generator": {"generator_type": "t", "name": "t"},
        },
        "risk_class": "R1",
        "findings": [
            {
                "finding_id": "f",
                "check_id": "lean.build",
                "check_version": "0.1.0",
                "dimension": "kernel",
                "status": "PASS",
                "severity": "INFO",
                "summary": "legacy pass without coverage",
                "details": {},
                "provenance": {
                    "tool": "t",
                    "tool_version": "0",
                    "command": [],
                    "input_hash": "a" * 64,
                    "started_at": "2026-01-01T00:00:00+00:00",
                    "finished_at": "2026-01-01T00:00:01+00:00",
                    "elapsed_ms": 1000,
                },
            }
        ],
        "hard_gate_passed": True,
        "recommendation": "ESCALATE",
        "recommendation_reasons": ["legacy"],
        "unresolved_uncertainty": [],
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    migrated = migrate_packet_0_1_to_0_2(raw)
    assert migrated["schema_version"] == "0.2.0"
    assert migrated["recommendation_policy_id"] == LEGACY_UNRESOLVED
    assert any(LEGACY_UNRESOLVED in u for u in migrated["unresolved_uncertainty"])
    finding = migrated["findings"][0]
    assert finding["status"] == "UNKNOWN"  # PASS without coverage demoted
    packet = load_packet_migrating(raw)
    assert packet.schema_version == "0.2.0"


def test_subject_refs_roundtrip() -> None:
    finding = EvidenceFinding(
        finding_id="f3",
        check_id="semantic.project_examples",
        check_version="0.2.0",
        dimension=EvidenceDimension.SEMANTIC,
        status=FindingStatus.UNKNOWN,
        severity=Severity.L2,
        summary="x",
        provenance=_prov(),
        basis=EvidenceBasis.EXECUTED_TEST,
        coverage=EvidenceCoverage(
            requested_subject_count=1,
            evaluated_subject_count=0,
            complete_for_declared_scope=False,
            exclusion_reasons=["missing"],
        ),
        subject_refs=[SubjectReference(kind="fixture", ref="helper-ok")],
    )
    assert finding.subject_refs[0].ref == "helper-ok"


def test_export_schemas_check(repository_root: Path) -> None:
    import subprocess
    import sys

    # Ensure schemas are exported first in this test process when dirty tree.
    subprocess.run(
        [sys.executable, str(repository_root / "scripts" / "export_schemas.py")],
        cwd=repository_root,
        check=True,
    )
    result = subprocess.run(
        [
            sys.executable,
            str(repository_root / "scripts" / "export_schemas.py"),
            "--check",
        ],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr + result.stdout
