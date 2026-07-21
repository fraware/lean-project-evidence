"""AUDIT-003 / AUDIT-020: axiom gate honesty on regex-stub extraction."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from lpe.contract.loader import load_contract
from lpe.evidence.compiler import _check_axioms, compile_evidence
from lpe.lean.extractor import LeanExtractionResult, REGEX_STUB_EXTRACTOR
from lpe.models import CandidateDescriptor, FindingStatus, GeneratorProvenance


def test_axiom_unknown_never_pass_on_regex_stub_empty_axioms(
    example_project: Path,
) -> None:
    """Invariant: incomplete regex-stub with empty axioms_used → UNKNOWN, never PASS."""
    contract = load_contract(example_project)
    extraction = LeanExtractionResult(
        axioms_used=[],
        extractor=REGEX_STUB_EXTRACTOR,
    )
    finding = _check_axioms(contract, extraction, started=datetime.now(timezone.utc))
    assert finding.status is FindingStatus.UNKNOWN
    assert finding.status is not FindingStatus.PASS
    assert finding.check_id == "lean.prohibited_axioms"


def test_axiom_unknown_on_legacy_regex_extractor_id(example_project: Path) -> None:
    contract = load_contract(example_project)
    extraction = LeanExtractionResult(
        axioms_used=[],
        extractor="lean.regex-extractor",
    )
    finding = _check_axioms(contract, extraction, started=datetime.now(timezone.utc))
    assert finding.status is FindingStatus.UNKNOWN


def test_compile_axiom_gate_never_pass_with_regex_stub(
    example_project: Path, example_candidate: CandidateDescriptor
) -> None:
    """Invariant: end-to-end skip-build compile never PASS axiom gate on stub path."""
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is not FindingStatus.PASS
    assert axiom.status in {FindingStatus.UNKNOWN, FindingStatus.FAIL}
    assert packet.hard_gate_passed is False


def test_prohibited_axiom_still_fails_on_regex_stub(example_project: Path) -> None:
    """Invariant: explicit prohibited axioms FAIL even when extractor is incomplete."""
    contract = load_contract(example_project)
    extraction = LeanExtractionResult(
        axioms_used=["Definitely.Prohibited.Axiom"],
        extractor=REGEX_STUB_EXTRACTOR,
    )
    finding = _check_axioms(contract, extraction, started=datetime.now(timezone.utc))
    assert finding.status is FindingStatus.FAIL


def test_hard_gate_false_when_axiom_unknown(example_project: Path) -> None:
    candidate = CandidateDescriptor(
        candidate_id="cand-axiom-hard",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="# docs\n",
        claimed_intent="docs",
        changed_paths=["README.md"],
        changed_declarations=[],
        generator=GeneratorProvenance(generator_type="test", name="test", version="0"),
    )
    packet = compile_evidence(example_project, candidate, skip_build=True)
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    if axiom.status is FindingStatus.UNKNOWN:
        assert packet.hard_gate_passed is False
