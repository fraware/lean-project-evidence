# Official technical source baseline

The engineering team should verify external behavior against primary documentation before changing integrations.

## Lean installation and toolchains

- Lean installation: `https://lean-lang.org/install/`
- Elan version manager: `https://github.com/leanprover/elan`
- Lean repository development guidance: `https://github.com/leanprover/lean4/blob/master/doc/dev/index.md`

The target repository's `lean-toolchain` file is authoritative for exact-environment execution.

## Lean CI

- Official Lean GitHub Action: `https://github.com/leanprover/lean-action`

The scaffold uses `leanprover/lean-action@v1` only as an integration template. The core repository CI is Python-first until a versioned Lean adapter exists.

## Mathlib

- Mathlib repository: `https://github.com/leanprover-community/mathlib4`
- Mathlib documentation and community guidance: `https://leanprover-community.github.io/`

## Schemas

- JSON Schema Draft 2020-12: `https://json-schema.org/draft/2020-12`

## Source policy

- Pin material production integrations.
- Record external tool versions in evidence provenance.
- Revalidate behavior after upstream upgrades.
- Keep compatibility tests for every supported Lean adapter protocol version.
