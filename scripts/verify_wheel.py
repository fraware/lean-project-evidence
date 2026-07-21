#!/usr/bin/env python3
"""Install a built wheel into a temp venv and smoke-import ``lpe`` (§19.4).

Usage:
  python scripts/verify_wheel.py dist/*.whl
  python scripts/verify_wheel.py dist/lean_project_evidence-0.2.0-py3-none-any.whl
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "wheels",
        nargs="+",
        type=Path,
        help="One or more wheel paths (globs must be expanded by the shell).",
    )
    args = parser.parse_args(argv)
    wheels = [p.resolve() for p in args.wheels]
    missing = [p for p in wheels if not p.is_file()]
    if missing:
        print(f"wheel(s) not found: {missing}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="lpe-wheel-smoke-") as tmp:
        root = Path(tmp)
        venv_dir = root / "venv"
        venv.create(venv_dir, with_pip=True)
        if sys.platform == "win32":
            python = venv_dir / "Scripts" / "python.exe"
            pip = venv_dir / "Scripts" / "pip.exe"
        else:
            python = venv_dir / "bin" / "python"
            pip = venv_dir / "bin" / "pip"
        _run([str(pip), "install", "--upgrade", "pip"])
        for wheel in wheels:
            _run([str(pip), "install", str(wheel)])
        _run(
            [
                str(python),
                "-c",
                "import lpe; from lpe.cli import app; "
                "assert lpe.__version__; print('wheel_smoke_ok', lpe.__version__)",
            ]
        )
    print("verify_wheel: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
