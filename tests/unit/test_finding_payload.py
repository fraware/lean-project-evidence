"""Typed FindingPayload discriminated union tests (CLOSURE-010)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from lpe.evidence.payloads import (
    ExecutedCheckFindingPayload,
    OpaqueFindingPayload,
    StructuralDiffFindingPayload,
    SynthesisFindingPayload,
    executed_check_payload,
    finding_payload_as_dict,
    opaque_finding_payload,
    parse_finding_payload,
    structural_diff_payload,
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


def _prov() -> Provenance:
    now = datetime(2026, 7, 21, tzinfo=UTC)
    return Provenance(
        tool="test",
        tool_version="0.0.1",
        input_hash="a" * 64,
        started_at=now,
        finished_at=now,
        elapsed_ms=1,
    )


def test_parse_bare_dict_preserved() -> None:
    raw = {"exit_code": 0, "note": "legacy"}
    parsed = parse_finding_payload(raw)
    assert parsed == raw
    assert finding_payload_as_dict(parsed) == raw


def test_parse_typed_synthesis() -> None:
    typed = parse_finding_payload(
        {
            "payload_type": "SynthesisFindingPayload",
            "synthesis_rule": "repository.api_fit",
            "source_check_ids": ["semantic.statement_diff"],
            "notes": ["n1"],
            "details": {"k": 1},
        }
    )
    assert isinstance(typed, SynthesisFindingPayload)
    assert typed.synthesis_rule == "repository.api_fit"
    dumped = finding_payload_as_dict(typed)
    assert dumped is not None
    assert dumped["payload_type"] == "SynthesisFindingPayload"


def test_parse_rejects_unknown_discriminator() -> None:
    with pytest.raises(ValidationError):
        parse_finding_payload({"payload_type": "NotARealPayload"})


def test_parse_rejects_non_mapping() -> None:
    with pytest.raises(TypeError, match="unsupported finding payload"):
        parse_finding_payload(["not", "a", "dict"])
    assert finding_payload_as_dict(None) is None


def test_payload_helpers_construct_variants() -> None:
    opaque = opaque_finding_payload({"k": 1})
    assert opaque.data["k"] == 1
    structural = structural_diff_payload({"compared": [{"name": "A.b"}], "note": "x"})
    assert structural.changed_names == ["A.b"]
    executed = executed_check_payload(
        "lean.build",
        {"exit_code": 0, "timed_out": False},
    )
    assert executed.exit_code == 0
    assert executed.timed_out is False


def test_evidence_finding_accepts_typed_and_bare() -> None:
    bare = EvidenceFinding(
        finding_id="f1",
        check_id="kernel.build",
        check_version="0.2.0",
        dimension=EvidenceDimension.KERNEL,
        status=FindingStatus.PASS,
        severity=Severity.INFO,
        summary="ok",
        provenance=_prov(),
        basis=EvidenceBasis.EXECUTED_TEST,
        coverage=EvidenceCoverage(
            requested_subject_count=1,
            evaluated_subject_count=1,
            complete_for_declared_scope=True,
        ),
        payload={"exit_code": 0},
    )
    assert bare.payload == {"exit_code": 0}

    typed = EvidenceFinding(
        finding_id="f2",
        check_id="repository.api_fit",
        check_version="synthesis.v1",
        dimension=EvidenceDimension.REPOSITORY,
        status=FindingStatus.PASS,
        severity=Severity.INFO,
        summary="synth",
        provenance=_prov(),
        basis=EvidenceBasis.STRUCTURAL_COMPARISON,
        coverage=EvidenceCoverage(
            requested_subject_count=1,
            evaluated_subject_count=1,
            complete_for_declared_scope=True,
        ),
        payload=SynthesisFindingPayload(
            synthesis_rule="repository.api_fit",
            source_check_ids=["semantic.statement_diff"],
        ),
    )
    assert isinstance(typed.payload, SynthesisFindingPayload)

    structural = StructuralDiffFindingPayload(
        changed_names=["Foo.bar"],
        details={"kind": "theorem"},
    )
    opaque = OpaqueFindingPayload(data={"x": 1})
    executed = ExecutedCheckFindingPayload(check_id="downstream.suite", exit_code=0)
    assert opaque.data["x"] == 1
    assert structural.changed_names == ["Foo.bar"]
    assert executed.exit_code == 0
