from __future__ import annotations

import re
import subprocess
from pathlib import Path

from lpe.models import ArtifactType, ChangedDeclaration

DECLARATION = re.compile(
    r"^(?P<prefix>[+-])\s*(?P<kind>theorem|lemma|def|abbrev|instance|structure|class)\s+"
    r"(?P<name>[A-Za-z0-9_.'«»]+)"
)

KIND_MAP = {
    "theorem": ArtifactType.THEOREM,
    "lemma": ArtifactType.THEOREM,
    "def": ArtifactType.DEFINITION,
    "abbrev": ArtifactType.ABBREV,
    "instance": ArtifactType.INSTANCE,
    "structure": ArtifactType.STRUCTURE,
    "class": ArtifactType.CLASS,
}


class GitError(RuntimeError):
    pass


def resolve_commit(repository: Path, revision: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "--verify", f"{revision}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if stderr:
            raise GitError(
                f"cannot resolve revision {revision!r}: {stderr}. "
                "Use a branch, tag, or full commit hash."
            )
        raise GitError(
            f"cannot resolve revision {revision!r}: use a branch, tag, or full commit hash"
        )
    return result.stdout.strip()


def changed_paths(repository: Path, base: str, head: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repository), "diff", "--name-only", base, head],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or f"cannot diff {base}..{head}")
    return [line for line in result.stdout.splitlines() if line]


def _is_public_path(path: str, public_api_prefixes: tuple[str, ...]) -> bool:
    if not public_api_prefixes:
        return False
    normalized = path.replace("\\", "/")
    return any(normalized.startswith(prefix.rstrip("/") + "/") or normalized == prefix for prefix in public_api_prefixes)


def classify_added_declarations(
    repository: Path,
    base: str,
    head: str,
    *,
    public_api_prefixes: tuple[str, ...] = (),
) -> list[ChangedDeclaration]:
    result = subprocess.run(
        ["git", "-C", str(repository), "diff", "--unified=0", base, head, "--", "*.lean"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GitError(result.stderr.strip())

    current_path = ""
    added: dict[str, str] = {}
    removed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if line.startswith("+++ b/"):
            current_path = line.removeprefix("+++ b/")
            continue
        match = DECLARATION.match(line)
        if not match or not current_path:
            continue
        key = f"{current_path}::{match.group('name')}"
        if match.group("prefix") == "+":
            added[key] = match.group("kind")
        else:
            removed[key] = match.group("kind")

    declarations: list[ChangedDeclaration] = []
    all_keys = set(added) | set(removed)
    for key in sorted(all_keys):
        path, name = key.split("::", 1)
        kind_name = added.get(key) or removed.get(key)
        kind = KIND_MAP[kind_name]
        is_new = key in added and key not in removed
        is_removed = key in removed and key not in added
        signature_changed = key in added and key in removed
        if is_removed and not is_new:
            continue
        declarations.append(
            ChangedDeclaration(
                name=name,
                kind=kind,
                path=path,
                signature_changed=signature_changed,
                public=_is_public_path(path, public_api_prefixes),
            )
        )
    return declarations
