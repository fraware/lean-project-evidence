from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lpe.contract.loader import load_contract
from lpe.evidence.compiler import HostExecutionRefusedError, compile_evidence
from lpe.execution.sandbox import DockerSandboxExecutor
from lpe.git.candidate import enrich_candidate_from_git
from lpe.git.diff import GitError
from lpe.lean.extractor import LeanExtractionResult
from lpe.models import (
    ArtifactType,
    CandidateDescriptor,
    ChangedDeclaration,
    FindingStatus,
    GeneratorProvenance,
    Recommendation,
)


def _generator() -> GeneratorProvenance:
    return GeneratorProvenance(
        generator_type="test",
        name="test",
        version="0",
    )


def _init_git(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.org"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _commit_all(repo: Path, message: str) -> str:
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _seed_contract(repo: Path, example_project: Path) -> None:
    import shutil

    shutil.copytree(
        example_project / ".lean-project-contract",
        repo / ".lean-project-contract",
    )


# --- AUDIT-001 ---


def test_host_exec_refused_without_insecure_flag(
    tmp_path: Path,
    example_project: Path,
    example_candidate: CandidateDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))
    with pytest.raises(HostExecutionRefusedError, match="insecure-host-exec"):
        compile_evidence(
            example_project,
            example_candidate,
            skip_build=False,
            insecure_host_exec=False,
        )


