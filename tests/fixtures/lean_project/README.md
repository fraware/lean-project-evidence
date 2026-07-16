# Lean project fixture (toolchain extraction)

Minimal Lean 4 + Lake package used by `@pytest.mark.lean` tests.

Modules:

- `Core` → `Consumer` / `Diamond` → `Chain` (diamond + transitive chain)
- `LibA` → `LibB` → `LibC` → `Cross` (multi-module stress; `Cross` also
  imports `Consumer` for cross-branch fan-in)

Hand-audited cone expectations: `expectations_multi_module.json`.

## Requirements

- Lean 4.14.x / Lake (see `lean-toolchain`)
- Not required for default CI without Lean — those tests skip cleanly
- **Do not vendor Mathlib** — fixture stays self-contained

## Produce toolchain extraction

```bash
lake build
lake exe lpe_extract
# writes .lpe/lean-extraction.json (gitignored; regenerated in tests)
```

Or via CLI / Python:

```bash
lpe lean extract --repo tests/fixtures/lean_project
```

```python
from lpe.lean import extract_lean_repository
extract_lean_repository(Path("tests/fixtures/lean_project"))
```

## E2E evidence compile (no skip-build)

On a host with Lean 4.14 + Lake, integration tests run:

```text
compile_evidence(..., skip_build=False, insecure_host_exec=True)
```

with `network_policy: allow`. Default Docker (`ubuntu:22.04`) has no Lean — use
`--insecure-host-exec` for toolchain-complete packets, **or** build the local
Lean image and set:

```text
LPE_DOCKER_IMAGE=lpe-lean:4.14
```

Then `network_policy: deny` yields sandboxed `--network=none` builds with
`execution.isolation` PASS **and** a real Lake typecheck (when the image is
present). Docker prefers **one** `docker run` for `lake build && lake exe
lpe_extract` (`combined_build_extract` / `sandbox_invocations: 1`). Set
`LPE_DOCKER_COMBINED_BUILD_EXTRACT=0` for sequential fallback (two containers).
Host Lake is not required for the Docker toolchain path. Pytest only
`docker image inspect`s — it never rebuilds.

### Build the Lean Docker image

From the repository root (Windows Docker Desktop or Linux):

```powershell
.\scripts\build_lean_docker_image.ps1
```

```bash
./scripts/build_lean_docker_image.sh
```

See `docker/lpe-lean/README.md` and `SECURITY.md`. First build downloads elan +
Lean (several minutes / hundreds of MB).

## Export protocol (schema 1.1)

Partner projects can ship the same schema by:

1. Declaring a Lake exe named `lpe_extract` that writes `.lpe/lean-extraction.json`, or
2. Setting `LPE_LEAN_EXTRACT_CMD` to a custom command, or
3. Committing a pre-built `.lpe/lean-extraction.json` with `extractor: lean.toolchain` and `complete: true`

### JSON fields (schema `extraction_schema_version: "1.1"`)

| Field | Meaning |
| --- | --- |
| `declaration_dependency_edges` | `[dependee, depender]` from `ConstantInfo.getUsedConstantsAsSet` |
| `import_edges` | `[imported_module, importing_module]` from Environment `ModuleData` |
| `dependency_edges` | Backward-compatible mirror of declaration edges (toolchain) |
| `imports` | Fixture modules observed as imports of other fixture modules |
| `import_diff` | Filled by Python: `{added, removed}` vs a baseline import list |

Older artifacts without `extraction_schema_version` remain loadable (implicit `1.0`).

Without a toolchain artifact, LPE uses `regex-stub` and never claims axiom PASS.

## Residual limitations

Even with elaborator Environment IR:

- Tactic proofs may erase intermediate constants; only constants remaining in
  the elaborated type/value are observed.
- Opaque / axiom / quotient constants expose only what Lean stores (no extra
  body unfold).
- Import edges are module→module, not per-declaration import provenance.
- Impact cones intentionally use declaration edges, not coarse module import
  fan-out, when schema 1.1 decl edges are present.
- Fixture is **not** Mathlib-scale; multi-module stress is still a small closed
  package without external dependencies.
