# Lean Ethereum — upstream delivery gate (2026-10-15)

## Governing outcome

Deliver one useful, externally reviewed contribution in the Ethereum cryptography / verification critical path. This branch is a **delivery package**, not a new proof project. It contains exact, unchanged artifacts from previously source-pinned successful CI runs, including two independent maintainer-facing notes. Do not claim an upstream contribution is submitted, accepted, or merged until the upstream PR records that event.

## Priority 1 — leanVM #533: minimal Lean proof contribution

**Parent:** [leanEthereum/leanVM #533](https://github.com/leanEthereum/leanVM/pull/533), author `kevaundray`, branch `kw/leanxmss-aeneas`, HEAD `4a5a6cf008fc724ad91f9c234d5a3f3d6a7bdc0d` (rechecked October 15).

**Precisely scoped change:** `handoff_leanvm_533/both-folds.patch` changes the bodies of exactly the previously admitted `leanxmss.Proofs.Encoding.fold6` and `fold12` declarations in `verification/leanxmss/LeanxmssProofs/Encoding.lean`. Statements and other source are unchanged. Independent same-build proof and `#print axioms` audit: [run #38479742934](https://github.com/fraware/lean-project-evidence/actions/runs/38479742934), passed. Independent exact-parent patch reconstruction: [run #38480309105](https://github.com/fraware/lean-project-evidence/actions/runs/38480309105), passed.

The replacement source Git blob is `41b62c33554ff74b96c129e21cc7fd11d225179c`. Each new lemma depends only on `propext`, `Classical.choice`, and `Quot.sound`. **`encode_spec` and dependent guest claims are still admitted**. No binary or Charon/Aeneas translation correctness is claimed.

**First external action:** publish `handoff_leanvm_533/REVIEW_NOTE.md` to the *existing* #533 PR, asking whether the maintainer wants the two exact lemmas as an amendment. This avoids a competing parent PR based on a draft architectural branch. Once the maintainer confirms integration, apply the exact patch to their requested branch or prepare a small stacked contribution. Further `Digits.sum` and digest proofs are follow-on options, not blockers to this contact.

## Priority 2 — leanSpec #1204: atomic reservation defense in depth

**Parent:** [leanEthereum/leanSpec #1204](https://github.com/leanEthereum/leanSpec/pull/1204), author `adust09`, branch `feat/durable-signing-protection`, HEAD `e8f9c29da3c2b725b988ed85dac8dce3d89d0012` (rechecked October 15). The PR has merge conflicts with `main`.

**Precisely scoped contribution:** `handoff_pr1204/pr1204-atomic-reservation.patch` is the four-file source-pinned conditional SQLite high-water reservation amendment. It prevents two concurrent claimers sharing one SQLite file from both obtaining the same logical duty or overwriting a higher signed slot. Native CI [#38319468627](https://github.com/fraware/lean-project-evidence/actions/runs/38319468627) passed Ruff, typing, 69 focused tests, and 2,964 standard tests; independent reproduction [#38319568933](https://github.com/fraware/lean-project-evidence/actions/runs/38319568933) passed. This is an older but directly reviewed *minimal four-file* patch; later eight-file identity/durability experiments have different evidence and are intentionally excluded from this delivery package.

**Security boundary:** the parent PR assumes exclusive signing-key ownership and a single-writer model. Concurrency findings require a shared SQLite database and do **not** demonstrate an exploit in that documented supported configuration. The patch does not address independent hosts, rollback, duplicated underlying secret material, or hardware guarantees. Read `handoff_pr1204/THREAT_MODEL.md`, `CLAIMS.md`, and the full `REVIEW_NOTE.md` before proposing adoption.

**Second external action:** ask `adust09` whether multi-process shared-file safety is in scope; if yes, deliver the tested four-file patch through the original author’s desired integration route. Avoid a competing parent PR or urgent security claims.

## Single operator entry point

The package provides `delivery/ship.sh`. It verifies **all 11 pinned artifact blobs** and rechecks the active contributor account and both upstream PR heads.

```bash
git clone --branch delivery/lean-ethereum-upstream-20261015 --single-branch \
  https://github.com/fraware/lean-project-evidence.git
cd lean-project-evidence
bash delivery/ship.sh status
```

`status` makes no GitHub writes. It fails if the local files, GitHub account, PR heads, or PR visibility are inconsistent.

Only following independent human inspection and the explicit decision to contact the maintainer:

```bash
bash delivery/ship.sh publish leanvm
# separately, if desired:
bash delivery/ship.sh publish signing
```

Each command operates on **one** named upstream PR. The underlying scripts independently guard author identity, pinned PR head, and comment duplication. The signing script publishes on invocation; **never call it as a dry run**. The wrapper is the safe default.

If the connector or local GitHub identity cannot write upstream PR comments, use a GitHub session that is permitted to comment there; do not weaken the pinned checks or post unverified claims.

## Decision log and time budget

- **Now:** send the two scoped maintainer notes, with leanVM first. No new isolated proof branches until an owner replies or a finite contact window expires.
- **Within 7 days of publication:** record maintainer feedback, path choice (#533 Rust/Aeneas versus #595/#610 Clean), and integration instructions. A lack of response triggers one respectful follow-up or a targeted alternative contribution, not uncontrolled additional research.
- **Next engineering gate:** a maintainer-reviewed diff or a documented reason to pivot.
- **After adoption or confirmed proof scope:** finish the actual `encode_spec`/execution correspondence and audit source-to-artifact trust assumptions.
- **2027 research program:** prove meaningful evidence preservation/composition and validate in two independent systems before asserting portability or scientific novelty.

**Outcome metric:** reviewed or accepted upstream security/verification improvement, not branch count, proof count, or locally green CI alone.

## Recorded facts versus open items

Confirmed: the two upstream PRs are open at the pinned heads; the original patch handoffs and cited runs exist; the connected GitHub integration has read access to upstream repositories but lacks push access. Earlier attempts to post through the connected integration returned HTTP 403. The local authenticated `gh` route has not been executed here.

Open: upstream publication, maintainer response, patch integration, PR acceptance, operational deployment applicability, full `encode_spec` proof, and any general cross-system research claim.
