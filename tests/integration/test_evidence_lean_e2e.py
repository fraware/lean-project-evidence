"""End-to-end Lean evidence path: real Lake build → toolchain-complete packet.

Path used on this host
----------------------
``--insecure-host-exec`` + ``network_policy: allow`` because the default Docker
image (``ubuntu:22.04``) has no Lean/Lake. Isolation stays UNKNOWN (honest —
host subprocess cannot claim network isolation PASS).

When ``LPE_DOCKER_IMAGE=lpe-lean:4.14`` (local image from ``docker/lpe-lean/``)
is present, prefer Docker + ``network_policy: deny`` for isolation PASS +
toolchain-complete. Post-build ``lake exe lpe_extract`` runs in the same
sandbox (no host Lake required) — see
``test_e2e_docker_lean_image_isolation_and_toolchain``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from lpe.evidence.compiler import compile_evidence
from lpe.execution.sandbox import (
    DEFAULT_LEAN_DOCKER_IMAGE,
    DockerSandboxExecutor,
    docker_image_present,
)
from lpe.lean.extractor import EXTRACTION_SCHEMA_V1_1, TOOLCHAIN_EXTRACTOR
from lpe.lean.toolchain import NOTE_DOCKER_EXTRACT
from lpe.models import (
    CandidateDescriptor,
    ChangedDeclaration,
    FindingStatus,
    GeneratorProvenance,
)


LEAN_PROJECT = Path(__file__).resolve().parents[1] / "fixtures" / "lean_project"
EXAMPLE_CONTRACT = (
    Path(__file__).resolve().parents[2] / "examples" / "minimal-project" / ".lean-project-contract"
)
LEAN_DOCKER_IMAGE = os.environ.get("LPE_LEAN_DOCKER_IMAGE", DEFAULT_LEAN_DOCKER_IMAGE)


def _generator() -> GeneratorProvenance:
    return GeneratorProvenance(generator_type="test", name="lean-e2e", version="0")


def _init_git(repo: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "lean-e2e@example.org"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "LeanE2E"],
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


def _seed_lean_project_with_contract(dest: Path, *, network_policy: str = "allow") -> Path:
    """Copy Lake fixture + a contract tuned for host-exec Lean builds."""
    shutil.copytree(
        LEAN_PROJECT,
        dest,
        ignore=shutil.ignore_patterns(
            ".lake", "lake-manifest.json", ".lpe", ".lean-project-contract"
        ),
    )
    shutil.copytree(EXAMPLE_CONTRACT, dest / ".lean-project-contract")
    project_yaml = dest / ".lean-project-contract" / "project.yaml"
    data = yaml.safe_load(project_yaml.read_text(encoding="utf-8"))
    data["project_id"] = "lpe-fixture-project"
    data["repository"]["public_api_paths"] = ["LpeFixture"]
    data["execution"]["build_command"] = ["lake", "build"]
    data["execution"]["network_policy"] = network_policy
    data["execution"]["timeout_seconds"] = 600
    project_yaml.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return dest


def _helper_candidate(*, base_commit: str, head_commit: str | None = None) -> CandidateDescriptor:
    """Well-formed candidate with FQN declarations (impact cone membership)."""
    return CandidateDescriptor(
        candidate_id="cand-lean-e2e-helper",
        project_id="lpe-fixture-project",
        obligation_ids=["O-01"],
        base_commit=base_commit,
        head_commit=head_commit,
        patch_text="+def helper : Nat := coreVal + 2\n",
        claimed_intent="bump helper for e2e toolchain compile",
        changed_paths=["LpeFixture/Core.lean"],
        changed_declarations=[
            ChangedDeclaration(
                name="LpeFixture.Core.helper",
                kind="definition",
                path="LpeFixture/Core.lean",
                signature_changed=False,
                public=True,
                foundational=False,
            )
        ],
        generator=_generator(),
    )


def _bump_helper(project: Path) -> None:
    """Body-only change that still typechecks (does not break corePositive)."""
    core = project / "LpeFixture" / "Core.lean"
    core.write_text(
        core.read_text(encoding="utf-8").replace(
            "def helper : Nat := coreVal + 1",
            "def helper : Nat := coreVal + 2",
        ),
        encoding="utf-8",
    )


@pytest.mark.lean
def test_e2e_host_exec_toolchain_complete_packet(tmp_path: Path) -> None:
    """Real ``lake build`` + extract via host-exec (no --skip-build).

    Docker default image lacks Lean; this is the supported E2E path on hosts
    with Lean 4.14 + Lake installed.
    """
    project = _seed_lean_project_with_contract(tmp_path / "lean_e2e")
    _init_git(project)
    base = _commit_all(project, "seed lean fixture")

    # Body-only change that still builds; keep well-formed FQN candidate (no
    # head_commit so git enrichment does not replace FQNs with short names).
    _bump_helper(project)
    # Commit the change and evaluate at head (candidate snapshot = head tree).
    head = _commit_all(project, "bump helper")

    candidate = _helper_candidate(base_commit=base, head_commit=head)
    # Head-based candidates do not need illustrative patch_text.
    candidate = candidate.model_copy(update={"patch_text": None})
    packet = compile_evidence(
        project,
        candidate,
        skip_build=False,
        insecure_host_exec=True,
        use_worktree=False,
    )

    build = next(f for f in packet.findings if f.check_id == "lean.build")
    assert build.status is FindingStatus.PASS, build.details.get("stderr", "")[:800]

    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is FindingStatus.PASS
    assert axiom.details.get("extractor") == TOOLCHAIN_EXTRACTOR

    impact = next(f for f in packet.findings if f.check_id == "lean.impact_cone")
    assert impact.status is FindingStatus.PASS
    assert impact.details.get("extractor") == TOOLCHAIN_EXTRACTOR
    assert impact.details.get("complete") is True
    assert impact.details.get("extraction_schema_version") == EXTRACTION_SCHEMA_V1_1
    cone = impact.details.get("impact_cone") or []
    # helper's downstream uses (Consumer) — not the diamond/chain from coreVal.
    assert "LpeFixture.Consumer.usesUsesCore" in cone
    assert "LpeFixture.Consumer.usesCore" in cone or "LpeFixture.Consumer.usesUsesCore" in cone

    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    # Host subprocess: honest UNKNOWN — never fake isolation PASS.
    assert isolation.status is FindingStatus.UNKNOWN
    assert isolation.status is not FindingStatus.PASS
    assert isolation.details.get("build_ran") is True
    assert isolation.details.get("insecure_host_exec") is True
    assert isolation.details.get("skip_build") is False
    assert isolation.details.get("extract_executor") == "SubprocessLeanExecutor"

    replacement = next(f for f in packet.findings if f.check_id == "downstream.replacement_tests")
    assert replacement.details.get("toolchain_backed") is True
    assert replacement.details.get("successor_count", 0) >= 1
    # With Lake on PATH, structured check should PASS (hash + lake env).
    assert replacement.status is FindingStatus.PASS
    assert "lake" in str(replacement.details.get("replacement_check", ""))

    artifact = project / ".lpe" / "lean-extraction.json"
    assert artifact.is_file()


@pytest.mark.lean
def test_e2e_git_worktree_cleanup_and_persisted_extraction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Git worktree build cleans up; toolchain JSON persisted to primary repo."""
    project = _seed_lean_project_with_contract(tmp_path / "lean_wt")
    _init_git(project)
    base = _commit_all(project, "seed")

    _bump_helper(project)
    head = _commit_all(project, "bump helper")
    (project / "dirty-uncommitted.txt").write_text("dirt\n", encoding="utf-8")

    created: list[Path] = []
    from lpe.workspace.snapshots import create_snapshot_pair

    real_create = create_snapshot_pair

    def tracking_create(*args, **kwargs):  # type: ignore[no-untyped-def]
        pair = real_create(*args, **kwargs)
        created.append(pair.candidate_path)
        assert not (pair.candidate_path / "dirty-uncommitted.txt").exists()
        return pair

    monkeypatch.setattr("lpe.workspace.manager.create_snapshot_pair", tracking_create)
    monkeypatch.setattr("lpe.evidence.compiler.create_snapshot_pair", tracking_create)
    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))

    # head_commit forces worktree + git enrichment (short names). FQN resolution
    # maps short names to module FQNs when extraction is available.
    candidate = CandidateDescriptor(
        candidate_id="cand-lean-e2e-wt",
        project_id="lpe-fixture-project",
        obligation_ids=["O-01"],
        base_commit=base,
        head_commit=head,
        claimed_intent="worktree e2e",
        changed_paths=["LpeFixture/Core.lean"],
        changed_declarations=[],
        generator=_generator(),
    )
    packet = compile_evidence(
        project,
        candidate,
        skip_build=False,
        insecure_host_exec=True,
        use_worktree=True,
    )

    assert created, "worktree should have been created"
    for path in created:
        assert not path.exists() or not any(path.iterdir())

    build = next(f for f in packet.findings if f.check_id == "lean.build")
    assert build.status is FindingStatus.PASS, build.details.get("stderr", "")[:800]
    assert build.details.get("worktree")

    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is FindingStatus.PASS
    assert axiom.details.get("extractor") == TOOLCHAIN_EXTRACTOR

    impact = next(f for f in packet.findings if f.check_id == "lean.impact_cone")
    assert impact.status is FindingStatus.PASS
    assert impact.details.get("complete") is True
    assert impact.details.get("extraction_schema_version") == EXTRACTION_SCHEMA_V1_1
    # Short git names resolve to FQNs for cone membership.
    changed = impact.details.get("changed") or []
    assert any(c.endswith(".helper") or c == "helper" for c in changed)
    if any("." in c for c in changed):
        cone = impact.details.get("impact_cone") or []
        assert "LpeFixture.Consumer.usesUsesCore" in cone or "LpeFixture.Consumer.usesCore" in cone

    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    assert isolation.status is FindingStatus.UNKNOWN
    assert isolation.details.get("build_ran") is True

    # Persisted out of the worktree for providers / follow-up inspect.
    assert (project / ".lpe" / "lean-extraction.json").is_file()


