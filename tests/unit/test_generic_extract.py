"""Generic injection dry-run / mocks and paired extract fingerprint gates."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lpe.lean.extract_pair import (
    StaleExtractionError,
    assert_artifact_fresh,
    extract_pair,
    fingerprint_for_path,
    invalidate_reuse_reason,
)
from lpe.lean.generic import (
    bundled_extractor_root,
    discover_lake_workspace,
    discover_modules,
    read_toolchain_spec,
    run_generic_extract,
    toolchain_is_supported,
)
from lpe.lean.models import (
    UNSUPPORTED_TOOLCHAIN_CODE,
    ExtractionCompleteness,
    LeanExtractionResultV2,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "lean_project"


def test_bundled_extractor_sources_exist() -> None:
    root = bundled_extractor_root()
    assert (root / "LpeExtract" / "Main.lean").is_file()
    assert (root / "LpeExtract" / "Protocol.lean").is_file()
    assert (root / "lakefile.toml").is_file() or (
        Path(__file__).resolve().parents[2] / "lean" / "lakefile.toml"
    ).is_file()


def test_discover_lake_workspace_fixture() -> None:
    from lpe.lean.generic import LakeWorkspaceInfo

    info = discover_lake_workspace(FIXTURE)
    assert isinstance(info, LakeWorkspaceInfo)
    assert info.package_name == "LpeFixture"
    assert "LpeFixture" in info.library_roots


def test_discover_modules_fixture() -> None:
    from lpe.lean.generic import LakeWorkspaceInfo

    info = discover_lake_workspace(FIXTURE)
    assert isinstance(info, LakeWorkspaceInfo)
    discovery = discover_modules(FIXTURE, info)
    assert discovery.error is None
    assert discovery.method == "lake_metadata"
    assert any(m.startswith("LpeFixture") for m in discovery.modules)


def test_toolchain_support_matrix() -> None:
    assert toolchain_is_supported("leanprover/lean4:v4.14.0")
    assert toolchain_is_supported("leanprover/lean4:v4.14.1")
    assert not toolchain_is_supported("leanprover/lean4:v4.9.0")
    assert not toolchain_is_supported("")


def test_unsupported_toolchain_never_silent_success(tmp_path: Path) -> None:
    (tmp_path / "lakefile.toml").write_text(
        'name = "X"\n[[lean_lib]]\nname = "X"\n',
        encoding="utf-8",
    )
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v3.0.0\n", encoding="utf-8")
    (tmp_path / "X.lean").write_text("def x := 1\n", encoding="utf-8")
    result = run_generic_extract(
        tmp_path,
        snapshot_fingerprint="fp",
        dry_run=False,
    )
    assert result.is_unsupported_toolchain
    assert any(e.code == UNSUPPORTED_TOOLCHAIN_CODE for e in result.errors)
    assert result.completeness.environment_loaded is False


def test_generic_dry_run_fixture() -> None:
    result = run_generic_extract(
        FIXTURE,
        snapshot_fingerprint="dry",
        dry_run=True,
    )
    assert not result.has_blocking_errors
    assert any("dry_run" in n for n in result.notes)
    assert result.completeness.environment_loaded is False


def test_paired_extract_dry_run_fingerprints() -> None:
    paired = extract_pair(
        base_path=FIXTURE,
        candidate_path=FIXTURE,
        base_tree_hash="tree-base",
        candidate_tree_hash="tree-head",
        dry_run=True,
    )
    assert paired.base_fingerprint.tree_hash == "tree-base"
    assert paired.candidate_fingerprint.tree_hash == "tree-head"
    assert paired.base.snapshot_fingerprint == paired.base_fingerprint.digest
    assert paired.candidate.snapshot_fingerprint == paired.candidate_fingerprint.digest
    assert paired.base_fingerprint.digest != paired.candidate_fingerprint.digest


def test_stale_reuse_refused() -> None:
    fp = fingerprint_for_path(FIXTURE, tree_hash="tree-a")
    cached = LeanExtractionResultV2(
        snapshot_fingerprint="not-matching",
        toolchain_spec=read_toolchain_spec(FIXTURE),
        completeness=ExtractionCompleteness(),
    )
    with pytest.raises(StaleExtractionError):
        assert_artifact_fresh(cached, fp, label="base")
    reason = invalidate_reuse_reason(
        cached,
        tree_hash="tree-a",
        toolchain_spec=fp.toolchain_spec,
    )
    assert reason is not None


def test_tree_change_invalidates_fingerprint() -> None:
    a = fingerprint_for_path(FIXTURE, tree_hash="aaa")
    b = fingerprint_for_path(FIXTURE, tree_hash="bbb")
    assert a.digest != b.digest
    # toolchain change also invalidates
    from lpe.lean.extract_pair import ExtractionFingerprint

    c = ExtractionFingerprint(tree_hash="aaa", toolchain_spec="leanprover/lean4:v4.14.0")
    d = ExtractionFingerprint(tree_hash="aaa", toolchain_spec="leanprover/lean4:v4.14.1")
    assert c.digest != d.digest


def test_reuse_with_matching_fingerprint() -> None:
    paired = extract_pair(
        base_path=FIXTURE,
        candidate_path=FIXTURE,
        base_tree_hash="same-tree",
        candidate_tree_hash="same-tree-head",
        dry_run=True,
    )
    reused = extract_pair(
        base_path=FIXTURE,
        candidate_path=FIXTURE,
        base_tree_hash="same-tree",
        candidate_tree_hash="same-tree-head",
        dry_run=True,
        reuse_base=paired.base,
        reuse_candidate=paired.candidate,
    )
    assert reused.reused_base is True
    assert reused.reused_candidate is True


@pytest.mark.slow
@pytest.mark.lean
def test_scale_validation_skipped_without_network() -> None:
    """External §9.11 scale gates skip without pinned SHAs / network clones."""
    import os

    import yaml

    matrix_path = (
        Path(__file__).resolve().parents[2] / "docs" / "closure" / "compatibility-matrix.yaml"
    )
    data = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    pending = [
        p
        for p in data["projects"]
        if p["id"] != "fixture"
        and str(p.get("commit_sha")) in {"pending_selection", "pending_live_validation"}
    ]
    if pending and not os.environ.get("LPE_SCALE_CLONE_ROOT"):
        pytest.skip(
            "compatibility matrix external SHAs pending_live_validation — "
            "no network scale run (see tests/unit/test_compatibility_matrix.py)"
        )
    pytest.fail("LPE_SCALE_CLONE_ROOT set but scale runner not wired in this module")


def test_normalize_protocol_payload_rehashes_pretty() -> None:
    from lpe.hashing import sha256_text
    from lpe.lean.generic import _normalize_protocol_payload

    pretty = "Nat -> Nat"
    raw = {
        "schema_version": "2.0",
        "snapshot_fingerprint": "fp",
        "declarations": [
            {
                "fqn": "Foo.id",
                "kind": "definition",
                "module": "Foo",
                "type_pretty": pretty,
                "type_expr_hash": "not-a-sha256",
            }
        ],
    }
    result = _normalize_protocol_payload(
        raw, snapshot_fingerprint="fp", toolchain_spec="leanprover/lean4:v4.14.0"
    )
    assert result.declarations[0].type_expr_hash == sha256_text(pretty)


def test_try_generic_extract_absent_lake_returns_none(tmp_path: Path) -> None:
    from lpe.lean.generic import try_generic_extract

    (tmp_path / "README.md").write_text("no lake\n", encoding="utf-8")
    assert try_generic_extract(tmp_path, dry_run=True) is None


def test_run_generic_extract_live_path_with_mocked_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Live injector path without network/Lake: mock executor + protocol JSON."""
    from lpe.execution.protocol import ExecutionResult
    from lpe.lean import generic as generic_mod
    from lpe.lean.generic import run_generic_extract

    (tmp_path / "lakefile.toml").write_text(
        'name = "MockPkg"\n[[lean_lib]]\nname = "MockPkg"\n',
        encoding="utf-8",
    )
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.14.0\n", encoding="utf-8")
    (tmp_path / "MockPkg.lean").write_text("def x := 1\n", encoding="utf-8")

    class FakeExecutor:
        def verify_build(
            self,
            repository: Path,
            command: list[str],
            timeout_seconds: int,
            max_output_bytes: int,
            environment_allowlist: list[str],
        ) -> ExecutionResult:
            if command[:2] == ["lake", "exe"]:
                out = repository / ".lpe" / "lean-extraction-v2.json"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(
                    json.dumps(
                        {
                            "schema_version": "2.0",
                            "snapshot_fingerprint": "fp-mock",
                            "toolchain_spec": "leanprover/lean4:v4.14.0",
                            "extractor": "lean.generic-injector",
                            "declarations": [
                                {
                                    "fqn": "MockPkg.x",
                                    "kind": "definition",
                                    "module": "MockPkg",
                                    "type_pretty": "Nat",
                                    "type_expr_hash": "a" * 64,
                                }
                            ],
                            "errors": [],
                            "notes": ["mocked"],
                            "completeness": {"environment_loaded": True},
                        }
                    ),
                    encoding="utf-8",
                )
            return ExecutionResult(
                command=tuple(command),
                cwd=repository,
                exit_code=0,
                stdout="",
                stderr="",
                elapsed_ms=1,
                timed_out=False,
            )

        def run(self, **kwargs):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    monkeypatch.setattr(
        generic_mod,
        "_copy_extractor_sources",
        lambda dest: None,
    )
    monkeypatch.setattr(
        generic_mod,
        "_write_ephemeral_lakefile",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        generic_mod,
        "_write_aggregator",
        lambda *a, **k: None,
    )

    result = run_generic_extract(
        tmp_path,
        snapshot_fingerprint="fp-mock",
        executor=FakeExecutor(),  # type: ignore[arg-type]
        dry_run=False,
    )
    assert not result.has_blocking_errors
    assert any(d.fqn == "MockPkg.x" for d in result.declarations)
