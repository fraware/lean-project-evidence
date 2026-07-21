"""Lean toolchain extraction — requires Lake/Lean (@pytest.mark.lean)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from lpe.hashing import sha256_text
from lpe.lean.extractor import (
    EXTRACTION_SCHEMA_V1_1,
    REGEX_STUB_EXTRACTOR,
    TOOLCHAIN_EXTRACTOR,
    build_dependency_graph,
    extract_lean_repository,
    impact_cone,
    import_expansion,
)
from lpe.lean.toolchain import project_declares_lpe_extract, try_run_lake_extract


LEAN_PROJECT = Path(__file__).resolve().parents[1] / "fixtures" / "lean_project"


@pytest.mark.lean
def test_lean_project_declares_extract_target() -> None:
    assert (LEAN_PROJECT / "lakefile.toml").is_file()
    assert project_declares_lpe_extract(LEAN_PROJECT)
    assert (LEAN_PROJECT / "LpeExtract.lean").is_file()


@pytest.mark.lean
def test_lake_exe_produces_toolchain_json(tmp_path: Path) -> None:
    """Copy fixture so we do not mutate the committed tree's .lake cache unexpectedly."""
    dest = tmp_path / "lean_project"
    shutil.copytree(
        LEAN_PROJECT,
        dest,
        ignore=shutil.ignore_patterns(".lake", "lake-manifest.json", ".lpe"),
    )
    # Keep lean-toolchain + sources; drop any prior extraction.
    result = try_run_lake_extract(dest, force=True)
    assert result is not None
    assert result.extractor == TOOLCHAIN_EXTRACTOR
    assert result.complete is True
    assert result.errors == []
    assert result.extraction_schema_version == EXTRACTION_SCHEMA_V1_1
    names = {d.name for d in result.declarations}
    assert "LpeFixture.Core.coreVal" in names
    assert "LpeFixture.Consumer.usesCore" in names
    assert "LpeFixture.Diamond.apex" in names
    assert "LpeFixture.Chain.step3" in names
    assert "LpeFixture.LibA.seed" in names
    assert "LpeFixture.Cross.bridgeTwice" in names
    for decl in result.declarations:
        assert decl.signature_hash
        assert decl.signature_hash == sha256_text(decl.signature)
    # Schema 1.1: Environment decl edges separate from module import edges.
    assert result.declaration_dependency_edges
    assert (
        "LpeFixture.Core.coreVal",
        "LpeFixture.Diamond.apex",
    ) in result.declaration_dependency_edges
    assert ("LpeFixture.Diamond.leftBranch", "LpeFixture.Diamond.bottom") in (
        result.declaration_dependency_edges
    )
    assert result.import_edges
    assert ("LpeFixture.Core", "LpeFixture.Diamond") in result.import_edges
    assert ("LpeFixture.Diamond", "LpeFixture.Chain") in result.import_edges
    # Backward-compatible dependency_edges mirrors decl edges for toolchain.
    assert set(result.dependency_edges) == set(result.declaration_dependency_edges)
    artifact = dest / ".lpe" / "lean-extraction.json"
    assert artifact.is_file()


@pytest.mark.lean
def test_adaptive_extract_prefers_lake_toolchain(tmp_path: Path) -> None:
    dest = tmp_path / "lean_project"
    shutil.copytree(
        LEAN_PROJECT,
        dest,
        ignore=shutil.ignore_patterns(".lake", "lake-manifest.json", ".lpe"),
    )
    result = extract_lean_repository(dest)
    assert result.extractor == TOOLCHAIN_EXTRACTOR
    assert result.complete is True
    graph = build_dependency_graph(result)
    cone = impact_cone(graph, changed={"LpeFixture.Core.coreVal"})
    assert "LpeFixture.Core.helper" in cone
    assert "LpeFixture.Consumer.usesCore" in cone
    assert "LpeFixture.Consumer.usesUsesCore" in cone


