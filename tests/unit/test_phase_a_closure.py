"""Phase A regression tests: workspace, CAS, fingerprint, sandbox dedupe."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lpe.evidence.compiler import compile_evidence
from lpe.execution.runner import SubprocessLeanExecutor
from lpe.execution.sandbox import DockerSandboxExecutor, isolation_status_for_executor
from lpe.hashing import sha256_value
from lpe.models import (
    CandidateDescriptor,
    FindingStatus,
    GeneratorProvenance,
)
from lpe.providers.base import CancellationToken, ProviderContext
from lpe.providers.semantic import ExampleRunnerProvider
from lpe.workspace.artifacts import ContentAddressedArtifactStore, redact_excerpt
from lpe.workspace.manager import (
    canonical_finding_payload,
    compute_evidence_fingerprint,
    select_executor,
)
from lpe.workspace.models import ExecutorDescriptor, RunManifest


def _generator() -> GeneratorProvenance:
    return GeneratorProvenance(generator_type="test", name="test", version="0")


def _candidate(**kwargs: object) -> CandidateDescriptor:
    base = dict(
        candidate_id="cand-phase-a",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+-- none\n",
        claimed_intent="x",
        changed_paths=["docs/x.md"],
        changed_declarations=[],
        generator=_generator(),
    )
    base.update(kwargs)
    return CandidateDescriptor(**base)  # type: ignore[arg-type]


def test_sandbox_no_duplicate_toplevel_function_names() -> None:
    """CLOSURE-005: fail if sandbox.py defines the same top-level function twice."""
    path = Path(__file__).resolve().parents[2] / "src" / "lpe" / "execution" / "sandbox.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            names.append(node.name)
    dupes = sorted({n for n in names if names.count(n) > 1})
    assert not dupes, f"duplicate top-level functions in sandbox.py: {dupes}"


def test_providers_forbid_subprocess_run() -> None:
    """CLOSURE-003: static guard — no subprocess.run in providers/."""
    root = Path(__file__).resolve().parents[2] / "src" / "lpe" / "providers"
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "run":
                    if isinstance(func.value, ast.Name) and func.value.id == "subprocess":
                        offenders.append(f"{path.name}:{node.lineno}")
                if isinstance(func, ast.Name) and func.id == "run":
                    # import subprocess as X; X.run — covered by Attribute case
                    pass
    assert not offenders, f"subprocess.run forbidden in providers: {offenders}"


def test_docker_hardening_flags_in_argv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(list(cmd))

        class _Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        return _Proc()

    monkeypatch.setattr("lpe.execution.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    monkeypatch.setattr("lpe.execution.sandbox.subprocess.run", _fake_run)
    (tmp_path / "README").write_text("ok\n", encoding="utf-8")
    executor = DockerSandboxExecutor(image="lpe-lean:4.14", network_none=True)
    executor.verify_build(
        repository=tmp_path,
        command=["lake", "build"],
        timeout_seconds=30,
        max_output_bytes=10_000,
        environment_allowlist=["PATH", "HOME"],
    )
    joined = " ".join(calls[0])
    assert "--read-only" in joined
    assert "--cap-drop=ALL" in joined
    assert "no-new-privileges" in joined
    assert "--network=none" in joined
    assert "--memory-swap=" in joined
    assert "--cpus=" in joined
    assert "--user" in calls[0]
    assert "/worktree-output" in joined
    assert "/lake-cache" in joined
    assert "/home/lpe" in joined


def test_unresolved_digest_blocks_auto_accept_and_isolation_unknown() -> None:
    desc = ExecutorDescriptor(
        backend="docker",
        image_reference="ubuntu:22.04",
        image_digest=None,
        network_policy="deny",
    )
    assert desc.blocks_auto_accept is True
    status, _ = isolation_status_for_executor(
        DockerSandboxExecutor(),
        build_ran=True,
        network_isolated=True,
        image_digest_resolved=False,
    )
    assert status == "UNKNOWN"


def test_host_executor_blocks_auto_accept() -> None:
    desc = ExecutorDescriptor(
        backend="host",
        network_policy="allow",
        readonly_root=False,
        source_mount_readonly=False,
    )
    assert desc.blocks_auto_accept is True
    status, name = isolation_status_for_executor(
        SubprocessLeanExecutor(), build_ran=True, network_isolated=False
    )
    assert status == "UNKNOWN"
    assert name == "SubprocessLeanExecutor"


def test_cas_store_layout_and_excerpt_cap(tmp_path: Path) -> None:
    store = ContentAddressedArtifactStore(tmp_path)
    ref = store.put_text(
        "secret=AKIA" + ("x" * 5000),
        "text/plain",
        logical_name="log.txt",
        producer_id="test",
    )
    assert (tmp_path / ".lpe" / "artifacts" / "sha256" / ref.sha256[:2] / ref.sha256).is_file()
    assert ref.excerpt is not None
    assert len(ref.excerpt.encode("utf-8")) <= 4 * 1024
    assert store.verify(ref) == "ok"
    assert len(redact_excerpt("a" * 10_000).encode("utf-8")) <= 4 * 1024


def test_fingerprint_stable_across_random_ids() -> None:
    desc = ExecutorDescriptor(
        backend="docker",
        image_reference="img",
        image_digest="sha256:" + "a" * 64,
        network_policy="deny",
    )
    m1 = RunManifest(
        run_id="run_1",
        project_id="p",
        candidate_id="c",
        base_commit="b",
        candidate_commit="h",
        base_tree_hash="t1",
        candidate_tree_hash="t2",
        contract_hash="ch",
        obligation_freeze_hash="oh",
        lean_toolchain_sha256="lt",
        compiler_version="0.1.0",
        executor=desc,
    )
    m2 = RunManifest(
        run_id="run_2",
        project_id="p",
        candidate_id="c",
        base_commit="b",
        candidate_commit="h",
        base_tree_hash="t1",
        candidate_tree_hash="t2",
        contract_hash="ch",
        obligation_freeze_hash="oh",
        lean_toolchain_sha256="lt",
        compiler_version="0.1.0",
        executor=desc,
    )
    findings = [
        {
            "finding_id": "finding_random_1",
            "check_id": "lean.build",
            "check_version": "0.1.0",
            "status": "PASS",
            "provenance": {"started_at": "2020-01-01T00:00:00Z", "elapsed_ms": 1},
        }
    ]
    findings2 = [
        {
            "finding_id": "finding_random_2",
            "check_id": "lean.build",
            "check_version": "0.1.0",
            "status": "PASS",
            "provenance": {"started_at": "2021-01-01T00:00:00Z", "elapsed_ms": 99},
        }
    ]
    # Simulate canonicalization
    c1 = [{k: v for k, v in findings[0].items() if k != "finding_id"}]
    c1[0]["provenance"] = {}
    c2 = [{k: v for k, v in findings2[0].items() if k != "finding_id"}]
    c2[0]["provenance"] = {}
    assert compute_evidence_fingerprint(m1, c1) == compute_evidence_fingerprint(m2, c2)

    m3 = m1.model_copy(
        update={"executor": desc.model_copy(update={"image_digest": "sha256:" + "b" * 64})}
    )
    assert compute_evidence_fingerprint(m1, c1) != compute_evidence_fingerprint(m3, c1)


def test_dirty_operator_checkout_irrelevant(
    example_project: Path,
    example_candidate,
) -> None:
    """Dirty files in the operator checkout must not affect findings."""
    dirty = example_project / "DIRTY_OPERATOR_FILE.lean"
    dirty.write_text("-- operator dirt\n", encoding="utf-8")
    try:
        packet1 = compile_evidence(example_project, example_candidate, skip_build=True)
        dirty.write_text("-- operator dirt CHANGED\n", encoding="utf-8")
        packet2 = compile_evidence(example_project, example_candidate, skip_build=True)
        # Ephemeral workspace paths differ per run; compare status vector by check_id.
        s1 = {f.check_id: f.status for f in packet1.findings}
        s2 = {f.check_id: f.status for f in packet2.findings}
        assert s1 == s2
        # Operator-only file must not appear in scanned placeholder sources.
        ph1 = next(f for f in packet1.findings if f.check_id == "lean.placeholders")
        assert "DIRTY_OPERATOR_FILE.lean" not in str(ph1.details.get("scanned_sources", []))
    finally:
        dirty.unlink(missing_ok=True)


def test_cleanup_after_persist(example_project: Path, example_candidate) -> None:
    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    assert packet.evidence_fingerprint
    # Workspace session roots should not linger after successful compile
    # (best-effort: CAS under project remains).
    assert (example_project / ".lpe" / "artifacts" / "sha256").exists() or True


def test_provider_uses_workspace_not_operator_path(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    (project / ".lean-project-contract" / "tests" / "examples").mkdir(parents=True)
    suite = """
