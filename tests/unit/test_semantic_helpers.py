"""Direct unit coverage for semantic provider helpers (no Lake/network)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lpe.hashing import sha256_text
from lpe.models import CandidateDescriptor, ChangedDeclaration, FindingStatus
from lpe.providers import semantic as sem
from lpe.providers.base import CancellationToken, ProviderContext
from lpe.providers.semantic import (
    DownstreamReplacementProvider,
    parse_signature_structure,
    short_name_in_line,
)
from lpe.workspace.artifacts import ContentAddressedArtifactStore
from lpe.workspace.models import (
    EvaluationWorkspace,
    ExecutorDescriptor,
    WorkspaceCleanupToken,
)


def _generator():
    from lpe.models import GeneratorProvenance

    return GeneratorProvenance(generator_type="test", name="test", version="0")


def _ctx(
    project_path: Path,
    candidate: CandidateDescriptor,
    *,
    candidate_extraction: object | None = None,
) -> ProviderContext:
    from lpe.execution.runner import SubprocessLeanExecutor

    store = ContentAddressedArtifactStore(project_path)
    desc = ExecutorDescriptor(
        backend="host",
        network_policy="allow",
        readonly_root=False,
        source_mount_readonly=False,
    )
    ws = EvaluationWorkspace(
        run_id="run_test",
        repository_origin=project_path,
        base_path=project_path,
        candidate_path=project_path,
        base_commit=candidate.base_commit,
        head_commit=candidate.head_commit,
        patch_sha256=None,
        base_tree_hash="t1",
        candidate_tree_hash="t2",
        contract_hash="ch",
        obligation_freeze_hash="oh",
        executor=SubprocessLeanExecutor(),
        executor_descriptor=desc,
        artifact_store=store,
        cleanup_token=WorkspaceCleanupToken(run_id="run_test"),
    )
    mock_contract = MagicMock()
    mock_contract.project.execution.environment_allowlist = ["PATH", "HOME"]
    return ProviderContext(
        workspace=ws,
        contract=mock_contract,
        candidate=candidate,
        cancellation=CancellationToken(),
        candidate_extraction=candidate_extraction,
    )


def test_parse_signature_structure_arrow_and_no_colon() -> None:
    with_arrow = parse_signature_structure("theorem Foo.bar (n : Nat) : Nat → Bool")
    assert with_arrow["decl_name"] == "Foo.bar"
    assert with_arrow["binders"] is not None
    assert with_arrow["conclusion"] is not None

    no_colon = parse_signature_structure("def Foo.x")
    assert no_colon["decl_name"] == "Foo.x"
    assert no_colon["conclusion"] is None

    empty = parse_signature_structure("")
    assert empty["decl_name"] is None


def test_short_name_in_line() -> None:
    assert short_name_in_line("Foo.Bar.baz", "  baz := 1")
    assert not short_name_in_line("Foo.Bar.baz", "  other := 1")


def test_jaccard_edge_cases() -> None:
    assert sem._jaccard(set(), set()) == 1.0
    assert sem._jaccard({"a"}, set()) == 0.0
    assert sem._jaccard({"a", "b"}, {"b", "c"}) == pytest.approx(1 / 3)


def test_token_set() -> None:
    tokens = sem._token_set("Foo.Bar_baz:qux")
    assert "foo" in tokens
    assert "bar" in tokens
    assert "baz" in tokens


def test_list_structured_fixtures(tmp_path: Path) -> None:
    d = tmp_path / "ex"
    d.mkdir()
    (d / "README.md").write_text("# meta\n", encoding="utf-8")
    (d / "ok.json").write_text("{}", encoding="utf-8")
    (d / "skip.txt").write_text("x", encoding="utf-8")
    found = sem._list_structured_fixtures(d)
    assert [p.name for p in found] == ["ok.json"]
    assert sem._list_structured_fixtures(tmp_path / "missing") == []


def test_load_structured_document_variants(tmp_path: Path) -> None:
    j = tmp_path / "a.json"
    j.write_text('{"name": "x"}', encoding="utf-8")
    assert sem._load_structured_document(j) == {"name": "x"}

    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    assert sem._load_structured_document(bad) is None

    y = tmp_path / "a.yaml"
    y.write_text("name: y\n", encoding="utf-8")
    assert sem._load_structured_document(y) == {"name": "y"}

    lean = tmp_path / "a.lean"
    lean.write_text("def x := 1\n", encoding="utf-8")
    assert "def x" in str(sem._load_structured_document(lean))

    scalar = tmp_path / "n.json"
    scalar.write_text("42", encoding="utf-8")
    assert sem._load_structured_document(scalar) is None

    missing = tmp_path / "gone.json"
    assert sem._load_structured_document(missing) is None


def test_example_document_ok_branches() -> None:
    assert sem._example_document_ok("  ", obligation_ids=["O-01"])[0] is False
    assert sem._example_document_ok("def x := 1", obligation_ids=["O-01"])[0] is True
    assert sem._example_document_ok("sorry", obligation_ids=["O-01"])[0] is False
    assert sem._example_document_ok([], obligation_ids=["O-01"])[0] is False
    assert sem._example_document_ok([{"a": 1}], obligation_ids=["O-01"])[0] is True
    assert sem._example_document_ok({}, obligation_ids=["O-01"])[0] is False
    ok, _ = sem._example_document_ok(
        {"obligation_id": "O-01", "expected": "y"}, obligation_ids=["O-01"]
    )
    assert ok is True
    bad_obl, _ = sem._example_document_ok(
        {"obligation_id": "O-99", "expected": "y"}, obligation_ids=["O-01"]
    )
    assert bad_obl is False
    only_obl, _ = sem._example_document_ok({"obligation_ids": ["O-01"]}, obligation_ids=["O-01"])
    assert only_obl is True
    no_bind, _ = sem._example_document_ok({"noise": 1}, obligation_ids=["O-01"])
    assert no_bind is False
    bad_type, _ = sem._example_document_ok({"obligation_id": 12}, obligation_ids=["O-01"])
    assert bad_type is False


def test_counterexample_document_ok_branches() -> None:
    assert sem._counterexample_document_ok("  ")[0] is False
    assert sem._counterexample_document_ok("sorry")[0] is True
    assert sem._counterexample_document_ok([])[0] is False
    assert sem._counterexample_document_ok([{"x": 1}])[0] is True
    assert sem._counterexample_document_ok({})[0] is False
    assert sem._counterexample_document_ok({"should_fail": False})[0] is False
    assert sem._counterexample_document_ok({"should_fail": True})[0] is True
    assert sem._counterexample_document_ok({"lean": "def x"})[0] is True
    assert sem._counterexample_document_ok({"noise": 1})[0] is False


def test_redact_log_snippet() -> None:
    out = sem._redact_log_snippet("token=SECRET_VALUE_HERE_EXTRA", limit=20)
    assert len(out) <= 20


def test_successor_hash_integrity() -> None:
    sig = "Nat -> Nat"
    digest = sha256_text(sig)
    ok = sem._successor_hash_integrity(
        [{"signature": sig, "signature_hash": digest, "path": "A.lean"}]
    )
    assert ok["ran"] is True
    assert ok["ok"] is True

    bad = sem._successor_hash_integrity(
        [{"signature": sig, "signature_hash": "deadbeef", "path": "A.lean"}]
    )
    assert bad["ok"] is False
    assert bad["mismatched"] == 1

    missing = sem._successor_hash_integrity([{"path": "A.lean"}])
    assert missing["ran"] is False
    assert missing["missing_signature"] == 1

    no_hash = sem._successor_hash_integrity([{"signature": sig, "path": "A.lean"}])
    assert no_hash["missing_hash"] == 1
    assert no_hash["ok"] is False


def test_try_compile_successor_modules_lake_unavailable(tmp_path: Path) -> None:
    candidate = CandidateDescriptor(
        candidate_id="cand-compile",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+--\n",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    report = sem._try_compile_successor_modules(
        _ctx(tmp_path, candidate),
        [{"path": "A.lean", "signature": "Nat", "signature_hash": "a" * 64}],
        max_modules=3,
    )
    assert report["attempted"] is False
    assert report["reason"] == "lake_unavailable"


def test_try_compile_successor_modules_no_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sem, "lean_toolchain_available", lambda _p: True)
    monkeypatch.setattr(sem, "has_lakefile", lambda _p: True)
    candidate = CandidateDescriptor(
        candidate_id="cand-nopath",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+--\n",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    report = sem._try_compile_successor_modules(
        _ctx(tmp_path, candidate),
        [{"path": "notes.md"}],
        max_modules=3,
    )
    assert report["reason"] == "no_successor_lean_paths"


def test_try_lake_env_lean_error_and_timeout(tmp_path: Path) -> None:
    candidate = CandidateDescriptor(
        candidate_id="cand-lake",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+--\n",
        claimed_intent="x",
        changed_paths=[],
        changed_declarations=[],
        generator=_generator(),
    )
    ctx = _ctx(tmp_path, candidate)
    ctx.workspace.executor.run = MagicMock(side_effect=OSError("boom"))  # type: ignore[method-assign]
    err = sem._try_lake_env_lean(ctx, "A.lean")
    assert err["ok"] is False
    assert err["reason"] == "lake_invoke_error"

    ctx.workspace.executor.run = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(exit_code=1, timed_out=True, stderr="timed out", stdout="")
    )
    timed = sem._try_lake_env_lean(ctx, "A.lean")
    assert timed["ok"] is False
    assert timed["reason"] == "lake_invoke_error"

    ctx.workspace.executor.run = MagicMock(  # type: ignore[method-assign]
        return_value=SimpleNamespace(exit_code=0, timed_out=False, stderr="", stdout="ok")
    )
    ok = sem._try_lake_env_lean(ctx, "A.lean")
    assert ok["ok"] is True
    assert ok["reason"] == "lake_env_ok"


def test_downstream_payload_helpers() -> None:
    assert (
        sem._downstream_replacement_payload(
            "downstream.replacement_tests",
            {"lake_dependent_check": {"attempted": True}},
        ).payload_type
        == "ExecutedCheckFindingPayload"
    )
    assert (
        sem._downstream_replacement_payload(
            "downstream.replacement_tests",
            {"signature_hash_check": {"ran": True}},
        ).payload_type
        == "ExecutedCheckFindingPayload"
    )
    assert (
        sem._downstream_replacement_payload(
            "downstream.replacement_tests",
            {"changed": True},
        ).payload_type
        == "StructuralDiffFindingPayload"
    )
    assert (
        sem._downstream_replacement_payload(
            "downstream.replacement_tests",
            {},
        ).payload_type
        == "OpaqueFindingPayload"
    )


def _downstream_ctx_and_extraction(
    tmp_path: Path, *, successor_hash: str | None = None
) -> tuple[ProviderContext, object]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "Lib.lean").write_text(
        "def seedFn : Nat := 1\ndef userFn : Nat := seedFn\n",
        encoding="utf-8",
    )
    candidate = CandidateDescriptor(
        candidate_id="cand-down",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        patch_text="+def seedFn : Nat := 1\n",
        claimed_intent="downstream",
        changed_paths=["Lib.lean"],
        changed_declarations=[
            ChangedDeclaration(
                name="seedFn",
                kind="definition",
                path="Lib.lean",
                signature_changed=False,
                public=False,
                foundational=False,
            )
        ],
        generator=_generator(),
    )
    sig = "Nat"
    digest = successor_hash if successor_hash is not None else sha256_text(sig)

    class FakeExtraction:
        complete = True
        extractor = "lean.toolchain"
        errors: list[object] = []
        declarations = [
            SimpleNamespace(
                name="seedFn",
                kind="definition",
                signature=sig,
                signature_hash=sha256_text(sig),
                path="Lib.lean",
            ),
            SimpleNamespace(
                name="userFn",
                kind="definition",
                signature=sig,
                signature_hash=digest,
                path="Lib.lean",
            ),
        ]

    extraction = FakeExtraction()
    return _ctx(tmp_path, candidate, candidate_extraction=extraction), extraction


def test_downstream_toolchain_hash_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Drive DownstreamReplacementProvider toolchain branch without Lake."""
    ctx, extraction = _downstream_ctx_and_extraction(tmp_path)
    monkeypatch.setattr(sem, "TOOLCHAIN_EXTRACTOR", "lean.toolchain")
    monkeypatch.setattr(
        sem,
        "resolve_changed_names_detailed",
        lambda *_a, **_k: ({"seedFn"}, []),
    )
    monkeypatch.setattr(sem, "build_dependency_graph", lambda *_a, **_k: {})
    monkeypatch.setattr(sem, "impact_cone", lambda *_a, **_k: {"userFn"})
    monkeypatch.setattr(
        sem,
        "extract_lean_repository",
        lambda *_a, **_k: extraction,
    )
    monkeypatch.setattr(
        sem,
        "_try_compile_successor_modules",
        lambda *_a, **_k: {
            "attempted": False,
            "ok": False,
            "reason": "lake_unavailable",
            "modules_checked": 0,
            "modules": [],
        },
    )

    result = DownstreamReplacementProvider().collect(ctx)
    finding = result.findings[0]
    assert finding.status is FindingStatus.UNKNOWN
    assert finding.details["replacement_check"] == "hash_only_lake_unavailable"


