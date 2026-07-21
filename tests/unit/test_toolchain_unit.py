"""Unit coverage for lean/toolchain.py with mocks (no host Lake required)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from lpe.execution.protocol import ExecutionResult
from lpe.lean.extractor import TOOLCHAIN_EXTRACTOR
from lpe.lean.toolchain import (
    NOTE_HOST_EXTRACT,
    _fill_signature_hashes,
    _normalize_and_load,
    _persist_notes,
    _result_from_exit,
    ensure_toolchain_extraction,
    extraction_artifact_path,
    finalize_extract_from_exit,
    has_lakefile,
    persist_toolchain_artifact,
    project_declares_lpe_extract,
    try_run_lake_extract,
)


def _seed_repo(root: Path, *, declare: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if declare:
        (root / "lakefile.toml").write_text(
            'name = "demo"\n[[lean_exe]]\nname = "lpe_extract"\n',
            encoding="utf-8",
        )
    else:
        (root / "lakefile.toml").write_text('name = "demo"\n', encoding="utf-8")
    return root


def _write_complete_artifact(repo: Path, *, with_sig: bool = False) -> Path:
    out = repo / ".lpe" / "lean-extraction.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    decls: list[dict[str, object]] = []
    if with_sig:
        decls.append(
            {
                "name": "Foo.bar",
                "kind": "def",
                "module": "Foo",
                "signature": "def bar : Nat",
            }
        )
    payload = {
        "extractor": TOOLCHAIN_EXTRACTOR,
        "complete": True,
        "declarations": decls,
        "axioms_used": [],
        "imports": [],
        "dependency_edges": [],
        "errors": [],
        "notes": [],
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


class _Executor:
    def __init__(
        self,
        *,
        exit_code: int = 0,
        write_json: bool = True,
        raise_exc: Exception | None = None,
        stderr: str = "",
    ) -> None:
        self.exit_code = exit_code
        self.write_json = write_json
        self.raise_exc = raise_exc
        self.stderr = stderr
        self.commands: list[list[str]] = []

    def verify_build(
        self,
        repository: Path,
        command: list[str],
        timeout_seconds: int,
        max_output_bytes: int,
        environment_allowlist: list[str],
    ) -> ExecutionResult:
        self.commands.append(list(command))
        if self.raise_exc is not None:
            raise self.raise_exc
        if self.write_json and self.exit_code == 0:
            _write_complete_artifact(repository)
        return ExecutionResult(
            command=tuple(command),
            cwd=repository,
            exit_code=self.exit_code,
            stdout="",
            stderr=self.stderr,
            elapsed_ms=1,
            timed_out=False,
        )


def test_has_lakefile_toml_and_lean(tmp_path: Path) -> None:
    root = tmp_path / "a"
    root.mkdir()
    assert has_lakefile(root) is False
    (root / "lakefile.lean").write_text("package demo\n", encoding="utf-8")
    assert has_lakefile(root) is True
    assert project_declares_lpe_extract(root) is False
    (root / "lakefile.lean").write_text("lean_exe lpe_extract\n", encoding="utf-8")
    assert project_declares_lpe_extract(root) is True


def test_extraction_artifact_path_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom = tmp_path / "custom.json"
    monkeypatch.setenv("LPE_LEAN_EXTRACTION_JSON", str(custom))
    assert extraction_artifact_path(tmp_path) == custom


def test_fill_signature_hashes() -> None:
    data = {
        "declarations": [
            {"name": "a", "signature": "def a : Nat"},
            {"name": "b", "signature_hash": "already", "signature": "def b"},
            {"name": "c"},
        ]
    }
    filled = _fill_signature_hashes(data)
    assert filled["declarations"][0]["signature_hash"]
    assert filled["declarations"][1]["signature_hash"] == "already"
    assert "signature_hash" not in filled["declarations"][2]


def test_normalize_and_load_fills_hashes(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path / "proj")
    art = _write_complete_artifact(repo, with_sig=True)
    loaded = _normalize_and_load(art)
    assert loaded is not None
    raw = json.loads(art.read_text(encoding="utf-8"))
    assert raw["declarations"][0]["signature_hash"]


def test_normalize_and_load_missing_and_bad_json(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    assert _normalize_and_load(missing) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    loaded = _normalize_and_load(bad)
    assert loaded is not None
    assert loaded.complete is False
    assert loaded.errors


def test_persist_notes_merges(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path / "proj")
    art = _write_complete_artifact(repo)
    loaded = _persist_notes(art, "note-a", "note-b", "note-a")
    assert loaded is not None
    assert "note-a" in loaded.notes
    assert "note-b" in loaded.notes
    assert loaded.notes.count("note-a") == 1


def test_result_from_exit_unknown_target_host() -> None:
    art = Path("/tmp/does-not-matter.json")
    assert (
        _result_from_exit(
            returncode=1,
            stdout="",
            stderr="unknown target `lpe_extract`",
            artifact=art,
            provenance_note=NOTE_HOST_EXTRACT,
            via_executor=False,
        )
        is None
    )
    assert (
        _result_from_exit(
            returncode=1,
            stdout="",
            stderr="lpe_extract not found",
            artifact=art,
            provenance_note=NOTE_HOST_EXTRACT,
            via_executor=False,
        )
        is None
    )


def test_result_from_exit_unknown_via_executor_fail_closed() -> None:
    result = _result_from_exit(
        returncode=1,
        stdout="",
        stderr="unknown target lpe_extract",
        artifact=Path("/tmp/x.json"),
        provenance_note=NOTE_HOST_EXTRACT,
        via_executor=True,
    )
    assert result is not None
    assert result.complete is False
    assert result.errors


def test_result_from_exit_success_missing_artifact(tmp_path: Path) -> None:
    art = tmp_path / "missing.json"
    result = _result_from_exit(
        returncode=0,
        stdout="",
        stderr="",
        artifact=art,
        provenance_note=NOTE_HOST_EXTRACT,
        via_executor=True,
    )
    assert result is not None
    assert result.complete is False
    assert "not written" in result.errors[0]


def test_try_run_returns_existing_complete(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path / "proj")
    _write_complete_artifact(repo)
    result = try_run_lake_extract(repo, force=False)
    assert result is not None
    assert result.complete is True


def test_try_run_no_lakefile_returns_none(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    assert try_run_lake_extract(root, force=True) is None


def test_try_run_no_declare_returns_none(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path / "proj", declare=False)
    assert try_run_lake_extract(repo, force=True) is None


def test_try_run_host_no_lake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _seed_repo(tmp_path / "proj")
    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: None)
    assert try_run_lake_extract(repo, force=True) is None


def test_try_run_host_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _seed_repo(tmp_path / "proj")

    def _fake_run(cmd: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        _write_complete_artifact(Path(cwd))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: "/usr/bin/lake")
    monkeypatch.setattr("lpe.lean.toolchain._run_cmd", _fake_run)
    result = try_run_lake_extract(repo, force=True)
    assert result is not None
    assert result.complete is True
    assert any("produced by lake exe lpe_extract" in n for n in result.notes)


def test_try_run_host_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _seed_repo(tmp_path / "proj")

    def _boom(cmd: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: "/usr/bin/lake")
    monkeypatch.setattr("lpe.lean.toolchain._run_cmd", _boom)
    result = try_run_lake_extract(repo, force=True)
    assert result is not None
    assert result.complete is False
    assert "failed" in result.errors[0].lower() or "timed" in result.errors[0].lower()


def test_try_run_host_unknown_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _seed_repo(tmp_path / "proj")

    def _fail(cmd: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 1, "", "error: unknown executable `lpe_extract`")

    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: "/usr/bin/lake")
    monkeypatch.setattr("lpe.lean.toolchain._run_cmd", _fail)
    assert try_run_lake_extract(repo, force=True) is None


def test_try_run_custom_cmd_host(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _seed_repo(tmp_path / "proj", declare=False)
    (repo / "lakefile.toml").write_text('name = "demo"\n', encoding="utf-8")
    monkeypatch.setenv("LPE_LEAN_EXTRACT_CMD", "my-extract out.json")

    def _fake_run(cmd: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        assert cmd == ["my-extract", "out.json"]
        _write_complete_artifact(Path(cwd))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: "/usr/bin/lake")
    monkeypatch.setattr("lpe.lean.toolchain._run_cmd", _fake_run)
    result = try_run_lake_extract(repo, force=True)
    assert result is not None
    assert result.complete is True


def test_try_run_custom_cmd_host_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _seed_repo(tmp_path / "proj")
    monkeypatch.setenv("LPE_LEAN_EXTRACT_CMD", "boom")

    def _fail(cmd: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 7, "", "nope")

    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: "/usr/bin/lake")
    monkeypatch.setattr("lpe.lean.toolchain._run_cmd", _fail)
    result = try_run_lake_extract(repo, force=True)
    assert result is not None
    assert result.complete is False
    assert "exit 7" in result.errors[0]


def test_try_run_custom_cmd_host_missing_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _seed_repo(tmp_path / "proj")
    monkeypatch.setenv("LPE_LEAN_EXTRACT_CMD", "ok-cmd")

    def _ok(cmd: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: "/usr/bin/lake")
    monkeypatch.setattr("lpe.lean.toolchain._run_cmd", _ok)
    result = try_run_lake_extract(repo, force=True)
    assert result is not None
    assert result.complete is False
    assert "missing" in result.errors[0]


def test_try_run_executor_oserror(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path / "proj")
    executor = _Executor(raise_exc=OSError("docker gone"))
    result = try_run_lake_extract(repo, force=True, executor=executor)  # type: ignore[arg-type]
    assert result is not None
    assert result.complete is False
    assert "failed" in result.errors[0].lower()


def test_try_run_custom_via_executor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _seed_repo(tmp_path / "proj")
    monkeypatch.setenv("LPE_LEAN_EXTRACT_CMD", "lake exe lpe_extract .lpe/lean-extraction.json")
    executor = _Executor()
    result = try_run_lake_extract(repo, force=True, executor=executor)  # type: ignore[arg-type]
    assert result is not None
    assert result.complete is True
    assert executor.commands[0][0] == "lake"


def test_try_run_custom_via_executor_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _seed_repo(tmp_path / "proj")
    monkeypatch.setenv("LPE_LEAN_EXTRACT_CMD", "lake exe lpe_extract out.json")
    executor = _Executor(exit_code=3, write_json=False, stderr="boom")
    result = try_run_lake_extract(repo, force=True, executor=executor)  # type: ignore[arg-type]
    assert result is not None
    assert result.complete is False
    assert "exit 3" in result.errors[0]


def test_try_run_custom_via_executor_missing_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _seed_repo(tmp_path / "proj")
    monkeypatch.setenv("LPE_LEAN_EXTRACT_CMD", "lake exe lpe_extract out.json")
    executor = _Executor(exit_code=0, write_json=False)
    result = try_run_lake_extract(repo, force=True, executor=executor)  # type: ignore[arg-type]
    assert result is not None
    assert result.complete is False
    assert "missing" in result.errors[0]


def test_ensure_toolchain_extraction_delegates(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path / "proj")
    _write_complete_artifact(repo)
    result = ensure_toolchain_extraction(repo)
    assert result is not None
    assert result.complete is True


def test_persist_toolchain_artifact_same_and_copy(tmp_path: Path) -> None:
    src = _seed_repo(tmp_path / "src")
    art = _write_complete_artifact(src)
    assert persist_toolchain_artifact(src, src) == art

    dst = tmp_path / "dst"
    dst.mkdir()
    out = persist_toolchain_artifact(src, dst)
    assert out is not None
    assert out.is_file()
    assert out.read_text(encoding="utf-8") == art.read_text(encoding="utf-8")


def test_persist_toolchain_artifact_alt_candidate(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    alt = src / ".lean-project-contract" / "lean-extraction.json"
    alt.parent.mkdir(parents=True)
    alt.write_text(
        json.dumps(
            {
                "extractor": TOOLCHAIN_EXTRACTOR,
                "complete": True,
                "declarations": [],
                "axioms_used": [],
                "imports": [],
                "dependency_edges": [],
                "errors": [],
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    dst = tmp_path / "dst"
    dst.mkdir()
    out = persist_toolchain_artifact(src, dst)
    assert out is not None
    assert out.is_file()


def test_persist_toolchain_artifact_missing(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    dst = tmp_path / "dst"
    dst.mkdir()
    assert persist_toolchain_artifact(src, dst) is None


def test_finalize_extract_public_wrapper(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path / "proj")
    _write_complete_artifact(repo)
    loaded = finalize_extract_from_exit(
        repo,
        returncode=0,
        stdout="",
        stderr="",
        provenance_note="unit-note",
        via_executor=False,
    )
    assert loaded is not None
    assert "unit-note" in loaded.notes


def test_try_run_loads_alt_candidate(tmp_path: Path) -> None:
    repo = _seed_repo(tmp_path / "proj")
    alt = repo / ".lean-project-contract" / "lean-extraction.json"
    alt.parent.mkdir(parents=True)
    alt.write_text(
        json.dumps(
            {
                "extractor": TOOLCHAIN_EXTRACTOR,
                "complete": True,
                "declarations": [],
                "axioms_used": [],
                "imports": [],
                "dependency_edges": [],
                "errors": [],
                "notes": [],
            }
        ),
        encoding="utf-8",
    )
    result = try_run_lake_extract(repo, force=False)
    assert result is not None
    assert result.complete is True


def test_custom_cmd_host_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _seed_repo(tmp_path / "proj")
    monkeypatch.setenv("LPE_LEAN_EXTRACT_CMD", "x")
    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: "/usr/bin/lake")

    def _boom(cmd: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
        raise OSError("exec failed")

    monkeypatch.setattr("lpe.lean.toolchain._run_cmd", _boom)
    result = try_run_lake_extract(repo, force=True)
    assert result is not None
    assert result.complete is False
