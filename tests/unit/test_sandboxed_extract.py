"""Unit tests: lake exe lpe_extract via LeanExecutor (no host Lake required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lpe.execution.protocol import ExecutionResult
from lpe.execution.sandbox import DockerSandboxExecutor
from lpe.lean.extractor import TOOLCHAIN_EXTRACTOR
from lpe.lean.toolchain import (
    NOTE_DOCKER_EXTRACT,
    extract_executor_label,
    try_run_lake_extract,
)


class _RecordingExecutor:
    """Minimal executor that records commands and writes toolchain JSON."""

    def __init__(self, *, exit_code: int = 0, write_json: bool = True) -> None:
        self.commands: list[list[str]] = []
        self.exit_code = exit_code
        self.write_json = write_json

    def verify_build(
        self,
        repository: Path,
        command: list[str],
        timeout_seconds: int,
        max_output_bytes: int,
        environment_allowlist: list[str],
    ) -> ExecutionResult:
        self.commands.append(list(command))
        if self.write_json and self.exit_code == 0:
            out = repository / ".lpe" / "lean-extraction.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "extractor": TOOLCHAIN_EXTRACTOR,
                "complete": True,
                "declarations": [],
                "axioms_used": [],
                "imports": [],
                "dependency_edges": [],
                "errors": [],
                "notes": [],
            }
            out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return ExecutionResult(
            command=tuple(command),
            cwd=repository,
            exit_code=self.exit_code,
            stdout="",
            stderr="extract failed" if self.exit_code else "",
            elapsed_ms=1,
            timed_out=False,
        )


def _seed_declaring_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "lakefile.toml").write_text(
        'name = "demo"\n[[lean_exe]]\nname = "lpe_extract"\n',
        encoding="utf-8",
    )
    return root


def test_extract_executor_label_docker() -> None:
    assert extract_executor_label(DockerSandboxExecutor(network_none=True)) == "docker-sandbox"
    assert extract_executor_label(_RecordingExecutor()) == "_RecordingExecutor"
    assert extract_executor_label(None) is None


def test_try_run_lake_extract_via_executor_writes_json(tmp_path: Path) -> None:
    repo = _seed_declaring_repo(tmp_path / "proj")
    executor = _RecordingExecutor()
    result = try_run_lake_extract(
        repo,
        force=True,
        executor=executor,  # type: ignore[arg-type]
    )
    assert executor.commands == [["lake", "exe", "lpe_extract", ".lpe/lean-extraction.json"]]
    assert result is not None
    assert result.complete is True
    assert result.extractor == TOOLCHAIN_EXTRACTOR
    assert NOTE_DOCKER_EXTRACT not in result.notes  # not a DockerSandboxExecutor
    assert any("produced by lake exe lpe_extract" in n for n in result.notes)
    artifact = repo / ".lpe" / "lean-extraction.json"
    assert artifact.is_file()
    raw = json.loads(artifact.read_text(encoding="utf-8"))
    assert any("produced by lake exe lpe_extract" in n for n in raw.get("notes", []))


def test_try_run_lake_extract_via_docker_label_persists_note(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _seed_declaring_repo(tmp_path / "proj")
    # Route DockerSandboxExecutor.verify_build through a recording stub.
    recorder = _RecordingExecutor()

    def _fake_verify(self, **kwargs):  # type: ignore[no-untyped-def]
        return recorder.verify_build(**kwargs)

    monkeypatch.setattr(DockerSandboxExecutor, "verify_build", _fake_verify)
    docker = DockerSandboxExecutor(network_none=True)
    result = try_run_lake_extract(repo, force=True, executor=docker)
    assert result is not None
    assert result.complete is True
    assert NOTE_DOCKER_EXTRACT in result.notes
    raw = json.loads((repo / ".lpe" / "lean-extraction.json").read_text(encoding="utf-8"))
    assert NOTE_DOCKER_EXTRACT in raw.get("notes", [])


def test_sandboxed_extract_failure_fail_closed(tmp_path: Path) -> None:
    repo = _seed_declaring_repo(tmp_path / "proj")
    executor = _RecordingExecutor(exit_code=1, write_json=False)
    result = try_run_lake_extract(
        repo,
        force=True,
        executor=executor,  # type: ignore[arg-type]
    )
    assert result is not None
    assert result.complete is False
    assert result.errors
    assert "exit 1" in result.errors[0]
    assert not (repo / ".lpe" / "lean-extraction.json").is_file()


def test_executor_path_does_not_require_host_lake(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _seed_declaring_repo(tmp_path / "proj")
    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: None)
    executor = _RecordingExecutor()
    result = try_run_lake_extract(
        repo,
        force=True,
        executor=executor,  # type: ignore[arg-type]
    )
    assert result is not None
    assert result.complete is True


def test_finalize_extract_and_build_failed_helpers(tmp_path: Path) -> None:
    from lpe.lean.toolchain import (
        NOTE_DOCKER_EXTRACT,
        build_failed_before_extract_result,
        finalize_extract_from_exit,
    )

    failed = build_failed_before_extract_result(
        exit_code=2,
        provenance_note=NOTE_DOCKER_EXTRACT,
    )
    assert failed.complete is False
    assert failed.errors
    assert "build failed" in failed.errors[0].lower() or "exit 2" in failed.errors[0]

    repo = _seed_declaring_repo(tmp_path / "proj")
    out = repo / ".lpe" / "lean-extraction.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
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
        )
        + "\n",
        encoding="utf-8",
    )
    ok = finalize_extract_from_exit(
        repo,
        returncode=0,
        stdout="",
        stderr="LPE_PHASE=ok\n",
        provenance_note=NOTE_DOCKER_EXTRACT,
    )
    assert ok is not None
    assert ok.complete is True
    assert NOTE_DOCKER_EXTRACT in ok.notes

    bad = finalize_extract_from_exit(
        repo,
        returncode=1,
        stdout="",
        stderr="LPE_PHASE=extract\nbang",
        provenance_note=NOTE_DOCKER_EXTRACT,
    )
    assert bad is not None
    assert bad.complete is False
    assert bad.errors