@pytest.mark.lean
def test_lake_extract_diamond_and_chain_impact_cone(tmp_path: Path) -> None:
    """Hand-designed diamond + chain: cone membership from Environment decl-deps."""
    dest = tmp_path / "lean_project"
    shutil.copytree(
        LEAN_PROJECT,
        dest,
        ignore=shutil.ignore_patterns(".lake", "lake-manifest.json", ".lpe"),
    )
    result = try_run_lake_extract(dest, force=True)
    assert result is not None
    assert result.complete is True
    graph = build_dependency_graph(result)

    # Diamond: apex fans to left/right then merges at bottom.
    diamond_cone = impact_cone(graph, changed={"LpeFixture.Diamond.apex"})
    assert "LpeFixture.Diamond.leftBranch" in diamond_cone
    assert "LpeFixture.Diamond.rightBranch" in diamond_cone
    assert "LpeFixture.Diamond.bottom" in diamond_cone
    # Transitive chain past the diamond.
    assert "LpeFixture.Chain.step1" in diamond_cone
    assert "LpeFixture.Chain.step2" in diamond_cone
    assert "LpeFixture.Chain.step3" in diamond_cone
    # Unrelated consumer branch must stay out of apex cone.
    assert "LpeFixture.Consumer.usesCore" not in diamond_cone
    assert "LpeFixture.Core.helper" not in diamond_cone

    # Changing coreVal reaches diamond apex and the full chain.
    core_cone = impact_cone(graph, changed={"LpeFixture.Core.coreVal"})
    assert "LpeFixture.Diamond.apex" in core_cone
    assert "LpeFixture.Diamond.bottom" in core_cone
    assert "LpeFixture.Chain.step3" in core_cone
    assert "LpeFixture.Core.helper" in core_cone
    assert "LpeFixture.Consumer.usesUsesCore" in core_cone


@pytest.mark.lean
def test_lake_extract_import_expansion_semantics(tmp_path: Path) -> None:
    dest = tmp_path / "lean_project"
    shutil.copytree(
        LEAN_PROJECT,
        dest,
        ignore=shutil.ignore_patterns(".lake", "lake-manifest.json", ".lpe"),
    )
    result = extract_lean_repository(
        dest,
        baseline_imports=["LpeFixture.Core"],
    )
    assert result.extractor == TOOLCHAIN_EXTRACTOR
    diff = result.import_diff or import_expansion(["LpeFixture.Core"], result.imports)
    # New fixture modules beyond the baseline Core import.
    assert "LpeFixture.Diamond" in diff["added"] or "LpeFixture.Chain" in diff["added"]
    assert "LpeFixture.Core" not in diff["added"]
    assert "LpeFixture.Core" not in diff["removed"]
    # Module→module edges present for designed imports.
    edge_set = set(result.import_edges)
    assert ("LpeFixture.Core", "LpeFixture.Consumer") in edge_set
    assert ("LpeFixture.Diamond", "LpeFixture.Chain") in edge_set


@pytest.mark.lean
def test_lake_extract_multi_module_cross_branch_impact_cone(tmp_path: Path) -> None:
    """Hand-audited LibA→…→Cross (+ Consumer fan-in) cone membership."""
    dest = tmp_path / "lean_project"
    shutil.copytree(
        LEAN_PROJECT,
        dest,
        ignore=shutil.ignore_patterns(".lake", "lake-manifest.json", ".lpe"),
    )
    expectations = json.loads(
        (LEAN_PROJECT / "expectations_multi_module.json").read_text(encoding="utf-8")
    )
    result = try_run_lake_extract(dest, force=True)
    assert result is not None
    assert result.complete is True
    names = {d.name for d in result.declarations}
    assert "LpeFixture.LibA.seed" in names
    assert "LpeFixture.Cross.bridge" in names
    graph = build_dependency_graph(result)

    for changed, spec in expectations["cones"].items():
        cone = impact_cone(graph, changed={changed})
        for name in spec["must_include"]:
            assert name in cone, f"{changed}: expected {name} in cone"
        for name in spec["must_exclude"]:
            assert name not in cone, f"{changed}: unexpected {name} in cone"

    edge_set = set(tuple(e) for e in result.import_edges)
    for a, b in expectations["import_edges_must_include"]:
        assert (a, b) in edge_set


