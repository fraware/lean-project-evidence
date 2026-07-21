# Lean extract defaults (CLOSURE-006 / CLOSURE-008)

## Generic extract

When Lake is available and the project does **not** declare an `lpe_extract`
target, the adaptive extractor **prefers the injected generic extractor** by
default (spec §9.1–9.3).

| Control | Effect |
| --- | --- |
| unset (auto) | Prefer generic when no `lpe_extract` / schema≥1.1 complete artifact policy requires the project toolchain helper |
| `LPE_PREFER_GENERIC_EXTRACT=1` | Force prefer generic even if `lpe_extract` exists |
| `LPE_PREFER_GENERIC_EXTRACT=0` | Disable generic preference; Lake `lpe_extract` / regex-stub paths only |
| `lpe evidence compile --prefer-generic-extract` | Sets env for this invocation |
| `lpe evidence compile --no-prefer-generic-extract` | Forces off for this invocation |

Unsupported toolchains still fail closed with `UNSUPPORTED_TOOLCHAIN` and must
never silent-PASS via regex-stub elaborator claims.

## Paired base/candidate extract

Paired extract always runs in **dry-run fingerprint mode** during evidence
compile (stable base/head tree + toolchain digests). **Live** elaborator-backed
paired Lake extract (2× cost) remains **opt-in**:

| Control | Effect |
| --- | --- |
| unset / `LPE_PAIRED_EXTRACT=0` | Dry-run fingerprints only (default; CI-safe) |
| `LPE_PAIRED_EXTRACT=1` | Live base + candidate generic extract |
| `lpe evidence compile --paired-extract` | Sets `LPE_PAIRED_EXTRACT=1` for this invocation |

### Why live paired stays opt-in

Live paired extract doubles Lake wall time and requires a working Lean toolchain
or `lpe-lean` image. Default CI and `skip_build` paths must remain usable without
that cost. Declaration-diff risk rewrite uses live paired results only when both
sides load an elaborator environment successfully; otherwise lexical risk
classification remains fail-closed (never invents elaborator PASS).

This is an intentional product default, not a stub: dry-run proves identity
wiring; live mode is available when operators need elaborator-backed diffs.
