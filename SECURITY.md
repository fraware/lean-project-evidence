# Security policy

Do not report exploitable execution or secret-handling vulnerabilities in a public issue.

Until a private reporting address is configured, contact the repository owner directly.

Generated Lean repositories and patches must be treated as untrusted code. Development shortcuts that expose credentials or remove execution isolation are release blockers.

## Host execution (AUDIT-001 / AUDIT-019)

`lpe evidence compile` prefers a Docker network-none sandbox for builds.

- Default: refuse host subprocess builds when Docker is unavailable.
- `network_policy: deny` (contract default) **requires** Docker `--network=none`. Host subprocess (`--insecure-host-exec`) is refused under deny because it cannot enforce network isolation.
- Opt-in host builds: set `network_policy: allow` **and** pass `--insecure-host-exec` (trusted machines only).
- Prefer `--sandbox` (default). `--no-sandbox` also requires `--insecure-host-exec` and is incompatible with `network_policy: deny`.

## Docker sandbox (AUDIT-006)

- Default image: `ubuntu:22.04` (generic; does **not** include Lean/Lake).
- Override with `LPE_DOCKER_IMAGE` for Lean-capable builds:
  - **Recommended:** local image `lpe-lean:4.14` from `docker/lpe-lean/` (elan +
    Lean `v4.14.0`, matching the fixture `lean-toolchain`). Build with
    `scripts/build_lean_docker_image.ps1` (Windows) or
    `scripts/build_lean_docker_image.sh` (Linux/macOS). First build is heavy;
    pytest only inspects an existing image tag and never rebuilds.
  - Community image `leanprovercommunity/lean4` (**stale** as of 2024–2025; pin a
    digest and verify before relying on it — there is no maintained official
    `leanprover/lean4` Docker Hub image)
- On Windows Docker Desktop, host `PATH`/`HOME` are rewritten to Linux container
  defaults (including `/root/.elan/bin`) so Lake is reachable inside the image.
- Memory limit: `LPE_DOCKER_MEMORY` (default `2g`). Hardening: `--cap-drop=ALL`, `--security-opt=no-new-privileges`, `--pids-limit=256`, tmpfs `/tmp`.
- Mount: repository mounted **read-write** at `/work` so Lake can write `.lake/` artifacts. Prefer `--worktree` (CLI default) so the live checkout is not mutated. Set `LPE_DOCKER_READONLY=1` for `:ro` (Lean/Lake builds that need write will fail closed with a clear hint — never claim isolation PASS for a build that could not write artifacts).
- Isolation finding `execution.isolation` is **PASS** only when a sandboxed, network-isolated build actually ran. `--skip-build` yields `NOT_APPLICABLE` (never a false PASS). Isolation PASS does **not** imply typecheck unless the image contains Lean/Lake.
- After a sandboxed build, `lake exe lpe_extract` prefers the **same** Docker
  executor in **one** `docker run` (`verify_build_and_extract` →
  `combined_build_extract` / `sandbox_invocations: 1`). Set
  `LPE_DOCKER_COMBINED_BUILD_EXTRACT=0` for sequential fallback (two containers).
  Host Lake is not required for the Docker toolchain path; sandboxed extract
  failures fail closed (UNKNOWN axioms, no host Lake fallback). Build-phase
  failure does not claim toolchain-complete extract. Host-exec
  (`--insecure-host-exec`) still extracts on the host and remains tested.

## Command allowlist (AUDIT-005)

`build_command` executables must be one of: `lake`, `lean`, `elan` (plus `.exe` on Windows). Shells and arbitrary binaries are rejected.

## Secrets (AUDIT-007 / AUDIT-008)

- Build stdout/stderr are redacted before embedding in evidence packets: GitHub PATs, Slack (`xox*` / `xapp-`), GitLab `glpat-`, npm, Stripe, OpenAI/Anthropic `sk-` shapes, Hugging Face `hf_`, AWS keys, Bearer/JWT triples, assignment shapes, and multiline PEM/OpenSSH private-key blocks. Ordinary Lean/Lake diagnostics are preserved (fail closed on secrets, avoid over-redact).
- Environment scrubbing uses the contract allowlist plus a denylist (`*_TOKEN`, `*_SECRET`, `*_PASSWORD`, `GITHUB_*`, `AWS_*`, and `CI`). `CI` is not in the default allowlist.

## Actions pinning (AUDIT-024)

CI workflows pin Actions by commit SHA. Dependabot (`pip` + `github-actions`) proposes updates weekly; review SHA/tag alignment on each Actions PR before merge.

## Review authority (AUDIT-002 / AUDIT-009)

Reviewer roles in decision JSON are not trusted. Authority comes only from `review.yaml`. R3/R4 `ACCEPT` cannot be recorded via `lpe review record` until a multi-authority protocol exists (ADR 0003).

## Candidate metadata (AUDIT-004 / AUDIT-015)

When compiling against a git project toplevel (or when `head_commit` is set), base/head revisions are verified and changed-path / declaration metadata is taken from git. Self-declared `public`, `signature_changed`, and `foundational` fields are ignored when git classification is available. Null/fake object ids (all zeros) are rejected.

## Placeholder and axiom gates (AUDIT-016 / AUDIT-003)

Placeholder scans cover patch text and changed `.lean` files on disk. Empty `patch_text` does not auto-pass if applied sources contain `sorry`/`admit`. The regex-stub axiom extractor never yields `lean.prohibited_axioms` PASS on incomplete extraction (empty `axioms_used` → UNKNOWN). Prohibited axioms found by the stub still FAIL.

## Hard gate honesty (AUDIT-020)

`hard_gate_passed` is true only when every hard-relevant check is PASS. `UNKNOWN` on `lean.prohibited_axioms` (or other hard checks) yields `hard_gate_passed=false` with ESCALATE — it must not be read as axiom-safe.

## Lean extraction (AUDIT-011 / AUDIT-012)

Default path is `extractor: "regex-stub"` (AST-lite). Toolchain completeness is claimed only when:

1. `.lpe/lean-extraction.json` (or `.lean-project-contract/lean-extraction.json`) is ingested with `extractor: lean.toolchain` and `complete: true`, or
2. Lake/Lean is available (host **or** Lean-capable Docker image) and the project declares `lake exe lpe_extract`, which LPE may invoke to emit that JSON (see `tests/fixtures/lean_project/` and `src/lpe/lean/toolchain.py`). On the Docker path, build+extract prefer a single sandbox invocation.

Without Lean installed (and without a Lean Docker image / committed JSON), extraction stays `regex-stub` (axiom/impact findings UNKNOWN, never fake PASS). Dependency edges are `dependee → depender` so impact cones are downstream dependents, not upstream imports.
