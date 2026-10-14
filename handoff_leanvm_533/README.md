# Source-pinned Aeneas checked-addition handoff for leanXMSS

Upstream proof baseline: `leanEthereum/leanVM` PR #533,
`4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.
The unchanged translated Rust guest lives at `Leanxmss/Funs.lean`.

This handoff comprises:

1. The existing [kernel-checked SWAR42 arithmetic and four range
   invariants](https://github.com/fraware/lean-project-evidence/actions/runs/38519333671)
   applied to the original `LeanxmssProofs/Encoding.lean`, with
   candidate Git blob `7460dd8c3920c39e2d599ba36d16b77c3d444d1e`.
2. A new independent `GuestAddPrefixes.lean` Lean module (Git blob
   `68dc7237711152dd54c1257fab33c0e0a361de04`). It uses the Aeneas library's
   `UScalar.add_spec` directly to prove successful checked arithmetic
   for the first, second and third guest additions and exact mathematical
   output values, assuming their source-stage operand correspondences.

[Full exact-source kernel and axiom acceptance](https://github.com/fraware/lean-project-evidence/actions/runs/38521837459)
passed all 1,713 project build jobs. Its `#print axioms` output for
`swar42_guest_first_add_spec`, `swar42_guest_second_add_spec`,
`swar42_guest_third_add_spec`, and the initial-prefix bounds was
`[propext, Classical.choice, Quot.sound]`; no `sorryAx`.

### What these verified theorems do not establish

The full translated `Digits.sum` function still needs the LOW6
checked addition, three later checked additions, exact value propagation
from the source's indexing/shifts/masks, and the final 42-digit equality.
These helper theorems are **conditional on their operand-value
correspondence premises**, which must be discharged inside the actual
function's weakest-precondition proof. The complete `encode_spec`
is still admitted.

### Exact reapplication

Check out the upstream PR #533 head and, from the repository root:

```bash
git apply --check /path/to/swar42-and-range.patch
git apply /path/to/swar42-and-range.patch
test "$(git hash-object verification/leanxmss/LeanxmssProofs/Encoding.lean)" = 7460dd8c3920c39e2d599ba36d16b77c3d444d1e
cp /path/to/GuestAddPrefixes.lean verification/leanxmss/GuestAddPrefixes.lean
test "$(git hash-object verification/leanxmss/GuestAddPrefixes.lean)" = 68dc7237711152dd54c1257fab33c0e0a361de04
cd verification/leanxmss
lake exe cache get
lake build
lake env lean -o .lake/build/lib/lean/GuestAddPrefixes.olean GuestAddPrefixes.lean
```

The separate handoff workflow checks application, source hashes, and
the module's syntax. The original full Lean and axiom CI is the
independent formal acceptance evidence.

**Upstream status:** No comment, PR, or merge has been posted or
accepted via the connected GitHub integration.
