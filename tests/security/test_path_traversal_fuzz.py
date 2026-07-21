"""AUDIT-025: path traversal adversarial cases on candidate paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from lpe.evidence.compiler import compile_evidence
from lpe.models import CandidateDescriptor, GeneratorProvenance
from lpe.paths import PathTraversalError, assert_safe_repo_relative


@pytest.mark.parametrize(
    "relative",
    [
        "../etc/passwd",
        "..\\Windows\\System32",
        "/etc/passwd",
        "src/../../secret",
        "C:/Windows/System32",
        "~/secret",
        "foo/../../../etc/shadow",
        "Example/../../../outside.lean",
        "..",
        "../",
        "a/b/../../c/../../../x",
    ],
)
def test_assert_safe_repo_relative_rejects_traversal(tmp_path: Path, relative: str) -> None:
    """Invariant: any escape / absolute / home path is refused before resolve."""
    with pytest.raises(PathTraversalError):
        assert_safe_repo_relative(tmp_path, relative)


@pytest.mark.parametrize(
    "relative",
    [
        "src/Foo.lean",
        "Example/Public/Api.lean",
        "nested/dir/file.lean",
    ],
)
def test_assert_safe_repo_relative_accepts_nested(tmp_path: Path, relative: str) -> None:
    (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / relative).write_text("-- lean\n", encoding="utf-8")
    resolved = assert_safe_repo_relative(tmp_path, relative)
    assert resolved == (tmp_path / relative).resolve()


def test_compile_rejects_changed_paths_traversal(example_project: Path) -> None:
    """Invariant: evidence compile refuses traversal in changed_paths before build."""
    candidate = CandidateDescriptor(
        candidate_id="c-traversal-paths",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        claimed_intent="probe",
        changed_paths=["../../../etc/passwd"],
        patch_text="diff --git a/x b/x\n",
        generator=GeneratorProvenance(generator_type="human", name="test", version="0"),
    )
    with pytest.raises(PathTraversalError):
        compile_evidence(example_project, candidate, skip_build=True)


def test_compile_rejects_patch_path_traversal(example_project: Path, tmp_path: Path) -> None:
    """Invariant: patch_path outside the repo is refused."""
    outside = tmp_path / "outside.patch"
    outside.write_text("diff --git a/x b/x\n", encoding="utf-8")
    # Relative form that escapes when resolved under the project.
    candidate = CandidateDescriptor(
        candidate_id="c-traversal-patch",
        project_id="example-category-project",
        obligation_ids=["O-01"],
        base_commit="deadbeef",
        claimed_intent="probe",
        changed_paths=["README.md"],
        patch_path="../../../etc/passwd",
        generator=GeneratorProvenance(generator_type="human", name="test", version="0"),
    )
    with pytest.raises(PathTraversalError):
        compile_evidence(example_project, candidate, skip_build=True)


def test_empty_relative_path_rejected(tmp_path: Path) -> None:
    with pytest.raises(PathTraversalError, match="non-empty"):
        assert_safe_repo_relative(tmp_path, "   ")
