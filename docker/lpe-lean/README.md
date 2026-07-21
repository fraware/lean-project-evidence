# `lpe-lean` Docker image

Local Lean-capable image for sandboxed Lake builds **and** post-build
`lake exe lpe_extract` (`network_policy: deny` → `--network=none`). The default
LPE image `ubuntu:22.04` has **no** Lean; isolation PASS on that image does
**not** imply typecheck or toolchain extract.

## Tag

| Tag | Toolchain |
| --- | --- |
| `lpe-lean:4.14` | `leanprover/lean4:v4.14.0` (matches `tests/fixtures/lean_project/lean-toolchain`) |

Elan is installed from a **checksum-pinned** GitHub release tarball
(`ELAN_VERSION` / `ELAN_SHA256` in the Dockerfile), not via `curl | sh`.

## Build (Windows Docker Desktop or Linux)

From the repository root:

```powershell
# Windows (PowerShell)
.\scripts\build_lean_docker_image.ps1
```

```bash
# Linux / macOS / Git Bash
./scripts/build_lean_docker_image.sh
```

First build downloads elan + Lean and may take several minutes and hundreds of MB.
Pytest never rebuilds the image; it only `docker image inspect`s an existing tag.

## Use with LPE

```powershell
$env:LPE_DOCKER_IMAGE = "lpe-lean:4.14"
lpe evidence compile --repo path\to\project ...
```

```bash
export LPE_DOCKER_IMAGE=lpe-lean:4.14
lpe evidence compile --repo path/to/project ...
```

Contract `network_policy: deny` selects Docker `--network=none`. Isolation
`execution.isolation` is PASS only when that sandboxed build actually ran.

Prefer recording the image **digest** in executor provenance (mutable tags are
insufficient for automatic acceptance).

## Follow-ups (CLOSURE-004)

- **SBOM:** `python scripts/generate_sbom.py` (or `./scripts/generate_sbom.sh`)
  writes CycloneDX-ish JSON under `artifacts/sbom/`. With `syft` on PATH and a
  local `lpe-lean:4.14` image, image SBOM is included; otherwise Python package
  BOM + image digest/inspect stubs are emitted. Scheduled CI runs the Python
  recipe weekly.
- **Record local digest (no registry login):**
  `./scripts/record_lean_docker_digest.sh` or
  `.\scripts\record_lean_docker_digest.ps1` writes `lpe-lean.digest.txt` and a
  publish-by-digest operator recipe under `artifacts/sbom/`.
- **Publish by digest:** push to a registry (operator login required), then pin
  runtime / CI to `image@sha256:...` rather than a floating tag. See the recipe
  file emitted by the record script.
- **CI vuln scan:** scheduled image build + vulnerability scan gate before
  promoting a digest (image build remains opt-in; never built in default PR CI).

## Why not a Hub image?

There is no maintained official `leanprover/lean4` Docker Hub image. Community
tags (e.g. `leanprovercommunity/lean4`) are often stale — prefer this local pin.
See `SECURITY.md`.
