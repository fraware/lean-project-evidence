## Summary

This is a **stacked correction to `adust09/leanSpec:feat/durable-signing-protection`**, the exact head of upstream [leanEthereum/leanSpec PR #1204](https://github.com/leanEthereum/leanSpec/pull/1204), at commit `e8f9c29da3c2b725b988ed85dac8dce3d89d0012`.

It combines two complementary changes to the validator's XMSS signing path:

1. **Atomic persistent reservation:** replace read/check/`INSERT OR REPLACE` with a conditional, monotone SQLite UPSERT and a checked affected-row result; remove the unrestricted writer from the storage interface.
2. **Signing preconditions:** check local-versus-consensus public-key binding and block-proof participants before signing, reject invalid/out-of-window or nonadvancing key preparation, preserve the proposer index, and restore block-production state only on known pre-signature refusals.

The reservation is committed **after successful preparation and before any XMSS signature is requested**. The change preserves the duty-skipping behavior for duplicate slot reservations.

## Independent validation

- [Combined six-file native CI run #38340641997](https://github.com/fraware/lean-project-evidence/actions/runs/38340641997): Ruff check and format, whole-project `ty check`, **72 focused tests**, **2,967 standard tests**, and **92% reported coverage** passed.
- [Exact six-file patch witness #38341089422](https://github.com/fraware/lean-project-evidence/actions/runs/38341089422): source commit and Git blob identity checks, clean patch application, exact output blob verification and Python compilation passed.
- [Original reservation race reproduced in the actual PR method](https://github.com/fraware/lean-project-evidence/actions/runs/38317231036) with an instrumented two-connection SQLite adapter (two tests).
- [Machine-checked reservation model and SQLite adversarial tests](https://github.com/fraware/lean-project-evidence/actions/runs/38317050285): separate proof/model evidence, not an implementation proof.

[Source-pinned patch](https://github.com/fraware/lean-project-evidence/blob/research/ethereum-xmss-composed-handoff-20261012/handoff_composed/xmss-composed.patch) · [Security contract and limitations](https://github.com/fraware/lean-project-evidence/blob/research/ethereum-xmss-composed-handoff-20261012/handoff_composed/SECURITY_CONTRACT.md)

## Scope limitations

The invariant concerns atomic, monotonically increasing claims per logical `(validator_index, key_role)` in **one shared SQLite database**. It does not coordinate independent database files, establish key uniqueness across role aliases, protect an overwritten or rolled-back backup, or prove the executable cryptography corresponds to a Lean specification. Failures occurring after signing must not be interpreted as evidence that the slot is unspent.

PR #1204 documents an exclusive-key / single-writer deployment model. The concurrency correction adds defense-in-depth for two SQLite connections sharing a file; it does not imply a demonstrated exploit within that documented operating model.

This is a review of a change stacked on PR #1204's current head, not a claim that upstream main contains PR #1204 or that the combined change has been merged.