@pytest.mark.docker
def test_docker_without_lean_image_isolation_honest_not_skip_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default ubuntu image: sandboxed build runs (FAIL without Lake); isolation PASS.

    Documents why E2E toolchain-complete packets use ``--insecure-host-exec`` on
    hosts where ``LPE_DOCKER_IMAGE`` is not a Lean-capable image. Disable host
    Lake extract so a present host toolchain cannot mask the Docker gap.
    """
    project = _seed_lean_project_with_contract(
        tmp_path / "lean_docker",
        network_policy="deny",
    )
    _init_git(project)
    base = _commit_all(project, "seed")
    monkeypatch.setenv("LPE_DOCKER_IMAGE", "ubuntu:22.04")
    monkeypatch.setattr(
        "lpe.evidence.compiler.try_run_lake_extract",
        lambda *a, **k: None,
    )
    # Prevent host Lake adaptive extract from masking the Docker Lean gap.
    from lpe.lean.extractor import REGEX_STUB_EXTRACTOR, LeanExtractionResult

    monkeypatch.setattr(
        "lpe.evidence.compiler.extract_lean_repository",
        lambda *a, **k: LeanExtractionResult(
            extractor=REGEX_STUB_EXTRACTOR,
            complete=False,
            notes=["docker e2e: host extract suppressed"],
        ),
    )

    candidate = _helper_candidate(base_commit=base, head_commit=base)
    candidate = candidate.model_copy(update={"patch_text": None})
    packet = compile_evidence(
        project,
        candidate,
        skip_build=False,
        insecure_host_exec=False,
        use_sandbox=True,
        use_worktree=False,
    )
    build = next(f for f in packet.findings if f.check_id == "lean.build")
    # ubuntu has no lake — build FAIL is expected.
    assert build.status is FindingStatus.FAIL
    joined = " ".join(build.provenance.command)
    assert "--network=none" in joined

    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    assert isolation.status is FindingStatus.PASS  # sandboxed build ran
    assert isolation.details.get("build_ran") is True
    assert isolation.details.get("skip_build") is False

    # Regex-stub / incomplete extract → axioms must not PASS.
    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is not FindingStatus.PASS


@pytest.mark.docker
def test_e2e_docker_lean_image_isolation_and_toolchain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Lean-capable image: sandboxed build + extract → isolation PASS + toolchain.

    Does **not** require host Lake: ``_lake_bin`` is scrubbed so extract must
    run via ``DockerSandboxExecutor`` (same image / network-none / rw mount).
    Skips when ``lpe-lean:4.14`` (or ``LPE_LEAN_DOCKER_IMAGE``) is not present —
    pytest never rebuilds the image. Build via ``scripts/build_lean_docker_image.*``.
    """
    if not docker_image_present(LEAN_DOCKER_IMAGE):
        pytest.skip(
            f"Lean Docker image {LEAN_DOCKER_IMAGE!r} not present "
            "(build with scripts/build_lean_docker_image.ps1 or .sh)"
        )

    project = _seed_lean_project_with_contract(
        tmp_path / "lean_docker_ok",
        network_policy="deny",
    )
    _init_git(project)
    base = _commit_all(project, "seed")
    _bump_helper(project)
    head = _commit_all(project, "bump helper")

    monkeypatch.setenv("LPE_DOCKER_IMAGE", LEAN_DOCKER_IMAGE)
    # Prove Docker extract does not lean on host Lake.
    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: None)

    candidate = CandidateDescriptor(
        candidate_id="cand-lean-docker-e2e",
        project_id="lpe-fixture-project",
        obligation_ids=["O-01"],
        base_commit=base,
        head_commit=head,
        claimed_intent="docker lean e2e",
        changed_paths=["LpeFixture/Core.lean"],
        changed_declarations=[],
        generator=_generator(),
    )
    packet = compile_evidence(
        project,
        candidate,
        skip_build=False,
        insecure_host_exec=False,
        use_sandbox=True,
        use_worktree=False,
    )

    isolation = next(f for f in packet.findings if f.check_id == "execution.isolation")
    assert isolation.status is FindingStatus.PASS
    assert isolation.details.get("build_ran") is True
    assert isolation.details.get("network_isolated") is True
    assert isolation.details.get("skip_build") is False
    assert isolation.details.get("extract_executor") == "docker-sandbox"
    assert isolation.details.get("combined_build_extract") is True
    assert isolation.details.get("sandbox_invocations") == 1

    build = next(f for f in packet.findings if f.check_id == "lean.build")
    assert build.status is FindingStatus.PASS, (build.details.get("stderr") or "")[:1200]
    joined = " ".join(build.provenance.command)
    assert "--network=none" in joined
    assert LEAN_DOCKER_IMAGE in joined or "lpe-lean" in joined
    assert build.details.get("combined_build_extract") is True
    assert build.details.get("sandbox_invocations") == 1
    # Single docker run carrying the fixed combined script + allowlisted lake build.
    assert joined.count("docker run") == 1 or joined.startswith("docker")
    assert "--network=none" in joined
    assert "lake" in joined
    assert "LPE_EXTRACT_OUT=" in joined
    assert "lpe_extract" in joined

    axiom = next(f for f in packet.findings if f.check_id == "lean.prohibited_axioms")
    assert axiom.status is FindingStatus.PASS
    assert axiom.details.get("extractor") == TOOLCHAIN_EXTRACTOR
    assert axiom.details.get("extract_executor") == "docker-sandbox"
    notes = axiom.details.get("notes") or []
    assert NOTE_DOCKER_EXTRACT in notes or any("docker-sandbox" in n for n in notes)

    impact = next(f for f in packet.findings if f.check_id == "lean.impact_cone")
    assert impact.status is FindingStatus.PASS
    assert impact.details.get("complete") is True
    assert impact.details.get("extraction_schema_version") == EXTRACTION_SCHEMA_V1_1
    assert impact.details.get("extract_executor") == "docker-sandbox"
    changed = impact.details.get("changed") or []
    assert any("helper" in c for c in changed)
    cone = impact.details.get("impact_cone") or []
    assert "LpeFixture.Consumer.usesUsesCore" in cone or "LpeFixture.Consumer.usesCore" in cone

    artifact = project / ".lpe" / "lean-extraction.json"
    assert artifact.is_file()
    assert NOTE_DOCKER_EXTRACT in artifact.read_text(encoding="utf-8")
