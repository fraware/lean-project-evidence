"""Unit tests for Lake toolchain runner (no Lean required for declare/check paths)."""

from __future__ import annotations

from pathlib import Path

from lpe.lean.toolchain import has_lakefile, project_declares_lpe_extract


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "lean_project"


def test_lean_project_fixture_declares_lpe_extract() -> None:
    assert has_lakefile(FIXTURE)
    assert project_declares_lpe_extract(FIXTURE)


def test_persist_toolchain_artifact_copies_json(tmp_path: Path) -> None:
    from lpe.lean.toolchain import persist_toolchain_artifact

    src = tmp_path / "src"
    dst = tmp_path / "dst"
    (src / ".lpe").mkdir(parents=True)
    (dst / ".lpe").mkdir(parents=True)
    payload = '{"extractor":"lean.toolchain","complete":true,"declarations":[]}\n'
    (src / ".lpe" / "lean-extraction.json").write_text(payload, encoding="utf-8")
    out = persist_toolchain_artifact(src, dst)
    assert out is not None
    assert out.read_text(encoding="utf-8") == payload


def test_toolchain_project_without_lakefile_does_not_declare_extract() -> None:
    root = Path(__file__).resolve().parents[1] / "fixtures" / "lean" / "toolchain_project"
    assert not has_lakefile(root)
    assert not project_declares_lpe_extract(root)
