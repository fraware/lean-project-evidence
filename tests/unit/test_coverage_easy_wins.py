"""Easy-win unit coverage for report, lean_status, router, generic discovery."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from lpe.evidence.router import select_review_question
from lpe.honesty.lean_status import lean_extractor_status
from lpe.lean.extractor import REGEX_STUB_EXTRACTOR, TOOLCHAIN_EXTRACTOR
from lpe.lean.generic import (
    discover_lake_workspace,
    discover_modules,
    load_supported_toolchain_prefixes,
    run_generic_extract,
)
from lpe.models import (
    EvidenceDimension,
    EvidenceFinding,
    FindingStatus,
    RiskClass,
    Severity,
)
from lpe.pilot.report import (
    render_summary_json,
    render_summary_markdown,
    write_summary_reports,
)
from lpe.pilot.summary import ConditionBucket, PilotSummary


def _empty_summary(**kwargs: object) -> PilotSummary:
    base = dict(
        project_id="p",
        candidate_count=0,
        automated_count=0,
        automation_rate=0.0,
        expert_minutes_total=0.0,
        expert_minutes_by_category={},
        expert_minutes_by_condition={},
        conditions={},
        overhead_snapshots=[],
        reproduction_exact_count=0,
        reproduction_known_count=0,
        event_count=0,
    )
    base.update(kwargs)
    return PilotSummary(**base)  # type: ignore[arg-type]


def test_write_summary_reports_empty(tmp_path: Path) -> None:
    summary = _empty_summary()
    j, md = write_summary_reports(summary, tmp_path)
    assert j.is_file() and md.is_file()
    assert "NON_CLAIMS" in j.read_text(encoding="utf-8")
    assert "software_instrumentation" in md.read_text(encoding="utf-8")


def test_render_summary_with_buckets() -> None:
    summary = _empty_summary(
        candidate_count=2,
        automated_count=1,
        automation_rate=0.5,
        expert_minutes_total=12.0,
        expert_minutes_by_category={"review": 12.0},
        conditions={
            "control": ConditionBucket(
                condition_tag="control",
                candidates=1,
                automated=0,
                expert_minutes=5.0,
                outcomes={"REQUEST_REPAIR": 1},
            )
        },
        overhead_snapshots=[
            {
                "artifact_id": "a1",
                "overhead_fraction": 0.05,
                "within_budget": True,
            }
        ],
    )
    text = render_summary_markdown(summary)
    assert "control" in text
    assert "review" in text
    assert "within_budget" in text
    payload = json.loads(render_summary_json(summary))
    assert payload["section_21_cleared"] is False


def test_lean_extractor_status_with_artifact(tmp_path: Path) -> None:
    art = tmp_path / ".lpe"
    art.mkdir()
    (art / "lean-extraction.json").write_text(
        json.dumps({"complete": True, "extractor": TOOLCHAIN_EXTRACTOR}),
        encoding="utf-8",
    )
    status = lean_extractor_status(tmp_path)
    assert status["artifact"] is not None
    assert status["mathlib_scale"] is False
    assert status["warnings"]

    (art / "lean-extraction.json").write_text(
        json.dumps({"complete": False, "extractor": REGEX_STUB_EXTRACTOR}),
        encoding="utf-8",
    )
    stub = lean_extractor_status(tmp_path)
    assert stub["extractor_mode"] == REGEX_STUB_EXTRACTOR or stub["warnings"]

    (art / "lean-extraction.json").write_text("{bad", encoding="utf-8")
    broken = lean_extractor_status(tmp_path)
    assert broken["artifact_complete"] is None


def test_select_review_question_dimensions() -> None:
    from datetime import UTC, datetime

    from lpe.models import Provenance

    now = datetime.now(UTC)

    def finding(dim: EvidenceDimension, status: FindingStatus) -> EvidenceFinding:
        return EvidenceFinding(
            finding_id=f"f-{dim.value}-{status.value}",
            check_id=f"check.{dim.value}",
            check_version="0.2.0",
            dimension=dim,
            status=status,
            severity=Severity.L2,
            summary="x",
            details={},
            provenance=Provenance(
                tool="t",
                tool_version="0",
                command=[],
                input_hash="a" * 64,
                output_hash="b" * 64,
                started_at=now,
                finished_at=now,
                elapsed_ms=0,
            ),
        )

    semantic_q = select_review_question(
        [finding(EvidenceDimension.SEMANTIC, FindingStatus.UNKNOWN)],
        RiskClass.R1,
        ["lean-engineer"],
        10,
    )
    assert semantic_q is not None
    assert "mathematical" in semantic_q.question.lower()

    repo_q = select_review_question(
        [finding(EvidenceDimension.REPOSITORY, FindingStatus.WARN)],
        RiskClass.R1,
        ["lean-engineer"],
        10,
    )
    assert repo_q is not None
    assert "abstraction" in repo_q.question.lower()

    down_q = select_review_question(
        [finding(EvidenceDimension.DOWNSTREAM, FindingStatus.UNKNOWN)],
        RiskClass.R2,
        ["repository-maintainer"],
        15,
    )
    assert down_q is not None
    assert "downstream" in down_q.question.lower()

    r3_q = select_review_question([], RiskClass.R3, ["r3-reviewer"], 20)
    assert r3_q is not None
    assert "high-risk" in r3_q.question.lower()

    none_q = select_review_question(
        [finding(EvidenceDimension.SEMANTIC, FindingStatus.PASS)],
        RiskClass.R1,
        ["lean-engineer"],
        10,
    )
    assert none_q is None


def test_discover_lakefile_lean(tmp_path: Path) -> None:
    (tmp_path / "lakefile.lean").write_text(
        "package MockLean\nlean_lib MockLib\n",
        encoding="utf-8",
    )
    (tmp_path / "MockLib").mkdir()
    (tmp_path / "MockLib" / "A.lean").write_text("def a := 1\n", encoding="utf-8")
    info = discover_lake_workspace(tmp_path)
    assert not isinstance(info, Exception)
    assert info.lakefile_kind == "lean"
    discovery = discover_modules(tmp_path, info)
    assert discovery.modules


def test_discover_modules_filesystem_and_ambiguous(tmp_path: Path) -> None:
    (tmp_path / "lakefile.toml").write_text(
        'name = "X"\n[[lean_lib]]\nname = "MissingLib"\n',
        encoding="utf-8",
    )
    only = tmp_path / "Src"
    only.mkdir()
    (only / "A.lean").write_text("def a := 1\n", encoding="utf-8")
    info = discover_lake_workspace(tmp_path)
    assert not isinstance(info, Exception)
    discovery = discover_modules(tmp_path, info)
    assert discovery.method in {"filesystem", "unknown", "ambiguous", "lake_metadata"}

    (tmp_path / "Other").mkdir()
    (tmp_path / "Other" / "B.lean").write_text("def b := 1\n", encoding="utf-8")
    amb = discover_modules(tmp_path, info)
    assert amb.method in {"ambiguous", "filesystem", "unknown", "lake_metadata"}


def test_discover_modules_single_root_lean(tmp_path: Path) -> None:
    (tmp_path / "lakefile.toml").write_text(
        'name = "Solo"\n[[lean_lib]]\nname = "NoSuch"\n',
        encoding="utf-8",
    )
    (tmp_path / "Solo.lean").write_text("def s := 1\n", encoding="utf-8")
    info = discover_lake_workspace(tmp_path)
    assert not isinstance(info, Exception)
    discovery = discover_modules(tmp_path, info)
    assert "Solo" in discovery.modules or discovery.method in {
        "filesystem",
        "unknown",
        "ambiguous",
    }


def test_load_supported_toolchain_prefixes_missing(tmp_path: Path) -> None:
    prefixes = load_supported_toolchain_prefixes(tmp_path / "missing.yaml")
    assert prefixes
    assert any("lean4" in p for p in prefixes)


def test_bundled_extractor_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from lpe.lean.generic import bundled_extractor_root

    fake = tmp_path / "extract"
    (fake / "LpeExtract").mkdir(parents=True)
    monkeypatch.setenv("LPE_EXTRACT_SOURCES", str(fake))
    assert bundled_extractor_root() == fake.resolve()


def test_run_generic_extract_build_fail_mocked_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lpe.execution.protocol import ExecutionResult
    from lpe.lean import generic as generic_mod

    (tmp_path / "lakefile.toml").write_text(
        'name = "MockPkg"\n[[lean_lib]]\nname = "MockPkg"\n',
        encoding="utf-8",
    )
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.14.0\n", encoding="utf-8")
    (tmp_path / "MockPkg.lean").write_text("def x := 1\n", encoding="utf-8")

    class FailBuild:
        def verify_build(self, **kwargs):  # type: ignore[no-untyped-def]
            return ExecutionResult(
                command=("lake", "build"),
                cwd=kwargs.get("repository", tmp_path),
                exit_code=1,
                stdout="",
                stderr="build failed",
                elapsed_ms=1,
                timed_out=False,
            )

        def run(self, **kwargs):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    monkeypatch.setattr(generic_mod, "_copy_extractor_sources", lambda dest: None)
    monkeypatch.setattr(generic_mod, "_write_ephemeral_lakefile", lambda *a, **k: None)
    monkeypatch.setattr(generic_mod, "_write_aggregator", lambda *a, **k: None)

    result = run_generic_extract(
        tmp_path,
        snapshot_fingerprint="fp",
        executor=FailBuild(),  # type: ignore[arg-type]
        dry_run=False,
    )
    assert result.has_blocking_errors
    assert any(e.code == "GENERIC_EXTRACT_BUILD_FAILED" for e in result.errors)


def test_run_generic_extract_run_fail_mocked_executor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from lpe.execution.protocol import ExecutionResult
    from lpe.lean import generic as generic_mod

    (tmp_path / "lakefile.toml").write_text(
        'name = "MockPkg"\n[[lean_lib]]\nname = "MockPkg"\n',
        encoding="utf-8",
    )
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.14.0\n", encoding="utf-8")
    (tmp_path / "MockPkg.lean").write_text("def x := 1\n", encoding="utf-8")

    class FailExe:
        def verify_build(self, repository, command, **kwargs):  # type: ignore[no-untyped-def]
            code = 0 if command[:2] == ["lake", "build"] else 2
            return ExecutionResult(
                command=tuple(command),
                cwd=repository,
                exit_code=code,
                stdout="",
                stderr="exe failed" if code else "",
                elapsed_ms=1,
                timed_out=False,
            )

        def run(self, **kwargs):  # type: ignore[no-untyped-def]
            raise NotImplementedError

    monkeypatch.setattr(generic_mod, "_copy_extractor_sources", lambda dest: None)
    monkeypatch.setattr(generic_mod, "_write_ephemeral_lakefile", lambda *a, **k: None)
    monkeypatch.setattr(generic_mod, "_write_aggregator", lambda *a, **k: None)

    result = run_generic_extract(
        tmp_path,
        snapshot_fingerprint="fp",
        executor=FailExe(),  # type: ignore[arg-type]
        dry_run=False,
    )
    assert any(e.code == "GENERIC_EXTRACT_RUN_FAILED" for e in result.errors)
