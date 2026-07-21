"""GitHub Checks API submission via ``gh api`` (dry-run by default).

Payload rendering lives in ``lpe.github.check``. This module only adapts a
rendered Checks API body to a ``gh api`` invocation. Live POST requires an
explicit ``post=True`` / ``--post`` flag so CI and local runs never surprise-
create check runs.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

# Sentinels that must never be POSTed as head_sha (dry-run plan also refuses).
_REFUSED_HEAD_SHAS = frozenset({"", "mock-sha", "unavailable-sha"})

_AUTH_HINT_RE = re.compile(
    r"(auth|authenticat|login|credential|token|HTTP\s*40[13]|forbidden)",
    re.IGNORECASE,
)


class GitHubSubmitError(RuntimeError):
    """Raised when a check-run submission cannot proceed or fails."""


Runner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True)
class CheckSubmitPlan:
    """Planned ``gh api`` invocation (always safe to inspect; POST is opt-in)."""

    owner: str
    repo: str
    endpoint: str
    argv: tuple[str, ...]
    payload: dict[str, Any]
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner,
            "repo": self.repo,
            "endpoint": self.endpoint,
            "argv": list(self.argv),
            "payload": self.payload,
            "dry_run": self.dry_run,
            "posted": False,
            "stdin_json": True,
            "command_preview": format_gh_api_command_preview(self.argv),
        }


@dataclass(frozen=True)
class CheckSubmitResult:
    plan: CheckSubmitPlan
    posted: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = self.plan.to_dict()
        data["posted"] = self.posted
        data["exit_code"] = self.exit_code
        data["stdout"] = self.stdout
        data["stderr"] = self.stderr
        return data


def format_gh_api_command_preview(argv: tuple[str, ...] | list[str]) -> str:
    """Shell-ish preview of the planned ``gh api`` argv (payload on stdin)."""
    return " ".join(argv) + "  # JSON body on stdin (--input -)"


def ensure_gh_on_path() -> str:
    """Return path to ``gh`` or raise a clear operator error."""
    path = shutil.which("gh")
    if path is None:
        raise GitHubSubmitError(
            "gh CLI not found on PATH. Install GitHub CLI "
            "(https://cli.github.com/) and authenticate with `gh auth login`, "
            "or omit --post to keep dry-run only."
        )
    return path


def classify_gh_api_failure(*, returncode: int, stdout: str, stderr: str) -> str:
    """Build an operator-facing error message from a failed ``gh api`` run."""
    detail = (stderr or stdout or "").strip() or "(no stderr/stdout)"
    if _AUTH_HINT_RE.search(detail) or returncode in {4, 127}:
        return (
            f"gh api authentication/authorization failed (exit {returncode}): "
            f"{detail}. Run `gh auth status` and ensure the token can write "
            "Checks (`checks:write`) on the target repo."
        )
    return f"gh api check-run failed (exit {returncode}): {detail}"


def build_check_run_api_argv(
    *,
    owner: str,
    repo: str,
) -> list[str]:
    """Build ``gh api`` argv for creating a check run (stdin JSON body)."""
    owner_clean = owner.strip()
    repo_clean = repo.strip()
    if not owner_clean or not repo_clean:
        raise GitHubSubmitError("owner and repo must be non-empty")
    if "/" in owner_clean or "/" in repo_clean:
        raise GitHubSubmitError("owner and repo must be separate arguments (not 'owner/repo')")
    endpoint = f"repos/{owner_clean}/{repo_clean}/check-runs"
    return [
        "gh",
        "api",
        endpoint,
        "--method",
        "POST",
        "--input",
        "-",
    ]


def plan_check_run_submit(
    payload: Mapping[str, Any],
    *,
    owner: str,
    repo: str,
    dry_run: bool = True,
) -> CheckSubmitPlan:
    """Validate payload shape and build a dry-run-friendly submission plan."""
    if not isinstance(payload, Mapping):
        raise GitHubSubmitError("payload must be a mapping")
    required = ("name", "head_sha", "status", "conclusion", "output")
    missing = [key for key in required if key not in payload]
    if missing:
        raise GitHubSubmitError(f"check payload missing required keys: {missing}")
    head_sha = payload.get("head_sha")
    if head_sha is None or head_sha in _REFUSED_HEAD_SHAS:
        raise GitHubSubmitError(
            "refusing to submit check with missing or sentinel head_sha "
            f"(got {head_sha!r}; use a real commit SHA, never mock-sha / "
            "unavailable-sha)"
        )
    argv = build_check_run_api_argv(owner=owner, repo=repo)
    body = dict(payload)
    return CheckSubmitPlan(
        owner=owner.strip(),
        repo=repo.strip(),
        endpoint=argv[2],
        argv=tuple(argv),
        payload=body,
        dry_run=dry_run,
    )


def submit_check_run(
    payload: Mapping[str, Any],
    *,
    owner: str,
    repo: str,
    post: bool = False,
    runner: Runner | None = None,
) -> CheckSubmitResult:
    """Submit a rendered check payload via ``gh api``.

    Default is dry-run (``post=False``): returns the plan without invoking ``gh``.
    Pass ``post=True`` to execute; tests should inject a mocked ``runner``.
    """
    plan = plan_check_run_submit(payload, owner=owner, repo=repo, dry_run=not post)
    if not post:
        return CheckSubmitResult(plan=plan, posted=False)

    if runner is None:
        ensure_gh_on_path()

    execute: Runner = runner or subprocess.run
    completed = execute(
        list(plan.argv),
        input=json.dumps(plan.payload, sort_keys=True),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise GitHubSubmitError(
            classify_gh_api_failure(
                returncode=completed.returncode,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
            )
        )
    return CheckSubmitResult(
        plan=plan,
        posted=True,
        exit_code=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def parse_owner_repo(slug: str) -> tuple[str, str]:
    """Parse ``owner/repo`` into components."""
    parts = slug.strip().split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise GitHubSubmitError(f"expected owner/repo slug, got {slug!r}")
    return parts[0], parts[1]