def test_host_exec_allowed_with_insecure_flag(
    tmp_path: Path,
    example_project: Path,
    example_candidate: CandidateDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With network_policy=allow, --insecure-host-exec may use host subprocess."""
    import shutil
    import yaml

    project = tmp_path / "proj"
    shutil.copytree(example_project, project)
    path = project / ".lean-project-contract" / "project.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["execution"]["network_policy"] = "allow"
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))

    class FakeExecutor:
        def verify_build(self, **kwargs):  # type: ignore[no-untyped-def]
            from lpe.execution.protocol import ExecutionResult

            return ExecutionResult(
                command=("lake", "build"),
                cwd=kwargs["repository"],
                exit_code=0,
                stdout="",
                stderr="",
                elapsed_ms=1,
                timed_out=False,
            )

    monkeypatch.setattr(
        "lpe.evidence.compiler.SubprocessLeanExecutor",
        FakeExecutor,
    )
    packet = compile_evidence(
        project,
        example_candidate,
        skip_build=False,
        insecure_host_exec=True,
    )
    build = next(f for f in packet.findings if f.check_id == "lean.build")
    assert build.status is FindingStatus.PASS


def test_host_exec_refused_when_network_policy_deny(
    example_project: Path,
    example_candidate: CandidateDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lpe.evidence.compiler import NetworkPolicyError

    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))
    with pytest.raises(NetworkPolicyError, match="network_policy"):
        compile_evidence(
            example_project,
            example_candidate,
            skip_build=False,
            insecure_host_exec=True,
        )


# --- AUDIT-004 / AUDIT-015 ---


def test_enrich_rejects_null_oid(tmp_path: Path, example_project: Path) -> None:
    _init_git(tmp_path)
    (tmp_path / "README").write_text("x\n", encoding="utf-8")
    _commit_all(tmp_path, "init")
    _seed_contract(tmp_path, example_project)
    contract = load_contract(tmp_path)
    candidate = CandidateDescriptor(
        candidate_id="cand-null",
        project_id=contract.project.project_id,
        obligation_ids=["O-01"],
        base_commit="0" * 40,
        head_commit="1" * 40,
        claimed_intent="forge",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    with pytest.raises(GitError, match="null/fake"):
        enrich_candidate_from_git(tmp_path, candidate, contract)


def test_enrich_overrides_self_declared_risk_fields(
    tmp_path: Path, example_project: Path
) -> None:
    _init_git(tmp_path)
    lean = tmp_path / "Internal.lean"
    lean.write_text("def foo : Nat := 1\n", encoding="utf-8")
    base = _commit_all(tmp_path, "base")
    lean.write_text("def foo : Int := 1\n", encoding="utf-8")
    head = _commit_all(tmp_path, "head")
    _seed_contract(tmp_path, example_project)
    contract = load_contract(tmp_path)

    forged = CandidateDescriptor(
        candidate_id="cand-forge",
        project_id=contract.project.project_id,
        obligation_ids=["O-01"],
        base_commit=base,
        head_commit=head,
        claimed_intent="downgrade risk",
        changed_paths=["unrelated.md"],
        changed_declarations=[
            ChangedDeclaration(
                name="foo",
                kind=ArtifactType.THEOREM,
                path="Internal.lean",
                signature_changed=False,
                public=False,
                foundational=False,
            )
        ],
        generator=_generator(),
    )
    enriched = enrich_candidate_from_git(tmp_path, forged, contract)
    assert enriched.changed_paths == ["Internal.lean"]
    assert len(enriched.changed_declarations) == 1
    assert enriched.changed_declarations[0].signature_changed is True
    assert enriched.changed_declarations[0].kind is ArtifactType.DEFINITION


def test_compile_forces_git_enrichment_for_risk(
    tmp_path: Path, example_project: Path
) -> None:
    _init_git(tmp_path)
    public = tmp_path / "Example" / "Public"
    public.mkdir(parents=True)
    lean = public / "Api.lean"
    lean.write_text("def keep : Nat := 1\n", encoding="utf-8")
    base = _commit_all(tmp_path, "base")
    lean.write_text("def keep : Nat := 1\ndef api : Nat := 2\n", encoding="utf-8")
    head = _commit_all(tmp_path, "head")
    _seed_contract(tmp_path, example_project)

    forged_low_risk = CandidateDescriptor(
        candidate_id="cand-risk",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit=base,
        head_commit=head,
        claimed_intent="claim R0",
        changed_paths=["README.md"],
        changed_declarations=[],
        generator=_generator(),
    )
    packet = compile_evidence(tmp_path, forged_low_risk, skip_build=True)
    # Public API definition addition should not stay R0 after git enrichment.
    assert packet.risk_class.value in {"R2", "R3"}
    assert packet.candidate.changed_paths == ["Example/Public/Api.lean"]


# --- AUDIT-016 ---


def test_placeholder_scan_finds_sorry_in_lean_file(
    example_project: Path, tmp_path: Path
) -> None:
    lean_dir = example_project / "Example" / "Public"
    lean_dir.mkdir(parents=True, exist_ok=True)
    lean_file = lean_dir / "PlaceholderProbe.lean"
    lean_file.write_text("theorem t : True := by sorry\n", encoding="utf-8")
    try:
        candidate = CandidateDescriptor(
            candidate_id="cand-sorry",
            project_id="example-category-project",
            obligation_ids=["O-01"],
            base_commit="deadbeef",
            patch_text="",
            claimed_intent="empty patch hides sorry",
            changed_paths=["Example/Public/PlaceholderProbe.lean"],
            changed_declarations=[],
            generator=_generator(),
        )
        packet = compile_evidence(example_project, candidate, skip_build=True)
        placeholders = next(f for f in packet.findings if f.check_id == "lean.placeholders")
        assert placeholders.status is FindingStatus.FAIL
        assert "sorry" in placeholders.details["tokens"]
        assert packet.recommendation is Recommendation.REJECT
    finally:
        lean_file.unlink(missing_ok=True)


def test_empty_patch_text_without_placeholders_passes_scan(
    example_project: Path,
) -> None:
    candidate = CandidateDescriptor(
        candidate_id="cand-empty-patch",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="",
        claimed_intent="docs only",
        changed_paths=["README.md"],
        changed_declarations=[],
        generator=_generator(),
    )
    # Model requires one of head/patch_path/patch_text — empty string is set.
    packet = compile_evidence(example_project, candidate, skip_build=True)
    placeholders = next(f for f in packet.findings if f.check_id == "lean.placeholders")
    assert placeholders.status is FindingStatus.PASS


# --- AUDIT-003 ---


def test_axiom_check_unknown_for_empty_regex_stub(example_project: Path) -> None:
    from lpe.evidence.compiler import _check_axioms
    from datetime import datetime, timezone

    contract = load_contract(example_project)
    extraction = LeanExtractionResult(
        axioms_used=[],
        extractor="lean.regex-extractor",
    )
    finding = _check_axioms(
        contract, extraction, started=datetime.now(timezone.utc)
    )
    assert finding.status is FindingStatus.UNKNOWN
    assert finding.check_id == "lean.prohibited_axioms"


def test_axiom_check_fail_when_prohibited_found(example_project: Path) -> None:
    from lpe.evidence.compiler import _check_axioms
    from datetime import datetime, timezone

    contract = load_contract(example_project)
    extraction = LeanExtractionResult(
        axioms_used=["Classical.choice"],
        extractor="lean.regex-extractor",
    )
    # Classical.choice may or may not be allowed — force a fake prohibited name.
    extraction = LeanExtractionResult(
        axioms_used=["Definitely.Prohibited.Axiom"],
        extractor="lean.regex-extractor",
    )
    finding = _check_axioms(
        contract, extraction, started=datetime.now(timezone.utc)
    )
    assert finding.status is FindingStatus.FAIL


def test_compile_axiom_gate_never_pass_with_regex_stub(
    example_project: Path, example_candidate: CandidateDescriptor
) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is not FindingStatus.PASS
    assert axiom.status in {FindingStatus.UNKNOWN, FindingStatus.FAIL}
