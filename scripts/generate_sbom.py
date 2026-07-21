#!/usr/bin/env python3
"""Generate release SBOM artifacts without requiring syft (§8.3 / §19.5).

Writes CycloneDX-ish JSON for the Python package from ``pyproject.toml``,
plus optional Docker image identity when ``docker`` + image are available.
When ``syft`` is on PATH, also emits full CycloneDX for the image/dir.

Usage:
  python scripts/generate_sbom.py
  python scripts/generate_sbom.py --out-dir artifacts/sbom --image lpe-lean:4.14
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _write_python_bom(repo: Path, out_dir: Path) -> Path:
    data = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    proj = data["project"]
    name = str(proj["name"])
    version = str(proj["version"])
    components = []
    for dep in proj.get("dependencies", []):
        dep_s = str(dep)
        pkg = dep_s.split(">=")[0].split("==")[0].split("[")[0].strip()
        components.append(
            {
                "type": "library",
                "name": pkg,
                "purl": f"pkg:pypi/{pkg}",
            }
        )
    doc = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "component": {
                "type": "library",
                "name": name,
                "version": version,
                "bom-ref": f"pkg:pypi/{name}@{version}",
            }
        },
        "components": components,
        "notes": [
            "Generated from pyproject.toml dependencies. Install syft for a "
            "full filesystem/image SBOM.",
        ],
    }
    path = out_dir / "lean-project-evidence.cdx.json"
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return path


def _pip_freeze(out_dir: Path) -> Path | None:
    path = out_dir / "python-pip-freeze.txt"
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "freeze"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    path.write_text(proc.stdout, encoding="utf-8")
    return path


def _docker_image_identity(image: str, out_dir: Path) -> list[Path]:
    if shutil.which("docker") is None:
        return []
    inspect = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
    )
    if inspect.returncode != 0:
        (out_dir / "lpe-lean.sbom.README.txt").write_text(
            f"Image {image!r} not present; build with "
            "scripts/build_lean_docker_image.sh then re-run.\n",
            encoding="utf-8",
        )
        return []
    written: list[Path] = []
    inspect_path = out_dir / "lpe-lean.inspect.json"
    inspect_path.write_text(inspect.stdout, encoding="utf-8")
    written.append(inspect_path)
    digest = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            "--format",
            "{{index .RepoDigests 0}}\n{{.Id}}",
            image,
        ],
        capture_output=True,
        text=True,
    )
    if digest.returncode == 0:
        dpath = out_dir / "lpe-lean.digest.txt"
        dpath.write_text(digest.stdout, encoding="utf-8")
        written.append(dpath)
    return written


def _try_syft(target: str, out_path: Path) -> bool:
    if shutil.which("syft") is None:
        return False
    try:
        subprocess.run(
            ["syft", target, "-o", f"cyclonedx-json={out_path}"],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return out_path.is_file()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Output directory (default: artifacts/sbom)",
    )
    parser.add_argument("--image", default="lpe-lean:4.14")
    parser.add_argument(
        "--skip-image",
        action="store_true",
        help="Skip Docker image identity / syft image SBOM",
    )
    args = parser.parse_args(argv)
    repo = _repo_root()
    out_dir = args.out_dir or (repo / "artifacts" / "sbom")
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = [_write_python_bom(repo, out_dir)]
    freeze = _pip_freeze(out_dir)
    if freeze:
        written.append(freeze)

    if _try_syft(f"dir:{repo}", out_dir / "lean-project-evidence.syft.cdx.json"):
        written.append(out_dir / "lean-project-evidence.syft.cdx.json")

    if not args.skip_image:
        written.extend(_docker_image_identity(args.image, out_dir))
        if _try_syft(f"docker:{args.image}", out_dir / "lpe-lean.cdx.json"):
            written.append(out_dir / "lpe-lean.cdx.json")

    print("SBOM artifacts:")
    for path in written:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