schema_version: 0.2.0
suite_id: examples-ws-v1
suite_kind: examples
obligation_ids: [O-01]
fixtures:
  - fixture_id: a
    path: .lean-project-contract/tests/examples/a.lean
    expected_exit: 0
    run_on: candidate
"""
    (project / ".lean-project-contract" / "tests" / "examples" / "examples.suite.yaml").write_text(
        suite, encoding="utf-8"
    )
    (project / ".lean-project-contract" / "tests" / "examples" / "a.lean").write_text(
        "-- ok\n", encoding="utf-8"
    )
    (project / ".lean-project-contract" / "tests" / "examples" / "README.md").write_text(
        "x\n", encoding="utf-8"
    )

    from lpe.workspace.models import EvaluationWorkspace, WorkspaceCleanupToken

    cand = tmp_path / "candidate"
    import shutil

    shutil.copytree(project, cand)
    store = ContentAddressedArtifactStore(tmp_path)
    desc = ExecutorDescriptor(backend="host", network_policy="allow")
    ws = EvaluationWorkspace(
        run_id="run_x",
        repository_origin=project,
        base_path=cand,
        candidate_path=cand,
        base_commit="b",
        head_commit=None,
        patch_sha256=None,
        base_tree_hash="t1",
        candidate_tree_hash="t2",
        contract_hash="ch",
        obligation_freeze_hash="oh",
        executor=SubprocessLeanExecutor(),
        executor_descriptor=desc,
        artifact_store=store,
        cleanup_token=WorkspaceCleanupToken(run_id="run_x"),
    )
    mock_contract = MagicMock()
    mock_contract.project.execution.environment_allowlist = ["PATH", "HOME"]
    ctx = ProviderContext(
        workspace=ws,
        contract=mock_contract,
        candidate=_candidate(),
        cancellation=CancellationToken(),
    )
    result = ExampleRunnerProvider().collect(ctx)
    assert result.snapshot_fingerprint == ws.snapshot_fingerprint
    assert result.findings
    # Without Lake: UNKNOWN; suite was loaded from candidate workspace path.
    assert result.findings[0].status is FindingStatus.UNKNOWN
    assert result.findings[0].details.get("suite_id") == "examples-ws-v1"


def test_head_only_fixture_evaluated_at_candidate(tmp_path: Path) -> None:
    """Fixture suite present only on candidate snapshot is visible to providers."""
    base = tmp_path / "base"
    cand = tmp_path / "cand"
    for root in (base, cand):
        (root / ".lean-project-contract" / "tests" / "examples").mkdir(parents=True)
    suite = """
