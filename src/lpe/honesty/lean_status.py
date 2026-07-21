"""Lean / extractor honesty for ``lpe doctor`` and ``lpe lean status``."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from lpe.lean.extractor import (
    REGEX_STUB_EXTRACTOR,
    TOOLCHAIN_EXTRACTOR,
    lean_toolchain_available,
)

MATHLIB_SCALE_WARNING = (
    "not Mathlib-scale: fixture / project toolchain extraction is not "
    "elaborator-complete Mathlib evidence; do not claim Mathlib-scale kernel truth"
)

REGEX_STUB_WARNING = (
    f"extractor mode is {REGEX_STUB_EXTRACTOR!r}: lexical AST-lite only; "
    "kernel / axiom findings are incomplete and must not be treated as closure"
)


def lean_extractor_status(repository: Path | None = None) -> dict[str, Any]:
    """Report which extractor path is available without running extraction.

    Prefer toolchain when ``lake``/``lean`` are on PATH; otherwise regex-stub.
    Always includes an explicit Mathlib-scale non-claim.
    """
    lake = shutil.which("lake")
    lean = shutil.which("lean")
    toolchain_on_path = lean_toolchain_available(repository)
    mode = TOOLCHAIN_EXTRACTOR if toolchain_on_path else REGEX_STUB_EXTRACTOR

    artifact = None
    artifact_complete: bool | None = None
    if repository is not None:
        artifact_path = repository / ".lpe" / "lean-extraction.json"
        if artifact_path.is_file():
            artifact = str(artifact_path.resolve())
            try:
                import json

                data = json.loads(artifact_path.read_text(encoding="utf-8"))
                artifact_complete = bool(data.get("complete"))
                claimed = str(data.get("extractor") or "")
                if claimed == TOOLCHAIN_EXTRACTOR and artifact_complete:
                    mode = TOOLCHAIN_EXTRACTOR
                elif claimed == REGEX_STUB_EXTRACTOR or not artifact_complete:
                    # Prefer honesty: incomplete artifact ⇒ stub semantics.
                    if not toolchain_on_path:
                        mode = REGEX_STUB_EXTRACTOR
            except (OSError, ValueError, TypeError):
                artifact_complete = None

    warnings: list[str] = [MATHLIB_SCALE_WARNING]
    if mode == REGEX_STUB_EXTRACTOR:
        warnings.append(REGEX_STUB_WARNING)
    elif not toolchain_on_path:
        warnings.append(
            "toolchain extractor id may appear in artifacts, but lake/lean are "
            "not on PATH for this process"
        )

    return {
        "extractor_mode": mode,
        "toolchain_available": toolchain_on_path,
        "lake": lake,
        "lean": lean,
        "artifact": artifact,
        "artifact_complete": artifact_complete,
        "mathlib_scale": False,
        "warnings": warnings,
        "note": (
            "Toolchain mode means Lake/Lean elaborator IR may be available for "
            "this host; it does not imply Mathlib-scale completeness."
        ),
    }