@pytest.mark.docker
@pytest.mark.lean
def test_docker_combined_multi_module_cone_when_image_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same multi-module cones via one Docker combined build+extract (no host Lake)."""
    import os

    from lpe.execution.sandbox import (
        DEFAULT_LEAN_DOCKER_IMAGE,
        DockerSandboxExecutor,
        docker_image_present,
        parse_combined_phase,
    )
    from lpe.lean.toolchain import (
        NOTE_DOCKER_EXTRACT,
        finalize_extract_from_exit,
    )

    image = os.environ.get("LPE_LEAN_DOCKER_IMAGE", DEFAULT_LEAN_DOCKER_IMAGE)
    if not docker_image_present(image):
        pytest.skip(f"Lean Docker image {image!r} not present")

    dest = tmp_path / "lean_project"
    shutil.copytree(
        LEAN_PROJECT,
        dest,
        ignore=shutil.ignore_patterns(".lake", "lake-manifest.json", ".lpe"),
    )
    expectations = json.loads(
        (LEAN_PROJECT / "expectations_multi_module.json").read_text(encoding="utf-8")
    )
    monkeypatch.setenv("LPE_DOCKER_IMAGE", image)
    monkeypatch.setattr("lpe.lean.toolchain._lake_bin", lambda: None)

    executor = DockerSandboxExecutor(network_none=True)
    result = executor.verify_build_and_extract(
        repository=dest,
        build_command=["lake", "build"],
        extract_out=".lpe/lean-extraction.json",
        timeout_seconds=600,
        max_output_bytes=2_000_000,
        environment_allowlist=["PATH", "HOME", "USER", "TMPDIR"],
    )
    assert parse_combined_phase(result.stderr, result.stdout) == "ok"
    assert result.exit_code == 0, (result.stderr or result.stdout)[:1500]

    loaded = finalize_extract_from_exit(
        dest,
        returncode=0,
        stdout=result.stdout,
        stderr=result.stderr,
        provenance_note=NOTE_DOCKER_EXTRACT,
        via_executor=True,
    )
    assert loaded is not None
    assert loaded.complete is True
    graph = build_dependency_graph(loaded)
    for changed, spec in expectations["cones"].items():
        cone = impact_cone(graph, changed={changed})
        for name in spec["must_include"]:
            assert name in cone, f"{changed}: expected {name} in cone"
        for name in spec["must_exclude"]:
            assert name not in cone, f"{changed}: unexpected {name} in cone"


@pytest.mark.lean
def test_lake_extract_opaque_kinds_and_limitation_notes(tmp_path: Path) -> None:
    """Real Lake extract: opaque kind present; limitation notes honest.

    Does not claim that opaque body internals appear in impact cones — only
    that Lean-emitted edges are used and residual limitations are documented.
    Axiom kinds are covered by synthetic IR unit tests (fixture axioms would
    fail lean.prohibited_axioms on E2E ACCEPT paths).
    """
    dest = tmp_path / "lean_project"
    shutil.copytree(
        LEAN_PROJECT,
        dest,
        ignore=shutil.ignore_patterns(".lake", "lake-manifest.json", ".lpe"),
    )
    result = try_run_lake_extract(dest, force=True)
    assert result is not None
    assert result.complete is True
    by_name = {d.name: d for d in result.declarations}
    assert "LpeFixture.OpaqueLimits.secretOpaque" in by_name
    assert by_name["LpeFixture.OpaqueLimits.secretOpaque"].kind == "opaque"
    assert "LpeFixture.OpaqueLimits.seedAxiom" not in by_name
    assert any("opaque/axiom" in n or "limitations:" in n for n in result.notes)
    graph = build_dependency_graph(result)
    cone = impact_cone(graph, changed={"LpeFixture.OpaqueLimits.secretOpaque"})
    assert "LpeFixture.OpaqueLimits.usesOpaque" in cone
    # hiddenHelper may or may not appear depending on Lean's opaque value storage;
    # never invent a cone membership claim beyond emitted edges.
    edges = set(result.declaration_dependency_edges)
    if (
        "LpeFixture.OpaqueLimits.hiddenHelper",
        "LpeFixture.OpaqueLimits.secretOpaque",
    ) not in edges:
        assert "LpeFixture.OpaqueLimits.hiddenHelper" not in cone


@pytest.mark.lean
def test_without_lean_json_regex_stub_remains_incomplete(tmp_path: Path) -> None:
    """Honesty: deleting JSON and disabling toolchain run keeps regex-stub incomplete."""
    dest = tmp_path / "lean_project"
    shutil.copytree(
        LEAN_PROJECT,
        dest,
        ignore=shutil.ignore_patterns(".lake", "lake-manifest.json", ".lpe"),
    )
    result = extract_lean_repository(dest, run_toolchain=False)
    assert result.extractor == REGEX_STUB_EXTRACTOR
    assert result.complete is False
