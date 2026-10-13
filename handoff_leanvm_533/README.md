# leanVM PR #533: checked replacement for `Encoding.fold12`

**Parent:** [leanEthereum/leanVM PR #533](https://github.com/leanEthereum/leanVM/pull/533) at `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.

**Exact original Git blob:** `4853d8a398a1ff2762a71473c17c17e175f80b73`  
**Exact candidate Git blob:** `3f135ec7d108a821371f3db4b8e63c339665d823`  
**Evidence run:** [GitHub Actions #38477725808](https://github.com/fraware/lean-project-evidence/actions/runs/38477725808) (green; 1,713 Lean build jobs).

The only change replaces the admitted body of
`leanxmss.Proofs.Encoding.fold12` with a proof by staged base-4096 division
and bounded remainders. The theorem statement and all other file content
remain byte-for-byte unchanged.

### What is proved

`lake env lean ProofCandidateAxioms.lean` printed

```text
'leanxmss.Proofs.Encoding.fold12' depends on axioms: [propext, Classical.choice, Quot.sound]
```

No `sorryAx` occurs in this theorem's axiom closure. The upstream
`verify_spec` theorem **still** has `sorryAx` because `fold6` and
`encode_spec` are not completed in this handoff. No full guest-to-VM
semantic correspondence is asserted.

### Apply with source identity check

```bash
git clone https://github.com/leanEthereum/leanVM.git
cd leanVM
git fetch origin pull/533/head
git checkout --detach 4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d
test "$(git hash-object verification/leanxmss/LeanxmssProofs/Encoding.lean)" = 4853d8a398a1ff2762a71473c17c17e175f80b73
curl -fsSLo /tmp/fold12.patch https://raw.githubusercontent.com/fraware/lean-project-evidence/research/leanvm-pr533-fold12-handoff-20261013/handoff_leanvm_533/fold12.patch
git apply --check /tmp/fold12.patch
git apply /tmp/fold12.patch
test "$(git hash-object verification/leanxmss/LeanxmssProofs/Encoding.lean)" = 3f135ec7d108a821371f3db4b8e63c339665d823
```

Then reproduce `lake exe cache get && lake build` from
`verification/leanxmss`, and print the axioms of `fold12`.

### Publication status

An attempt to post the result directly on PR #533 failed with GitHub API
HTTP 403 (`Resource not accessible by integration`). No upstream comment,
review, PR, or merge was created.

The patch is available for the PR author to incorporate, subject to the
upstream architecture and review decision. It does not modify the upstream
implementation.
