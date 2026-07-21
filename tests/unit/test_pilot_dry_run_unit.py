"""Unit coverage for pilot dry-run helpers (mocked CLI; not a live pilot)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lpe.pilot.dry_run import (
    SECTION_21_CLEARED,
    build_frozen_corpus,
    load_example_candidates,
    run_frozen_corpus_dry_run,
    synthetic_candidates,
)


def test_section_21_cleared_is_false() -> None:
    assert SECTION_21_CLEARED is False


def test_synthetic_candidates_cycle_templates(tmp_path: Path) -> None:
    paths = synthetic_candidates(tmp_path, 5)
    assert len(paths) == 5
    payloads = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    assert payloads[0]["changed_declarations"][0]["public"] is False
    assert payloads[1]["changed_declarations"][0]["public"] is True
    assert payloads[2]["changed_declarations"][0]["kind"] == "definition"
    assert payloads[3]["candidate_id"] == "candidate-synth-03"
    assert all(p["project_id"] == "example-category-project" for p in payloads)


def test_load_example_candidates(repository_root: Path) -> None:
    found = load_example_candidates(repository_root)
    assert len(found) >= 6
    assert all(p.name.startswith("R") and p.suffix == ".json" for p in found)


def test_build_frozen_corpus_size(repository_root: Path, tmp_path: Path) -> None:
    corpus = build_frozen_corpus(repository_root, tmp_path)
    assert 10 <= len(corpus) <= 20


def test_build_frozen_corpus_rejects_out_of_range(
    repository_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import lpe.pilot.dry_run as dry_run

    monkeypatch.setattr(dry_run, "load_example_candidates", lambda _r: [])
    monkeypatch.setattr(dry_run, "synthetic_candidates", lambda _w, _n: [])
    with pytest.raises(ValueError, match="out of range"):
        build_frozen_corpus(repository_root, tmp_path)


def test_run_frozen_corpus_dry_run_mocked_cli(
    example_project: Path,
    repository_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise orchestration with a tiny corpus and stubbed compile/review."""
    import lpe.pilot.dry_run as dry_run

    tiny = synthetic_candidates(tmp_path / "tiny", 2)
    monkeypatch.setattr(dry_run, "build_frozen_corpus", lambda *_a, **_k: tiny)

    def _fake_invoke(app: object, args: list[str]) -> SimpleNamespace:
        if args and args[0] == "evidence" and "compile" in args:
            out_idx = args.index("--output") + 1
            packet_path = Path(args[out_idx])
            cand_idx = args.index("--candidate") + 1
            cand = json.loads(Path(args[cand_idx]).read_text(encoding="utf-8"))
            packet_path.parent.mkdir(parents=True, exist_ok=True)
            packet_path.write_text(
                json.dumps(
                    {
                        "packet_id": f"pkt-{cand['candidate_id']}",
                        "recommendation": "ESCALATE",
                        "risk_class": "R1",
                        "hard_gate_passed": False,
                    }
                ),
                encoding="utf-8",
            )
            return SimpleNamespace(exit_code=0, stdout="", stderr="")
        if args and args[0] == "review":
            return SimpleNamespace(exit_code=0, stdout="", stderr="")
        return SimpleNamespace(exit_code=1, stdout="unexpected", stderr="")

    runner = MagicMock()
    runner.invoke.side_effect = _fake_invoke

    result = run_frozen_corpus_dry_run(
        example_project=example_project,
        repository_root=repository_root,
        work_dir=tmp_path / "work",
        actor_id="unit-dry-run",
        cli_runner=runner,
    )

    assert result.corpus_size == 2
    assert result.project_id == "example-category-project"
    assert result.report_json.is_file()
    assert result.report_md.is_file()
    assert result.summary_json.is_file()
    assert result.summary_md.is_file()
    assert result.automation_rate == 1.0
    artifact = json.loads(result.report_json.read_text(encoding="utf-8"))
    assert artifact["section_21_cleared"] is False
    assert artifact["causal_claims"] is False
    assert artifact["metric_class"] == "software_instrumentation"
    assert artifact["NON_CLAIMS"]["section_21_cleared"] is False


def test_run_frozen_corpus_dry_run_compile_failure(
    example_project: Path,
    repository_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lpe.pilot.dry_run as dry_run

    tiny = synthetic_candidates(tmp_path / "tiny", 1)
    monkeypatch.setattr(dry_run, "build_frozen_corpus", lambda *_a, **_k: tiny)
    runner = MagicMock()
    runner.invoke.return_value = SimpleNamespace(exit_code=1, stdout="compile boom", stderr="")
    with pytest.raises(RuntimeError, match="compile failed"):
        run_frozen_corpus_dry_run(
            example_project=example_project,
            repository_root=repository_root,
            work_dir=tmp_path / "work",
            cli_runner=runner,
        )


def test_run_frozen_corpus_dry_run_bad_recommendation(
    example_project: Path,
    repository_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lpe.pilot.dry_run as dry_run

    tiny = synthetic_candidates(tmp_path / "tiny", 1)
    monkeypatch.setattr(dry_run, "build_frozen_corpus", lambda *_a, **_k: tiny)

    def _fake_invoke(app: object, args: list[str]) -> SimpleNamespace:
        out_idx = args.index("--output") + 1
        packet_path = Path(args[out_idx])
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_text(
            json.dumps(
                {
                    "packet_id": "pkt-bad",
                    "recommendation": "MAYBE",
                    "risk_class": "R0",
                    "hard_gate_passed": False,
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(exit_code=0, stdout="", stderr="")

    runner = MagicMock()
    runner.invoke.side_effect = _fake_invoke
    with pytest.raises(RuntimeError, match="unexpected recommendation"):
        run_frozen_corpus_dry_run(
            example_project=example_project,
            repository_root=repository_root,
            work_dir=tmp_path / "work",
            cli_runner=runner,
        )


def test_run_frozen_corpus_dry_run_hard_gate_must_fail(
    example_project: Path,
    repository_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import lpe.pilot.dry_run as dry_run

    tiny = synthetic_candidates(tmp_path / "tiny", 1)
    monkeypatch.setattr(dry_run, "build_frozen_corpus", lambda *_a, **_k: tiny)

    def _fake_invoke(app: object, args: list[str]) -> SimpleNamespace:
        out_idx = args.index("--output") + 1
        packet_path = Path(args[out_idx])
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_text(
            json.dumps(
                {
                    "packet_id": "pkt-gate",
                    "recommendation": "ESCALATE",
                    "risk_class": "R1",
                    "hard_gate_passed": True,
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(exit_code=0, stdout="", stderr="")

    runner = MagicMock()
    runner.invoke.side_effect = _fake_invoke
    with pytest.raises(RuntimeError, match="hard_gate_passed"):
        run_frozen_corpus_dry_run(
            example_project=example_project,
            repository_root=repository_root,
            work_dir=tmp_path / "work",
            cli_runner=runner,
        )