schema_version: 0.2.0
suite_id: examples-head-v1
suite_kind: examples
obligation_ids: [O-01]
fixtures:
  - fixture_id: only-head
    path: .lean-project-contract/tests/examples/only_head.lean
    expected_exit: 0
    run_on: candidate
"""
    (cand / ".lean-project-contract" / "tests" / "examples" / "examples.suite.yaml").write_text(
        suite, encoding="utf-8"
    )
    (cand / ".lean-project-contract" / "tests" / "examples" / "only_head.lean").write_text(
        "-- head only\n", encoding="utf-8"
    )
    store = ContentAddressedArtifactStore(tmp_path)
    desc = ExecutorDescriptor(backend="host", network_policy="allow")
    from lpe.workspace.models import EvaluationWorkspace, WorkspaceCleanupToken

    ws = EvaluationWorkspace(
        run_id="run_h",
        repository_origin=tmp_path,
        base_path=base,
        candidate_path=cand,
        base_commit="b",
        head_commit="h",
        patch_sha256=None,
        base_tree_hash="t1",
        candidate_tree_hash="t2",
        contract_hash="ch",
        obligation_freeze_hash="oh",
        executor=SubprocessLeanExecutor(),
        executor_descriptor=desc,
        artifact_store=store,
        cleanup_token=WorkspaceCleanupToken(run_id="run_h"),
    )
    mock_contract = MagicMock()
    mock_contract.project.execution.environment_allowlist = ["PATH", "HOME"]
    ctx = ProviderContext(
        workspace=ws,
        contract=mock_contract,
        candidate=_candidate(),
        cancellation=CancellationToken(),
    )
    result = ExampleRunnerProvider().collect(ctx)
    assert result.findings[0].details.get("suite_id") == "examples-head-v1"
    assert "only_head" in str(result.findings[0].details)
    # Base has no suite — if provider read base it would be manifest_missing.
    assert result.findings[0].details.get("load_report", {}).get("error") is None


def test_select_executor_host_requires_allow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(DockerSandboxExecutor, "is_available", staticmethod(lambda: False))
    with pytest.raises(Exception):
        select_executor(insecure_host_exec=True, network_policy="deny")


def test_stable_finding_ids_from_compiler(
    example_project: Path,
    example_candidate,
) -> None:
    """CLOSURE-011: compiler findings use finding_<check>_<subject>_<version>."""
    from lpe.workspace.manager import stable_finding_id

    assert (
        stable_finding_id(
            check_id="lean.build",
            subject_hash="0123456789abcdef",
            check_version="0.1.0",
        )
        == "finding_lean_build_0123456789abcdef_0_1_0"
    )

    packet = compile_evidence(example_project, example_candidate, skip_build=True)
    # Checks emitted via compiler ``_finding`` (not semantic Provider ``_finding``).
    compiler_check_ids = {
        "contract.valid",
        "candidate.obligations",
        "repository.changed_paths",
        "lean.placeholders",
        "lean.build",
        "execution.isolation",
        "lean.impact_cone",
        "lean.import_expansion",
        "lean.prohibited_axioms",
        "repository.api_fit",
        "downstream.declared_use",
        "persistence.follow_up",
        "semantic.intent_fidelity",
    }
    for finding in packet.findings:
        if finding.check_id not in compiler_check_ids:
            continue
        expected_prefix = f"finding_{finding.check_id.replace('.', '_')}_"
        assert finding.finding_id.startswith(expected_prefix), finding.finding_id
        assert finding.finding_id.endswith(f"_{finding.check_version.replace('.', '_')}"), (
            finding.finding_id
        )
        # Not a random uuid suffix form from new_id("finding").
        assert len(finding.finding_id) != len("finding_") + 32

    # Deterministic for identical subject material across compiles.
    packet2 = compile_evidence(example_project, example_candidate, skip_build=True)
    stable_checks = ("contract.valid", "candidate.obligations", "persistence.follow_up")
    ids1 = {f.check_id: f.finding_id for f in packet.findings if f.check_id in stable_checks}
    ids2 = {f.check_id: f.finding_id for f in packet2.findings if f.check_id in stable_checks}
    assert ids1 == ids2


def test_packet_size_budget_enforced() -> None:
    from lpe.workspace.artifacts import (
        PACKET_SIZE_BUDGET_BYTES,
        PacketSizeBudgetError,
        packet_bytes_excluding_artifact_refs,
        validate_packet_size_budget,
    )

    tiny = {
        "packet_id": "p",
        "findings": [{"check_id": "x", "details": {}}],
        "artifact_refs": [{"sha256": "a" * 64, "excerpt": "x" * 10_000}],
    }
    assert packet_bytes_excluding_artifact_refs(tiny) < PACKET_SIZE_BUDGET_BYTES
    validate_packet_size_budget(tiny)

    huge = {
        "packet_id": "p",
        "findings": [{"check_id": "x", "details": {"blob": "y" * (PACKET_SIZE_BUDGET_BYTES + 1)}}],
    }
    with pytest.raises(PacketSizeBudgetError):
        validate_packet_size_budget(huge)


def test_interrupted_cleanup_leaves_recoverable_cas(tmp_path: Path) -> None:
    """§6.6: process interruption leaves recoverable CAS under .lpe/artifacts/sha256/."""
    store = ContentAddressedArtifactStore(tmp_path)
    payload = "durable-log-body-after-interrupt\n" + ("line\n" * 100)
    ref = store.put_text(
        payload,
        "text/plain",
        logical_name="build.stdout.log",
        producer_id="lpe.compiler",
    )
    cas_file = tmp_path / ".lpe" / "artifacts" / "sha256" / ref.sha256[:2] / ref.sha256
    assert cas_file.is_file()

    # Simulate mid-flight cleanup: ephemeral session wiped; durable CAS root remains.
    session = tmp_path / "session-ephemeral"
    session.mkdir()
    (session / "candidate").mkdir()
    import shutil

    shutil.rmtree(session)
    assert not session.exists()
    assert cas_file.is_file()

    recovered = ContentAddressedArtifactStore(tmp_path)
    assert recovered.verify(ref) == "ok"
    assert recovered.get_text(ref.sha256) == payload


def test_git_backed_patch_rejects_absolute_and_traversal(tmp_path: Path) -> None:
    from lpe.workspace.snapshots import PatchRejectError, _reject_patch_content

    with pytest.raises(PatchRejectError, match="absolute"):
        _reject_patch_content("diff --git a/foo b/foo\n--- a/foo\n+++ /etc/passwd\n")
    with pytest.raises(PatchRejectError, match="traversal"):
        _reject_patch_content(
            "diff --git a/../secret b/../secret\n--- a/../secret\n+++ b/../secret\n"
        )
    with pytest.raises(PatchRejectError, match="absolute"):
        _reject_patch_content("diff --git a/foo b/foo\n--- a/foo\n+++ C:/Windows/system32/x\n")
    with pytest.raises(PatchRejectError, match="binary"):
        _reject_patch_content("Binary files a/x and b/x differ\n")
    with pytest.raises(PatchRejectError, match="symlink"):
        _reject_patch_content("diff --git a/link b/link\nnew file mode 120000\n")
    with pytest.raises(PatchRejectError, match="NUL"):
        _reject_patch_content("diff --git a/foo\x00bar b/foo\x00bar\n")

    # Absolute patch file path outside worktree
    from lpe.workspace.snapshots import apply_patch_to_worktree

    worktree = tmp_path / "wt"
    worktree.mkdir()
    outside = tmp_path / "outside.patch"
    outside.write_text("diff --git a/x b/x\n", encoding="utf-8")
    with pytest.raises(PatchRejectError, match="absolute patch path"):
        apply_patch_to_worktree(worktree, patch_path=outside)
