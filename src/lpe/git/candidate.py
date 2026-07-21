from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from lpe.git.diff import GitError, changed_paths, classify_added_declarations, resolve_commit
from lpe.models import CandidateDescriptor, ProjectContract

_NULL_OID = "0" * 40


def normalize_revision(repository: Path, revision: str) -> str:
    """Resolve a git revision to a full commit hash."""
    return resolve_commit(repository, revision)


def is_git_repository(repository: Path) -> bool:
    """Return True when ``repository`` is inside a git work tree."""
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def is_git_toplevel(repository: Path) -> bool:
    """Return True when ``repository`` is the git work tree root."""
    if not is_git_repository(repository):
        return False
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False
    return Path(result.stdout.strip()).resolve() == repository.resolve()


def repository_has_commits(repository: Path) -> bool:
    """Return True when the repository has at least one commit."""
    if not is_git_repository(repository):
        return False
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _reject_null_oid(label: str, revision: str) -> None:
    normalized = revision.strip().lower()
    if normalized == _NULL_OID or set(normalized) == {"0"}:
        raise GitError(
            f"{label} {revision!r} is a null/fake git object id. "
            "Provide a real branch, tag, or commit hash that exists in the repository."
        )


def enrich_candidate_from_git(
    repository: Path,
    candidate: CandidateDescriptor,
    contract: ProjectContract,
) -> CandidateDescriptor:
    """Verify revisions and replace self-declared risk metadata from git.

    When the project is a git toplevel with commits (or the candidate supplies
    ``head_commit``), base/head are resolved and ``changed_paths`` /
    ``changed_declarations`` (including ``public`` and ``signature_changed``)
    are taken from git classification — self-declared values are ignored.
    ``foundational`` is not inferred from git diffs in v0 (remains false unless
    supplied on a non-forced path).
    """
    if not is_git_repository(repository):
        return candidate

    force = bool(candidate.head_commit) or (
        is_git_toplevel(repository) and repository_has_commits(repository)
    )
    if not force:
        return candidate

    _reject_null_oid("base_commit", candidate.base_commit)
    if candidate.head_commit is not None:
        _reject_null_oid("head_commit", candidate.head_commit)

    if candidate.head_commit is None:
        # Patch-only candidate against a real git project: still verify base.
        base = normalize_revision(repository, candidate.base_commit)
        return candidate.model_copy(update={"base_commit": base})

    base = normalize_revision(repository, candidate.base_commit)
    head = normalize_revision(repository, candidate.head_commit)
    public_prefixes = tuple(contract.project.repository.public_api_paths)

    paths = changed_paths(repository, base, head)
    declarations = classify_added_declarations(
        repository,
        base,
        head,
        public_api_prefixes=public_prefixes,
    )

    return candidate.model_copy(
        update={
            "base_commit": base,
            "head_commit": head,
            "changed_paths": paths,
            "changed_declarations": declarations,
        }
    )


def build_candidate_from_commits(
    repository: Path,
    contract: ProjectContract,
    *,
    candidate_id: str,
    project_id: str,
    obligation_ids: list[str],
    base_commit: str,
    head_commit: str,
    claimed_intent: str,
    generator: dict[str, Any],
) -> CandidateDescriptor:
    _reject_null_oid("base_commit", base_commit)
    _reject_null_oid("head_commit", head_commit)
    base = normalize_revision(repository, base_commit)
    head = normalize_revision(repository, head_commit)
    public_prefixes = tuple(contract.project.repository.public_api_paths)
    paths = changed_paths(repository, base, head)
    declarations = classify_added_declarations(
        repository,
        base,
        head,
        public_api_prefixes=public_prefixes,
    )
    from lpe.models import GeneratorProvenance

    return CandidateDescriptor(
        candidate_id=candidate_id,
        project_id=project_id,
        obligation_ids=obligation_ids,
        base_commit=base,
        head_commit=head,
        claimed_intent=claimed_intent,
        changed_paths=paths,
        changed_declarations=declarations,
        generator=GeneratorProvenance.model_validate(generator),
    )
