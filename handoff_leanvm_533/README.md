# PR #533: two checked local arithmetic lemmas, composed candidate

Upstream parent: `leanEthereum/leanVM@4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d`.

Original source Git blob: `4853d8a398a1ff2762a71473c17c17e175f80b73`.  
Combined candidate Git blob: `41b62c33554ff74b96c129e21cc7fd11d225179c`.

The patch replaces only the previously admitted bodies of
`leanxmss.Proofs.Encoding.fold6` and `fold12`, preserving both statements
and all other source.

Independently proven against the exact parent:
- [`fold6` axiom-clean build](https://github.com/fraware/lean-project-evidence/actions/runs/38479334042)
- [`fold12` axiom-clean build](https://github.com/fraware/lean-project-evidence/actions/runs/38477725808)

Combined same-build acceptance:
[Actions run #38479742934](https://github.com/fraware/lean-project-evidence/actions/runs/38479742934).
**Consult its final verdict**. A separately checked lemma does not substitute
for the combined build.

Apply from a checkout at the parent commit:

```bash
git apply --check both-folds.patch
git apply both-folds.patch
git hash-object verification/leanxmss/LeanxmssProofs/Encoding.lean
```

The resulting hash must be `41b62c33554ff74b96c129e21cc7fd11d225179c`.

**Residual trust:** `encode_spec` is still admitted, and verifier and main
correspondence theorems retain `sorryAx`. SDK/VM models and translation
correctness are separate premises. This patch has **not** been accepted or
merged by upstream maintainers.
