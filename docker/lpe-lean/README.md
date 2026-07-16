# `lpe-lean` Docker image

Local Lean-capable image for sandboxed Lake builds **and** post-build
`lake exe lpe_extract` (`network_policy: deny` → `--network=none`). The default
LPE image `ubuntu:22.04` has **no** Lean; isolation PASS on that image does
**not** imply typecheck or toolchain extract.

## Tag

| Tag | Toolchain |
| --- | --- |
| `lpe-lean:4.14` | `leanprover/lean4:v4.14.0` (matches `tests/fixtures/lean_project/lean-toolchain`) |

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

## Why not a Hub image?

There is no maintained official `leanprover/lean4` Docker Hub image. Community
tags (e.g. `leanprovercommunity/lean4`) are often stale — prefer this local pin.
See `SECURITY.md`.
