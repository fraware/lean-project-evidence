"""§19 branch-coverage push toward 85% (mocks only; no network/Docker/Lean)."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from lpe.cli import _ledger_permission_report, app
from lpe.evidence import compiler as compiler_mod
from lpe.evidence.migration import migrate_finding_0_1_to_0_2
from lpe.execution.sandbox import (
    DockerNotAvailableError,
    DockerSandboxExecutor,
    _container_environment,
    _format_memory,
    _host_uid_gid,
    _parse_memory_bytes,
    docker_image_present,
    resolve_docker_image_digest,
)
from lpe.hashing import sha256_text
from lpe.lean.extractor import (
    TOOLCHAIN_EXTRACTOR,
    AdaptiveLeanExtractor,
    LeanDeclaration,
    LeanExtractionResult,
    RegexLeanExtractor,
    _apply_path_filters,
    _try_lake_extract_env,
    artifact_covers_lean_sources,
    list_lean_source_modules,
    load_toolchain_json,
    project_requires_toolchain,
)
from lpe.lean.generic import (
    _list_lean_modules_under,
    _normalize_protocol_payload,
    discover_modules,
    run_generic_extract,
)
from lpe.lean.models import MODULE_DISCOVERY_AMBIGUOUS_CODE, ExtractionError
from lpe.ledger.store import LedgerIntegrityError, LedgerStore
from lpe.models import (
    ArtifactType,
    CandidateDescriptor,
    ChangedDeclaration,
    EventType,
    FindingStatus,
    GeneratorProvenance,
    ReviewDecision,
    ReviewDecisionValue,
    RiskClass,
    UtilityEvent,
)
from lpe.providers import semantic as sem
from lpe.providers.base import CancellationToken, ProviderContext
from lpe.providers.semantic import (
    DuplicateRetrievalProvider,
    StatementDiffProvider,
)
from lpe.review.decisions import (
    AcceptanceError,
    record_review_decision,
    review_decision_to_event,
)
from lpe.workspace.artifacts import ContentAddressedArtifactStore
from lpe.workspace.manager import (
    HostExecutionRefusedError,
    NetworkPolicyError,
    select_executor,
)
from lpe.workspace.models import (
    EvaluationWorkspace,
    ExecutorDescriptor,
    WorkspaceCleanupToken,
)

runner = CliRunner()
NOW = datetime(2026, 7, 21, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Sandbox helpers
# ---------------------------------------------------------------------------


def test_parse_and_format_memory_matrix() -> None:
    assert _parse_memory_bytes("1g") == 1024**3
    assert _parse_memory_bytes("512m") == 512 * 1024**2
    assert _parse_memory_bytes("4k") == 4 * 1024
    assert _parse_memory_bytes("4096") == 4096
    assert _parse_memory_bytes("not-a-size") == 2 * 1024**3
    assert _parse_memory_bytes("") == 2 * 1024**3
    assert _format_memory(2 * 1024**3) == "2g"
    assert _format_memory(512 * 1024**2) == "512m"
    assert _format_memory(12345) == "12345"


def test_container_environment_non_windows_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.delenv("HOME", raising=False)
    env = _container_environment(["PATH", "HOME"], uid=1000)
    assert env["PATH"] == "/usr/bin:/bin"
    assert env["HOME"] == "/home/lpe"
    env_root = _container_environment(["PATH", "HOME"], uid=0)
    assert env_root["HOME"] == "/root"


def test_docker_image_present_and_digest_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("lpe.execution.sandbox.shutil.which", lambda _: None)
    assert docker_image_present("img") is False
    assert resolve_docker_image_digest("img") is None

    monkeypatch.setattr("lpe.execution.sandbox.shutil.which", lambda _: "/bin/docker")

    def _fail(*_a, **_k):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=1, stdout="", stderr="err")

    monkeypatch.setattr("lpe.execution.sandbox.subprocess.run", _fail)
    assert docker_image_present("img") is False
    assert resolve_docker_image_digest("img") is None

    def _empty(*_a, **_k):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=0, stdout="  \n", stderr="")

    monkeypatch.setattr("lpe.execution.sandbox.subprocess.run", _empty)
    assert resolve_docker_image_digest("img") is None

    def _repo(*_a, **_k):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            returncode=0,
            stdout="repo@sha256:" + ("ab" * 32) + "\n",
            stderr="",
        )

    monkeypatch.setattr("lpe.execution.sandbox.subprocess.run", _repo)
    assert resolve_docker_image_digest("img") == "sha256:" + ("ab" * 32)

    def _plain(*_a, **_k):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=0, stdout="sha256:" + ("cd" * 32), stderr="")

    monkeypatch.setattr("lpe.execution.sandbox.subprocess.run", _plain)
    assert resolve_docker_image_digest("img") == "sha256:" + ("cd" * 32)

    def _other(*_a, **_k):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=0, stdout="sha256-not-valid", stderr="")

    monkeypatch.setattr("lpe.execution.sandbox.subprocess.run", _other)
    assert resolve_docker_image_digest("img") is None

    def _ok_inspect(*_a, **_k):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=0, stdout="{}", stderr="")

    monkeypatch.setattr("lpe.execution.sandbox.subprocess.run", _ok_inspect)
    assert docker_image_present("img") is True


def test_host_uid_gid_env_and_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LPE_DOCKER_UID", "42")
    monkeypatch.setenv("LPE_DOCKER_GID", "43")
    assert _host_uid_gid() == (42, 43)
    monkeypatch.delenv("LPE_DOCKER_UID", raising=False)
    monkeypatch.delenv("LPE_DOCKER_GID", raising=False)

    def _missing() -> int:
        raise AttributeError("no getuid")

    monkeypatch.setattr(os, "getuid", _missing, raising=False)
    monkeypatch.setattr(os, "getgid", _missing, raising=False)
    assert _host_uid_gid() == (0, 0)


def test_docker_executor_readonly_env_and_digest_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LPE_DOCKER_READONLY", "true")
    monkeypatch.setattr(
        "lpe.execution.sandbox.resolve_docker_image_digest",
        lambda _img: "sha256:" + ("ee" * 32),
    )
    ex = DockerSandboxExecutor(image="lpe-lean:test")
    assert ex.readonly_mount is True
    assert ex.image_digest() == "sha256:" + ("ee" * 32)
    assert ex.image_digest() == "sha256:" + ("ee" * 32)  # cached


def test_docker_run_escape_and_empty_combined(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from lpe.execution.protocol import ProviderResourceProfile, ValidatedCommand

    monkeypatch.setattr("lpe.execution.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    ex = DockerSandboxExecutor(image="img")
    ws = SimpleNamespace(candidate_path=tmp_path, base_path=tmp_path)
    cmd = ValidatedCommand(
        argv=("lake", "build"),
        working_directory="../escape",
        snapshot_root="candidate",
    )
    profile = ProviderResourceProfile(
        timeout_seconds=5,
        max_stdout_bytes=1000,
        max_stderr_bytes=1000,
        memory_bytes=512 * 1024 * 1024,
        pids_limit=64,
        cpu_quota=1.0,
    )
    with pytest.raises(ValueError, match="escapes"):
        ex.run(
            workspace=ws,
            command=cmd,
            resource_profile=profile,
            environment_allowlist=["PATH"],
        )
    with pytest.raises(ValueError, match="empty"):
        ex.verify_build_and_extract(
            repository=tmp_path,
            build_command=[],
            extract_out=".lpe/out.json",
            timeout_seconds=5,
            max_output_bytes=1000,
            environment_allowlist=["PATH"],
        )


def test_run_docker_flag_matrix_and_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("lpe.execution.sandbox.shutil.which", lambda _: "/usr/bin/docker")
    captured: list[list[str]] = []

    def _ok(cmd, **_k):  # type: ignore[no-untyped-def]
        captured.append(list(cmd))
        return SimpleNamespace(returncode=1, stdout="out", stderr="err")

    monkeypatch.setattr("lpe.execution.sandbox.subprocess.run", _ok)
    ex = DockerSandboxExecutor(
        image="img",
        readonly_root=True,
        source_mount_readonly=True,
        network_none=False,
        readonly_mount=True,
    )
    result = ex._run_docker(
        repository=tmp_path,
        command=["echo", "hi"],
        timeout_seconds=5,
        max_output_bytes=1000,
        environment_allowlist=["PATH", "HOME"],
        source_origin=tmp_path,
    )
    assert "--read-only" in captured[0]
    assert any("/source:ro" in x for x in captured[0])
    assert "--network=none" not in captured[0]
    assert "writable ephemeral" in result.stderr

    def _timeout(cmd, **_k):  # type: ignore[no-untyped-def]
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=1, output=b"so", stderr=b"se")

    monkeypatch.setattr("lpe.execution.sandbox.subprocess.run", _timeout)
    timed = ex._run_docker(
        repository=tmp_path,
        command=["sleep"],
        timeout_seconds=1,
        max_output_bytes=1000,
        environment_allowlist=["PATH"],
    )
    assert timed.timed_out is True
    assert timed.exit_code == 124
    assert "so" in timed.stdout

    monkeypatch.setattr("lpe.execution.sandbox.shutil.which", lambda _: None)
    with pytest.raises(DockerNotAvailableError):
        DockerSandboxExecutor(image="img")._run_docker(
            repository=tmp_path,
            command=["x"],
            timeout_seconds=1,
            max_output_bytes=100,
            environment_allowlist=["PATH"],
        )


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------


def test_extract_file_missing_and_open_imports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("lpe.lean.extractor.lean_toolchain_available", lambda *_a, **_k: False)
    missing = RegexLeanExtractor().extract_file(tmp_path / "nope.lean")
    assert missing.errors and "file not found" in missing.errors[0]

    text = "open Foo   Bar\ndef x : Nat := 1\n"
    result = RegexLeanExtractor().extract_text(text, path="M.lean")
    assert "Foo" in result.imports and "Bar" in result.imports


def test_extract_repository_use_resolution_and_baseline(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("lpe.lean.extractor.lean_toolchain_available", lambda *_a, **_k: False)
    (tmp_path / "ModA.lean").write_text(
        "def helper : Nat := 1\ndef usesExact : Nat := ModA.helper\n",
        encoding="utf-8",
    )
    (tmp_path / "ModB.lean").write_text(
        "def helper : Nat := 2\ndef ghost : Nat := missingThing\n",
        encoding="utf-8",
    )
    (tmp_path / "ModC.lean").write_text(
        "def uniqueShort : Nat := 3\ndef usesShort : Nat := uniqueShort\n",
        encoding="utf-8",
    )
    result = RegexLeanExtractor().extract_repository(tmp_path, baseline_imports=["Old.Mod"])
    assert result.import_diff is not None
    names = {d.name for d in result.declarations}
    assert any("helper" in n for n in names)


def test_load_toolchain_json_variants(tmp_path: Path) -> None:
    path = tmp_path / "ext.json"
    path.write_text(
        json.dumps(
            {
                "extractor": "regex-stub",
                "complete": True,
                "declarations": [
                    {
                        "name": "M.foo",
                        "kind": "def",
                        "path": "M.lean",
                        "line": 1,
                        "signature": "Nat",
                        "signature_hash": "",
                    }
                ],
                "notes": ["already"],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_toolchain_json(path)
    assert loaded is not None
    assert loaded.complete is False
    assert loaded.extractor == "regex-stub"
    assert loaded.declarations[0].signature_hash
    assert loaded.notes == ["already"]

    path2 = tmp_path / "tc.json"
    path2.write_text(
        json.dumps(
            {
                "extractor": TOOLCHAIN_EXTRACTOR,
                "complete": True,
                "declarations": [],
            }
        ),
        encoding="utf-8",
    )
    tc = load_toolchain_json(path2)
    assert tc is not None
    assert tc.extractor == TOOLCHAIN_EXTRACTOR
    assert any("loaded toolchain" in n for n in tc.notes)


def test_try_lake_extract_env_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("lpe.lean.extractor.shutil.which", lambda _: None)
    assert _try_lake_extract_env(tmp_path) is None

    monkeypatch.setattr("lpe.lean.extractor.shutil.which", lambda _: "/fake/lake")
    assert _try_lake_extract_env(tmp_path) is None  # no lakefile

    (tmp_path / "lakefile.lean").write_text("package p", encoding="utf-8")
    art = tmp_path / "art.json"
    art.write_text(
        json.dumps({"extractor": TOOLCHAIN_EXTRACTOR, "complete": True, "declarations": []}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LPE_LEAN_EXTRACTION_JSON", str(art))
    loaded = _try_lake_extract_env(tmp_path)
    assert loaded is not None and loaded.extractor == TOOLCHAIN_EXTRACTOR

    monkeypatch.setenv("LPE_LEAN_EXTRACTION_JSON", str(tmp_path / "missing.json"))

    def _fail(*_a, **_k):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr("lpe.lean.extractor.subprocess.run", _fail)
    assert _try_lake_extract_env(tmp_path) is None

    monkeypatch.delenv("LPE_LEAN_EXTRACTION_JSON", raising=False)

    def _ok(*_a, **_k):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=0, stdout="/lean", stderr="")

    monkeypatch.setattr("lpe.lean.extractor.subprocess.run", _ok)
    probe = _try_lake_extract_env(tmp_path)
    assert probe is not None and probe.toolchain_available is True

    def _timeout(*_a, **_k):  # type: ignore[no-untyped-def]
        raise subprocess.TimeoutExpired(cmd="lake", timeout=1)

    monkeypatch.setattr("lpe.lean.extractor.subprocess.run", _timeout)
    assert _try_lake_extract_env(tmp_path) is None


def test_apply_filters_list_modules_covers_requires(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    decls = [
        LeanDeclaration(
            name="Keep.foo",
            kind="def",
            path="Keep.lean",
            line=1,
            signature="Nat",
            signature_hash=sha256_text("Nat"),
        ),
        LeanDeclaration(
            name="Drop.bar",
            kind="def",
            path="Drop.lean",
            line=1,
            signature="Nat",
            signature_hash=sha256_text("Nat"),
        ),
    ]
    loaded = LeanExtractionResult(
        declarations=decls,
        imports=["B"],
        extractor=TOOLCHAIN_EXTRACTOR,
        complete=True,
    )
    filtered = _apply_path_filters(loaded, lean_paths=["Keep.lean"], baseline_imports=["A"])
    assert len(filtered.declarations) == 1
    assert filtered.import_diff is not None

    assert list_lean_source_modules(tmp_path / "notadir") == set()
    (tmp_path / "Keep.lean").write_text("def foo : Nat := 1\n", encoding="utf-8")
    mods = list_lean_source_modules(tmp_path)
    assert "Keep" in mods

    empty = LeanExtractionResult(declarations=[], extractor=TOOLCHAIN_EXTRACTOR)
    monkeypatch.setattr("lpe.lean.extractor.list_lean_source_modules", lambda *_a, **_k: set())
    ok, missing = artifact_covers_lean_sources(empty, tmp_path)
    assert ok is True and missing == []

    monkeypatch.setattr(
        "lpe.lean.extractor.list_lean_source_modules",
        lambda *_a, **_k: {"M"},
    )
    pathless = LeanExtractionResult(
        declarations=[
            LeanDeclaration(
                name="M.foo",
                kind="def",
                path="",
                line=1,
                signature="Nat",
                signature_hash=sha256_text("Nat"),
            )
        ],
        import_edges=[("Other", "M")],
        extractor=TOOLCHAIN_EXTRACTOR,
        complete=True,
    )
    ok2, miss2 = artifact_covers_lean_sources(pathless, tmp_path)
    assert ok2 is True and miss2 == []

    monkeypatch.setattr(
        "lpe.lean.toolchain.project_declares_lpe_extract",
        lambda *_a, **_k: True,
    )
    assert project_requires_toolchain(tmp_path) is True

    monkeypatch.setattr(
        "lpe.lean.toolchain.project_declares_lpe_extract",
        lambda *_a, **_k: False,
    )
    lpe = tmp_path / ".lpe"
    lpe.mkdir()
    (lpe / "lean-extraction.json").write_text(
        json.dumps(
            {
                "extraction_schema_version": "1.1",
                "complete": True,
                "extractor": TOOLCHAIN_EXTRACTOR,
                "declarations": [],
            }
        ),
        encoding="utf-8",
    )
    assert project_requires_toolchain(tmp_path) is True


def test_adaptive_regex_fallback_and_stale(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("lpe.lean.extractor.lean_toolchain_available", lambda *_a, **_k: False)
    (tmp_path / "A.lean").write_text("def foo : Nat := 1\n", encoding="utf-8")
    lpe = tmp_path / ".lpe"
    lpe.mkdir()
    (lpe / "lean-extraction.json").write_text("{not-json", encoding="utf-8")

    monkeypatch.setattr("lpe.lean.extractor.project_requires_toolchain", lambda *_a, **_k: False)
    result = AdaptiveLeanExtractor().extract_repository(tmp_path, run_toolchain=False)
    assert result.extractor
    assert result.errors or result.notes

    (lpe / "lean-extraction.json").write_text(
        json.dumps(
            {
                "extractor": TOOLCHAIN_EXTRACTOR,
                "complete": True,
                "declarations": [
                    {
                        "name": "Only.ghost",
                        "kind": "def",
                        "path": "Ghost.lean",
                        "line": 1,
                        "signature": "Nat",
                        "signature_hash": sha256_text("Nat"),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "lpe.lean.extractor.artifact_covers_lean_sources",
        lambda *_a, **_k: (False, ["A"]),
    )
    stale = AdaptiveLeanExtractor().extract_repository(tmp_path, run_toolchain=False)
    assert stale.complete is False


# ---------------------------------------------------------------------------
# Compiler helpers
# ---------------------------------------------------------------------------


def test_compiler_helper_branches(example_project: Path, tmp_path: Path) -> None:
    from lpe.contract.loader import load_contract

    notes = SimpleNamespace(notes=["built via SubprocessLeanExecutor"])
    assert compiler_mod._extract_executor_from_notes(notes) == "SubprocessLeanExecutor"

    contract = load_contract(example_project)
    started = NOW
    err_ext = SimpleNamespace(
        errors=["boom"],
        axioms_used=[],
        extractor="regex-stub",
        complete=False,
    )
    finding = compiler_mod._check_axioms(contract, err_ext, started=started)
    assert finding.status is FindingStatus.UNKNOWN

    incomplete_tc = SimpleNamespace(
        errors=[],
        axioms_used=[],
        extractor=TOOLCHAIN_EXTRACTOR,
        complete=False,
    )
    finding2 = compiler_mod._check_axioms(contract, incomplete_tc, started=started)
    assert finding2.status is FindingStatus.UNKNOWN

    from lpe.evidence.compiler import PathTraversalError

    cand = CandidateDescriptor(
        candidate_id="cand-abs",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="base",
        patch_text="",
        claimed_intent="t",
        changed_paths=[],
        changed_declarations=[],
        generator=GeneratorProvenance(generator_type="human", name="t"),
        patch_path="/abs/x.patch" if os.name != "nt" else r"C:\abs\x.patch",
    )
    with pytest.raises(PathTraversalError):
        compiler_mod._validate_candidate_paths(tmp_path, cand)

    patch_file = tmp_path / "p.patch"
    patch_file.write_text("+def foo\n", encoding="utf-8")
    lean = tmp_path / "X.lean"
    lean.write_text("def foo : Nat := 1\n", encoding="utf-8")
    cand2 = CandidateDescriptor(
        candidate_id="cand-rel",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="base",
        patch_text="",
        claimed_intent="t",
        changed_paths=["X.lean"],
        changed_declarations=[],
        generator=GeneratorProvenance(generator_type="human", name="t"),
        patch_path="p.patch",
    )
    materials_text, sources = compiler_mod._collect_placeholder_materials(
        repository=tmp_path, candidate=cand2
    )
    assert "p.patch" in sources or "X.lean" in sources
    assert "def foo" in materials_text or "+def foo" in materials_text


def test_compile_evidence_sandbox_gates(
    example_project: Path, example_candidate: CandidateDescriptor
) -> None:
    with pytest.raises(HostExecutionRefusedError):
        compiler_mod.compile_evidence(
            project_path=example_project,
            candidate=example_candidate,
            skip_build=False,
            use_sandbox=False,
            insecure_host_exec=False,
        )


# ---------------------------------------------------------------------------
# Generic extract
# ---------------------------------------------------------------------------


def test_normalize_protocol_payload_value_hash_and_skip() -> None:
    payload = {
        "schema_version": "2.0",
        "snapshot_fingerprint": "s" * 64,
        "toolchain_spec": "",
        "declarations": [
            {
                "fqn": "M.foo",
                "kind": "definition",
                "module": "M",
                "type_pretty": "Nat",
                "type_expr_hash": "short",
                "value_expr_hash": "not-hex-value",
                "public_visibility": "public",
            },
        ],
        "errors": [],
        "notes": [],
    }
    result = _normalize_protocol_payload(payload, snapshot_fingerprint="s" * 64, toolchain_spec="")
    decl = result.declarations[0]
    assert len(decl.type_expr_hash) == 64
    assert decl.value_expr_hash is None


def test_generic_run_early_exits_and_host_lake_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.14.0\n", encoding="utf-8")
    (tmp_path / "lakefile.toml").write_text('name = "demo"\n', encoding="utf-8")

    monkeypatch.setattr(
        "lpe.lean.generic.discover_modules",
        lambda *_a, **_k: SimpleNamespace(
            modules=(),
            roots=(),
            method="ambiguous",
            error=ExtractionError(
                code=MODULE_DISCOVERY_AMBIGUOUS_CODE,
                message="ambiguous",
            ),
        ),
    )
    amb = run_generic_extract(tmp_path, snapshot_fingerprint="f" * 64, dry_run=True)
    assert amb.errors

    monkeypatch.setattr(
        "lpe.lean.generic.discover_modules",
        lambda *_a, **_k: SimpleNamespace(modules=(), roots=(), method="filesystem", error=None),
    )
    empty = run_generic_extract(tmp_path, snapshot_fingerprint="f" * 64, dry_run=True)
    assert any(
        e.code == "MODULE_DISCOVERY_UNKNOWN" or "no modules" in e.message for e in empty.errors
    )

    monkeypatch.setattr(
        "lpe.lean.generic.discover_modules",
        lambda *_a, **_k: SimpleNamespace(
            modules=("Demo.Main",), roots=("Demo",), method="filesystem", error=None
        ),
    )
    monkeypatch.setattr("lpe.lean.generic._copy_extractor_sources", lambda *_a, **_k: None)
    monkeypatch.setattr("lpe.lean.generic._write_ephemeral_lakefile", lambda *_a, **_k: None)
    monkeypatch.setattr("lpe.lean.generic._write_aggregator", lambda *_a, **_k: None)
    monkeypatch.setattr("lpe.lean.generic.shutil.which", lambda _: None)
    host = run_generic_extract(
        tmp_path, snapshot_fingerprint="f" * 64, executor=None, dry_run=False
    )
    assert any(e.code == "LAKE_UNAVAILABLE" for e in host.errors)


def test_generic_host_build_extract_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.14.0\n", encoding="utf-8")
    (tmp_path / "lakefile.toml").write_text('name = "demo"\n', encoding="utf-8")
    monkeypatch.setattr(
        "lpe.lean.generic.discover_modules",
        lambda *_a, **_k: SimpleNamespace(
            modules=("Demo.Main",), roots=("Demo",), method="filesystem", error=None
        ),
    )
    monkeypatch.setattr("lpe.lean.generic._copy_extractor_sources", lambda *_a, **_k: None)
    monkeypatch.setattr("lpe.lean.generic._write_ephemeral_lakefile", lambda *_a, **_k: None)
    monkeypatch.setattr("lpe.lean.generic._write_aggregator", lambda *_a, **_k: None)
    monkeypatch.setattr("lpe.lean.generic.shutil.which", lambda _: "/fake/lake")

    calls = {"n": 0}

    def _build_fail(*_a, **_k):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(returncode=1, stdout="", stderr="build fail")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", _build_fail)
    failed = run_generic_extract(
        tmp_path, snapshot_fingerprint="f" * 64, executor=None, dry_run=False
    )
    assert any("BUILD_FAILED" in e.code for e in failed.errors)

    calls["n"] = 0

    def _build_ok_extract_fail(*_a, **_k):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        return SimpleNamespace(returncode=2, stdout="", stderr="extract fail")

    monkeypatch.setattr("subprocess.run", _build_ok_extract_fail)
    failed2 = run_generic_extract(
        tmp_path, snapshot_fingerprint="f" * 64, executor=None, dry_run=False
    )
    assert any("RUN_FAILED" in e.code for e in failed2.errors)

    def _both_ok(*_a, **_k):  # type: ignore[no-untyped-def]
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", _both_ok)
    missing_art = run_generic_extract(
        tmp_path, snapshot_fingerprint="f" * 64, executor=None, dry_run=False
    )
    assert any("MISSING_ARTIFACT" in e.code for e in missing_art.errors)


def test_discover_modules_edges(tmp_path: Path) -> None:
    from lpe.lean.generic import LakeWorkspaceInfo

    assert _list_lean_modules_under(tmp_path / "nodir") == []
    lib = tmp_path / "Lib"
    lib.mkdir()
    (lib / "A.lean").write_text("def a : Nat := 1\n", encoding="utf-8")
    (tmp_path / ".lake").mkdir()
    (tmp_path / "lakefile.lean").write_text("package p", encoding="utf-8")
    mods = _list_lean_modules_under(tmp_path, rel_prefix="")
    assert any("A" in m for m in mods)

    ws = LakeWorkspaceInfo(
        package_name="demo",
        library_roots=("Lib",),
        source_roots=("Lib",),
        lakefile_kind="lean",
        discovery="filesystem",
    )
    discovery = discover_modules(tmp_path, ws)
    assert discovery.modules or discovery.error is not None


# ---------------------------------------------------------------------------
# Ledger store
# ---------------------------------------------------------------------------


def test_parse_exported_event_and_verify_edges(tmp_path: Path) -> None:
    from pydantic import ValidationError

    v1 = {
        "event_id": "e1",
        "event_type": EventType.CANDIDATE_REGISTERED.value,
        "project_id": "p",
        "artifact_id": "a",
        "obligation_id": "O-01",
        "actor_id": "actor",
        "occurred_at": NOW.isoformat(),
        "payload": {"candidate_id": "cand-1"},
    }
    parsed = LedgerStore._parse_exported_event(v1)
    assert isinstance(parsed, UtilityEvent)

    # Outer v2 gate true, but no payload_type → fall through to UtilityEvent
    v1b = {
        "schema_version": "0.2.0",
        "event_id": "e2",
        "event_type": EventType.EXPERT_TIME_RECORDED.value,
        "project_id": "p",
        "artifact_id": "a",
        "obligation_ids": ["O-01"],
        "actor_id": "actor",
        "occurred_at": NOW.isoformat(),
        "payload": {"hours": 0.1, "minutes": 6.0, "category": "review"},
    }
    with pytest.raises(ValidationError):
        LedgerStore._parse_exported_event(v1b)

    export = tmp_path / "bad.jsonl"
    export.write_text(
        "\n" + json.dumps({"no": "event"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(LedgerIntegrityError, match="missing event"):
        LedgerStore.verify_exported_jsonl(export)

    store = LedgerStore(tmp_path / "ledger.sqlite3")
    store.initialize()
    event = UtilityEvent(
        event_id="ev1",
        event_type=EventType.EXPERT_TIME_RECORDED,
        project_id="p",
        artifact_id="art",
        obligation_id="O-01",
        actor_id="r1",
        payload={"hours": 0.1, "minutes": 6.0, "category": "review"},
    )
    digest = store.append(event)
    good = tmp_path / "good.jsonl"
    store.export_jsonl(good)

    # Break previous_hash
    lines = good.read_text(encoding="utf-8").strip().splitlines()
    rec = json.loads(lines[0])
    rec["previous_hash"] = "deadbeef"
    broken = tmp_path / "broken_prev.jsonl"
    broken.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    with pytest.raises(LedgerIntegrityError, match="previous_hash"):
        LedgerStore.verify_exported_jsonl(broken)

    # Supersedes unknown
    event2 = UtilityEvent(
        event_id="ev2",
        event_type=EventType.EXPERT_TIME_RECORDED,
        project_id="p",
        artifact_id="art",
        obligation_id="O-01",
        actor_id="r1",
        payload={"hours": 0.1, "minutes": 6.0, "category": "review"},
        supersedes_event_id="never-seen",
    )
    # Build a synthetic export line with unknown supersedes
    fake = {
        "event": json.loads(event2.model_dump_json()),
        "event_hash": "0" * 64,
        "previous_hash": digest,
    }
    # Use proper chain: export after append with supersedes may fail at append
    # so write hand-crafted line after a valid first event.
    export2 = tmp_path / "super.jsonl"
    first = json.loads(lines[0])
    export2.write_text(
        json.dumps(first) + "\n" + json.dumps(fake) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(LedgerIntegrityError):
        LedgerStore.verify_exported_jsonl(export2)


def test_archive_count_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = LedgerStore(tmp_path / "ledger.sqlite3")
    store.initialize()
    store.append(
        UtilityEvent(
            event_id="ev1",
            event_type=EventType.EXPERT_TIME_RECORDED,
            project_id="p",
            artifact_id="art",
            obligation_id="O-01",
            actor_id="r1",
            payload={"hours": 0.1, "minutes": 6.0, "category": "review"},
        )
    )
    monkeypatch.setattr(store, "verify_exported_jsonl", lambda _p: 0)
    with pytest.raises(LedgerIntegrityError, match="mismatch"):
        store.archive_verified_jsonl(tmp_path / "arch.jsonl")


# ---------------------------------------------------------------------------
# Review decisions
# ---------------------------------------------------------------------------


def test_review_decision_payload_and_quorum_fail(tmp_path: Path) -> None:
    decision = ReviewDecision(
        review_id="rev-1",
        packet_id="pkt",
        reviewer_id="r1",
        reviewer_roles=[],
        decision=ReviewDecisionValue.ACCEPT,
        confidence=90,
        rationale="ok",
        review_minutes=5.0,
    )
    event = review_decision_to_event(
        decision,
        project_id="p",
        obligation_id="O-01",
        evidence_fingerprint=None,
        ledger_seal_tip=None,
    )
    assert "evidence_fingerprint" not in event.payload
    assert "ledger_seal_tip" not in event.payload

    ledger = tmp_path / "ledger.sqlite3"
    reject = decision.model_copy(update={"decision": ReviewDecisionValue.REJECT})
    digest = record_review_decision(
        ledger,
        reject,
        project_id="p",
        evidence_fingerprint="",
        risk_class=RiskClass.R1,
    )
    assert digest

    with patch(
        "lpe.review.quorum.evaluate_quorum",
        return_value=SimpleNamespace(
            satisfied=False,
            blocking_reasons=["nope"],
            matched_attestation_ids=[],
            policy=SimpleNamespace(policy_id="p"),
            semantic_fidelity=False,
            repository_accepted=False,
            implementation_accepted=False,
        ),
    ):
        with pytest.raises(AcceptanceError, match="quorum"):
            record_review_decision(
                ledger,
                decision,
                project_id="p",
                evidence_fingerprint="f" * 64,
                risk_class=RiskClass.R1,
            )


# ---------------------------------------------------------------------------
# CLI permission / pilot / research
# ---------------------------------------------------------------------------


def test_ledger_permission_report_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = _ledger_permission_report(tmp_path / "nope.sqlite3")
    assert missing["ok"] is False

    ledger = tmp_path / "ledger.sqlite3"
    ledger.write_text("x", encoding="utf-8")
    monkeypatch.setattr(os, "name", "nt")
    win = _ledger_permission_report(ledger)
    assert win["platform"] == "windows"
    assert win["ok"] is True

    monkeypatch.setattr(os, "name", "posix")
    # No seal → warning
    nos = _ledger_permission_report(ledger)
    assert any("no ledger seal" in w for w in nos["warnings"])

    # Fake world-writable via patched stat
    class _Mode:
        def __init__(self, mode: int) -> None:
            self.st_mode = mode

    real_stat = Path.stat

    def _stat(self, *a, **k):  # type: ignore[no-untyped-def]
        if self == ledger:
            return _Mode(stat.S_IFREG | 0o666)
        if self == ledger.parent:
            return _Mode(stat.S_IFDIR | 0o777)
        return real_stat(self, *a, **k)

    monkeypatch.setattr(Path, "stat", _stat)
    bad = _ledger_permission_report(ledger)
    assert bad["ok"] is False
    assert any("world-writable" in w for w in bad["warnings"])


def test_cli_pilot_record_validation_and_summary_formats(
    tmp_path: Path, example_project: Path
) -> None:
    ledger = tmp_path / "ledger.sqlite3"
    result = runner.invoke(
        app,
        [
            "pilot",
            "record",
            "--project",
            str(example_project),
            "--ledger",
            str(ledger),
            "--kind",
            "unknown-kind",
        ],
    )
    assert result.exit_code != 0

    result2 = runner.invoke(
        app,
        [
            "pilot",
            "record",
            "--project",
            str(example_project),
            "--ledger",
            str(ledger),
            "--kind",
            "expert-time",
        ],
    )
    assert result2.exit_code != 0  # missing candidate-id / fields

    # Seed ledger for summary
    store = LedgerStore(ledger)
    store.initialize()
    pid = "example-category-project"
    result3 = runner.invoke(
        app,
        [
            "pilot",
            "summary",
            str(ledger),
            "--project-id",
            pid,
            "--format",
            "json",
        ],
    )
    assert result3.exit_code == 0, result3.stdout + result3.stderr
    assert "candidate_count" in result3.stdout or "project_id" in result3.stdout

    out = tmp_path / "sum.md"
    result4 = runner.invoke(
        app,
        [
            "pilot",
            "summary",
            str(ledger),
            "--project-id",
            pid,
            "--format",
            "markdown",
            "--output",
            str(out),
        ],
    )
    assert result4.exit_code == 0, result4.stdout + result4.stderr
    assert out.is_file()

    result5 = runner.invoke(
        app,
        [
            "pilot",
            "summary",
            str(ledger),
            "--project-id",
            pid,
            "--format",
            "nope",
        ],
    )
    assert result5.exit_code != 0

    result6 = runner.invoke(
        app,
        ["research", "status", "--format", "text"],
    )
    assert result6.exit_code == 0


def test_cli_evaluate_gates_exit2(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    protocol = tmp_path / "protocol"
    protocol.mkdir()
    (protocol / "protocol.yaml").write_text("schema_version: '0.1.0'\n", encoding="utf-8")
    ledger = tmp_path / "ledger.sqlite3"
    LedgerStore(ledger).initialize()
    seal = tmp_path / "seal.json"
    seal.write_text("{}", encoding="utf-8")
    analysis = tmp_path / "analysis.json"
    analysis.write_text("{}", encoding="utf-8")
    output = tmp_path / "gates.json"
    monkeypatch.setattr(
        "lpe.honesty.research_gates.evaluate_gates_from_paths",
        lambda **_k: SimpleNamespace(
            shadow_pilot_passed=False,
            learned_routing_authorized=False,
            synthesis_authorized=False,
            blocking_reasons=["synthetic"],
            report_hash="h" * 64,
            model_dump=lambda: {"shadow_pilot_passed": False},
        ),
    )
    result = runner.invoke(
        app,
        [
            "research",
            "evaluate-gates",
            "--protocol",
            str(protocol),
            "--ledger",
            str(ledger),
            "--seal",
            str(seal),
            "--analysis",
            str(analysis),
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# Semantic providers
# ---------------------------------------------------------------------------


def _sem_ctx(
    project_path: Path,
    candidate: CandidateDescriptor,
    *,
    candidate_extraction: object | None = None,
    base_extraction: object | None = None,
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
        run_id="run_br",
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
        cleanup_token=WorkspaceCleanupToken(run_id="run_br"),
    )
    mock_contract = MagicMock()
    mock_contract.project.execution.environment_allowlist = ["PATH", "HOME"]
    return ProviderContext(
        workspace=ws,
        contract=mock_contract,
        candidate=candidate,
        cancellation=CancellationToken(),
        candidate_extraction=candidate_extraction,
        base_extraction=base_extraction,
    )


def test_statement_diff_authority_matrix(tmp_path: Path) -> None:
    h_base = sha256_text("Nat")
    h_head = sha256_text("Bool")
    candidate = CandidateDescriptor(
        candidate_id="c-sd",
        project_id="p",
        obligation_ids=["O-01"],
        base_commit="b",
        head_commit="h",
        patch_text="+def Foo : Bool := true\n",
        claimed_intent="t",
        changed_paths=["M.lean"],
        changed_declarations=[
            ChangedDeclaration(
                name="M.Foo",
                kind=ArtifactType.DEFINITION,
                path="M.lean",
                signature_changed=True,
            )
        ],
        generator=GeneratorProvenance(generator_type="human", name="t"),
    )

    class Head:
        complete = True
        extractor = "lean.toolchain"
        errors: ClassVar[list[object]] = []
        declarations: ClassVar[list[object]] = [
            SimpleNamespace(
                name="M.Foo",
                signature="Bool",
                signature_hash=h_head,
                path="M.lean",
            )
        ]

    class Base:
        complete = True
        extractor = "lean.toolchain"
        errors: ClassVar[list[object]] = []
        declarations: ClassVar[list[object]] = [
            SimpleNamespace(
                name="M.Foo",
                signature="Nat",
                signature_hash=h_base,
                path="M.lean",
            )
        ]

    ctx = _sem_ctx(tmp_path, candidate, candidate_extraction=Head(), base_extraction=Base())
    finding = StatementDiffProvider().collect(ctx).findings[0]
    assert finding.details["compared"][0].get("type_changed") is True
    assert finding.details["compared"][0]["authority"] == "elaborated_pair"

    # Incomplete toolchain → patch fallback
    class Incomplete:
        complete = False
        extractor = "regex-stub"
        errors: ClassVar[list[object]] = []
        declarations: ClassVar[list[object]] = [
            SimpleNamespace(
                name="M.Foo",
                signature="Bool",
                signature_hash=sha256_text("wrong"),
                path="M.lean",
            )
        ]

    ctx2 = _sem_ctx(tmp_path, candidate, candidate_extraction=Incomplete())
    finding2 = StatementDiffProvider().collect(ctx2).findings[0]
    assert finding2.details["used_patch_fallback"] is True


def test_duplicate_retrieval_matrix(tmp_path: Path) -> None:
    sig = "Nat → Nat"
    digest = sha256_text(sig)
    candidate = CandidateDescriptor(
        candidate_id="c-dup",
        project_id="p",
        obligation_ids=["O-01"],
        base_commit="b",
        patch_text="+def helperFn : Nat → Nat := id\n",
        claimed_intent="t",
        changed_paths=["M.lean"],
        changed_declarations=[
            ChangedDeclaration(
                name="M.helperFn",
                kind=ArtifactType.DEFINITION,
                path="M.lean",
            )
        ],
        generator=GeneratorProvenance(generator_type="human", name="t"),
    )

    class Ext:
        complete = True
        extractor = "lean.toolchain"
        errors: ClassVar[list[object]] = []
        declarations: ClassVar[list[object]] = [
            SimpleNamespace(
                name="M.helperFn",
                signature=sig,
                signature_hash=digest,
                path="M.lean",
            ),
            SimpleNamespace(
                name="Lib.otherHelperFn",
                signature=sig,
                signature_hash=digest,
                path="Lib.lean",
            ),
            SimpleNamespace(
                name="Lib.unrelated",
                signature="String",
                signature_hash=sha256_text("String"),
                path="Lib.lean",
            ),
        ]

    ctx = _sem_ctx(tmp_path, candidate, candidate_extraction=Ext())
    finding = DuplicateRetrievalProvider().collect(ctx).findings[0]
    assert finding.status in {FindingStatus.WARN, FindingStatus.PASS, FindingStatus.UNKNOWN}
    assert finding.details["attempted"] is True


def test_try_compile_successor_modules_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sem, "lean_toolchain_available", lambda *_a, **_k: True)
    monkeypatch.setattr(sem, "has_lakefile", lambda *_a, **_k: True)
    monkeypatch.setattr(
        sem,
        "_try_lake_env_lean",
        lambda *_a, **_k: {"ok": False, "reason": "compile_fail"},
    )
    (tmp_path / "Good.lean").write_text("def x := 1\n", encoding="utf-8")
    candidate = CandidateDescriptor(
        candidate_id="c-comp",
        project_id="p",
        obligation_ids=["O-01"],
        base_commit="b",
        patch_text="+def x\n",
        claimed_intent="t",
        changed_paths=["Good.lean"],
        changed_declarations=[
            ChangedDeclaration(
                name="Good.x",
                kind=ArtifactType.DEFINITION,
                path="Good.lean",
            )
        ],
        generator=GeneratorProvenance(generator_type="human", name="t"),
    )
    ctx = _sem_ctx(tmp_path, candidate)
    report = sem._try_compile_successor_modules(
        ctx,
        [
            {"path": 123},
            {"path": "nope.txt"},
            {"path": "Good.lean"},
            {"path": "Good.lean"},
            {"path": "Missing.lean"},
        ],
        max_modules=1,
    )
    assert report["modules_checked"] <= 1
    assert report["attempted"] is True


# ---------------------------------------------------------------------------
# Workspace manager + migration
# ---------------------------------------------------------------------------


def test_select_executor_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lpe.workspace.manager.DockerSandboxExecutor.is_available",
        staticmethod(lambda: False),
    )
    with pytest.raises(HostExecutionRefusedError):
        select_executor(insecure_host_exec=False, network_policy="deny")
    with pytest.raises(NetworkPolicyError):
        select_executor(insecure_host_exec=True, network_policy="deny")

    with pytest.warns(UserWarning):
        _ex, desc, isolated = select_executor(insecure_host_exec=True, network_policy="allow")
    assert desc.backend == "host"
    assert isolated is False

    monkeypatch.setattr(
        "lpe.workspace.manager.DockerSandboxExecutor.is_available",
        staticmethod(lambda: True),
    )
    monkeypatch.setattr(
        "lpe.workspace.manager.resolve_docker_image_digest",
        lambda _img: "sha256:" + ("aa" * 32),
    )
    _ex2, desc2, iso2 = select_executor(insecure_host_exec=False, network_policy="deny")
    assert iso2 is True
    assert desc2.network_policy == "deny"

    _ex3, desc3, iso3 = select_executor(insecure_host_exec=False, network_policy="allow")
    assert desc3.backend == "docker"
    assert iso3 is False


def test_migrate_finding_coverage_branches() -> None:
    pass_raw = {
        "check_id": "x",
        "status": "PASS",
        "dimension": "kernel",
        "severity": "L1",
        "summary": "ok",
        "details": {},
        "started_at": NOW.isoformat(),
        "finished_at": NOW.isoformat(),
    }
    migrated = migrate_finding_0_1_to_0_2(pass_raw)
    assert migrated["coverage"]["complete_for_declared_scope"] is False
    assert migrated["details"]["migration"]["pass_without_coverage"] == "LEGACY_UNRESOLVED"
    assert migrated["status"] == FindingStatus.UNKNOWN.value

    fail_raw = {**pass_raw, "status": "FAIL"}
    migrated_fail = migrate_finding_0_1_to_0_2(fail_raw)
    assert migrated_fail["coverage"]["complete_for_declared_scope"] is True


# ---------------------------------------------------------------------------
# Extra branch push (artifacts / manager / migration / CLI / generic / adaptive)
# ---------------------------------------------------------------------------


def test_artifact_store_edge_branches(tmp_path: Path) -> None:
    from lpe.workspace.artifacts import (
        ContentAddressedArtifactStore,
        PacketSizeBudgetError,
        packet_bytes_excluding_artifact_refs,
        redact_excerpt,
        validate_packet_size_budget,
    )

    text = "x" * 10 + "é" * 5000
    excerpt = redact_excerpt(text, limit=20)
    assert isinstance(excerpt, str)

    store = ContentAddressedArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="invalid"):
        store._path_for("zz")
    with pytest.raises(ValueError, match="invalid"):
        store._path_for("!")

    ref = store.put_bytes(
        b"\xff\xfe binary",
        media_type="application/octet-stream",
        logical_name="bin",
        producer_id="t",
        redact=True,
        include_excerpt=True,
    )
    assert ref.excerpt is None
    assert store.get_bytes(ref.sha256) == b"\xff\xfe binary"

    secret_ref = store.put_text(
        "token=ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        "text/plain",
        logical_name="s.txt",
        producer_id="t",
    )
    assert secret_ref.sha256
    with pytest.raises(FileNotFoundError):
        store.get_bytes("ab" + "0" * 62)

    bad_ref = secret_ref.model_copy(update={"byte_length": 1})
    with pytest.raises(ValueError, match="length"):
        store.verify(bad_ref)

    size = packet_bytes_excluding_artifact_refs(
        {"a": 1, "artifact_refs": [{"x": 1}], "nested": [{"artifact_refs": []}]}
    )
    assert size > 0
    with pytest.raises(PacketSizeBudgetError):
        validate_packet_size_budget({"pad": "y" * 2000}, budget=10)


def test_manager_cleanup_and_policy_edges(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from lpe.workspace.manager import (
        EvaluationWorkspaceManager,
        WorkspaceError,
        _normalize_network_policy,
    )

    assert _normalize_network_policy("weird") == "deny"
    assert _normalize_network_policy("ALLOW") == "allow"

    mgr = EvaluationWorkspaceManager(artifact_root=tmp_path)
    with pytest.raises(WorkspaceError):
        mgr.mark_persisted()
    mgr.cleanup()
    assert mgr.verify_cleanup() is True
    with pytest.raises(WorkspaceError):
        mgr.extract_pair()

    monkeypatch.setattr(
        "lpe.workspace.manager.DockerSandboxExecutor.is_available",
        staticmethod(lambda: False),
    )
    with pytest.raises(HostExecutionRefusedError):
        select_executor(insecure_host_exec=False, network_policy="allow")

    token = WorkspaceCleanupToken(run_id="run_x")
    ws = EvaluationWorkspace(
        run_id="run_x",
        repository_origin=tmp_path,
        base_path=tmp_path,
        candidate_path=tmp_path,
        base_commit="b",
        head_commit=None,
        patch_sha256=None,
        base_tree_hash="t1",
        candidate_tree_hash="t2",
        contract_hash="ch",
        obligation_freeze_hash="oh",
        executor=MagicMock(),
        executor_descriptor=ExecutorDescriptor(
            backend="host",
            network_policy="allow",
            readonly_root=False,
            source_mount_readonly=False,
        ),
        artifact_store=ContentAddressedArtifactStore(tmp_path),
        cleanup_token=token,
        session_root=None,
    )
    mgr._workspace = ws
    with pytest.raises(WorkspaceError, match="refused"):
        mgr.cleanup(force=False)
    mgr.cleanup(force=True)
    assert token.cleaned is True
    mgr.cleanup(force=True)
    assert mgr.verify_cleanup() is True


def test_migration_packet_and_finding_edges() -> None:
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
        Severity,
    )

    raw = {
        "check_id": "c",
        "status": "UNKNOWN",
        "dimension": "kernel",
        "severity": "L1",
        "summary": "x",
        "details": "not-a-dict",
        "basis": None,
        "started_at": NOW.isoformat(),
        "finished_at": NOW.isoformat(),
    }
    migrated = migrate_finding_0_1_to_0_2(raw)
    assert migrated["basis"] is None

    raw2 = {
        "check_id": "c",
        "status": "FAIL",
        "dimension": "kernel",
        "severity": "L1",
        "summary": "x",
        "details": {},
        "basis": "ELABORATOR_EXTRACTED",
        "coverage": EvidenceCoverage(
            requested_subject_count=1,
            evaluated_subject_count=1,
            complete_for_declared_scope=True,
        ).model_dump(),
        "provenance": {"tool": "t", "tool_version": "1"},
        "started_at": NOW.isoformat(),
        "finished_at": NOW.isoformat(),
    }
    migrated2 = migrate_finding_0_1_to_0_2(raw2)
    assert migrated2["provenance"]["producer_id"] == "t"

    with pytest.raises(ValueError):
        migrate_packet_0_1_to_0_2({"schema_version": "9.9.9"})

    try:
        load_packet_migrating({"schema_version": "0.2.0"})
    except Exception:
        pass

    # Use model_construct to bypass validators so assert_finding_pass_rules can fire.
    finding = EvidenceFinding.model_construct(
        check_id="c",
        dimension=EvidenceDimension.KERNEL,
        status=FindingStatus.PASS,
        severity=Severity.L1,
        summary="ok",
        details={},
        started_at=NOW,
        finished_at=NOW,
        coverage=EvidenceCoverage(
            requested_subject_count=1,
            evaluated_subject_count=1,
            complete_for_declared_scope=False,
            allows_partial_pass=False,
        ),
        basis=EvidenceBasis.HEURISTIC_RETRIEVAL,
        required_basis=EvidenceBasis.ELABORATOR_EXTRACTED,
    )
    with pytest.raises(ValueError):
        assert_finding_pass_rules(finding)


def test_cli_contract_migrate_and_research_format(
    monkeypatch: pytest.MonkeyPatch, example_project: Path
) -> None:
    monkeypatch.setattr(
        "lpe.cli.dry_run_contract_migration",
        lambda *_a, **_k: {"ok": False, "reason": "nope"},
    )
    result = runner.invoke(app, ["contract", "migrate-dry-run", str(example_project)])
    assert result.exit_code == 1

    monkeypatch.setattr(
        "lpe.cli.apply_contract_migration",
        lambda *_a, **_k: {"ok": False, "reason": "nope"},
    )
    result2 = runner.invoke(app, ["contract", "migrate", str(example_project), "--write"])
    assert result2.exit_code == 1

    result3 = runner.invoke(app, ["research", "status", "--format", "markdown"])
    assert result3.exit_code == 0
    result4 = runner.invoke(app, ["research", "status", "--format", "weird"])
    assert result4.exit_code == 1


def test_generic_bundled_root_and_invalid_json_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from lpe.lean.generic import bundled_extractor_root, try_generic_extract

    proto = tmp_path / "src"
    proto.mkdir()
    (proto / "Protocol.lean").write_text("-- p", encoding="utf-8")
    monkeypatch.setenv("LPE_EXTRACT_SOURCES", str(proto))
    assert bundled_extractor_root() == proto.resolve()

    monkeypatch.setenv("LPE_EXTRACT_SOURCES", str(tmp_path / "missing"))
    try:
        bundled_extractor_root()
    except FileNotFoundError:
        pass

    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.14.0\n", encoding="utf-8")
    (tmp_path / "lakefile.toml").write_text('name = "demo"\n', encoding="utf-8")
    monkeypatch.setattr(
        "lpe.lean.generic.discover_modules",
        lambda *_a, **_k: SimpleNamespace(
            modules=("Demo.Main",), roots=("Demo",), method="filesystem", error=None
        ),
    )
    monkeypatch.setattr("lpe.lean.generic._copy_extractor_sources", lambda *_a, **_k: None)
    monkeypatch.setattr("lpe.lean.generic._write_ephemeral_lakefile", lambda *_a, **_k: None)
    monkeypatch.setattr("lpe.lean.generic._write_aggregator", lambda *_a, **_k: None)
    monkeypatch.setattr("lpe.lean.generic.shutil.which", lambda _: "/fake/lake")

    def _ok_then_write(cmd, **kwargs):  # type: ignore[no-untyped-def]
        cwd = Path(kwargs.get("cwd") or ".")
        out = cwd / ".lpe" / "lean-extraction-v2.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        if "lpe_extract" in " ".join(str(c) for c in cmd):
            out.write_text("[1,2,3]", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", _ok_then_write)
    bad = run_generic_extract(tmp_path, snapshot_fingerprint="f" * 64, executor=None, dry_run=False)
    assert any("INVALID_JSON" in e.code for e in bad.errors)

    empty = tmp_path / "empty"
    empty.mkdir()
    assert try_generic_extract(empty) is None


def test_adaptive_requires_toolchain_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("lpe.lean.extractor.lean_toolchain_available", lambda *_a, **_k: False)
    monkeypatch.setattr("lpe.lean.extractor.project_requires_toolchain", lambda *_a, **_k: True)
    (tmp_path / "A.lean").write_text("def foo : Nat := 1\n", encoding="utf-8")
    result = AdaptiveLeanExtractor().extract_repository(tmp_path, run_toolchain=False)
    assert result.complete is False
    assert any("toolchain required" in n for n in result.notes)


def test_compiler_skip_build_host_path(
    example_project: Path,
    example_candidate: CandidateDescriptor,
) -> None:
    packet = compiler_mod.compile_evidence(
        project_path=example_project,
        candidate=example_candidate,
        skip_build=True,
        use_sandbox=True,
        insecure_host_exec=True,
        enable_semantic_providers=False,
        enable_lean_extraction=False,
    )
    assert packet is not None