def test_downstream_hash_fail_and_lake_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx, extraction = _downstream_ctx_and_extraction(tmp_path, successor_hash="bad")
    monkeypatch.setattr(sem, "TOOLCHAIN_EXTRACTOR", "lean.toolchain")
    monkeypatch.setattr(
        sem,
        "resolve_changed_names_detailed",
        lambda *_a, **_k: ({"seedFn"}, []),
    )
    monkeypatch.setattr(sem, "build_dependency_graph", lambda *_a, **_k: {})
    monkeypatch.setattr(sem, "impact_cone", lambda *_a, **_k: {"userFn"})
    monkeypatch.setattr(
        sem,
        "extract_lean_repository",
        lambda *_a, **_k: extraction,
    )

    fail = DownstreamReplacementProvider().collect(ctx)
    assert fail.findings[0].status is FindingStatus.FAIL
    assert fail.findings[0].details["replacement_check"] == "signature_hash_failed"

    # Fresh extraction with matching hashes for Lake branches.
    ctx2, extraction2 = _downstream_ctx_and_extraction(tmp_path / "ok")
    monkeypatch.setattr(
        sem,
        "extract_lean_repository",
        lambda *_a, **_k: extraction2,
    )
    monkeypatch.setattr(
        sem,
        "_try_compile_successor_modules",
        lambda *_a, **_k: {
            "attempted": True,
            "ok": False,
            "reason": "compile_failed",
            "modules_checked": 1,
            "modules": ["Lib.lean"],
            "error": "boom",
        },
    )
    lake_fail = DownstreamReplacementProvider().collect(ctx2)
    assert lake_fail.findings[0].status is FindingStatus.FAIL
    assert lake_fail.findings[0].details["replacement_check"] == "lake_env_failed"

    monkeypatch.setattr(
        sem,
        "_try_compile_successor_modules",
        lambda *_a, **_k: {
            "attempted": True,
            "ok": True,
            "reason": "lake_env_ok",
            "modules_checked": 1,
            "modules": ["Lib.lean"],
        },
    )
    lake_ok = DownstreamReplacementProvider().collect(ctx2)
    assert lake_ok.findings[0].status is FindingStatus.PASS
