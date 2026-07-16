#!/usr/bin/env python3
"""Verify a clean-clone bootstrap: install, test, and lpe doctor."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from shutil import which


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _lpe_executable() -> str:
    scripts_dir = Path(sys.executable).parent
    name = "lpe.exe" if os.name == "nt" else "lpe"
    candidate = scripts_dir / name
    if candidate.exists():
        return str(candidate)
    found = which("lpe")
    if found:
        return found
    raise FileNotFoundError("lpe CLI not found after editable install")


def run_step(label: str, command: list[str], *, cwd: Path) -> None:
    print(f"==> {label}")
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    root = _repo_root()
    python = sys.executable

    run_step(
        "pip install editable package with dev extras",
        [python, "-m", "pip", "install", "-e", ".[dev]"],
        cwd=root,
    )
    run_step("pytest", [python, "-m", "pytest", "-q"], cwd=root)
    run_step("lpe doctor", [_lpe_executable(), "doctor"], cwd=root)

    print("Clean-clone verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
