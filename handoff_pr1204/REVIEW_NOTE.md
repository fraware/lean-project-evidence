## Suggested maintainer review for leanSpec PR #1204

<!-- fraware-xmss-atomic-review-v1-e8f9c29 -->

I reproduced a concurrency limitation in the current `SigningProtection.reserve` implementation at commit `e8f9c29da3c2b725b988ed85dac8dce3d89d0012`. The application checks `last_signed_slot` before entering its database transaction; `put_last_signed_slot` then uses an unconditional `INSERT OR REPLACE`.

With two SQLite connections operating on the same file, a forced schedule permits two calls to reserve the same validator/role/slot and both to return successfully. Another forced schedule permits a delayed slot-5 write to overwrite a committed slot-8 high-water mark.

These limitations arise under concurrent writers. The PR currently **documents exclusive key ownership and a single-writer node model**. I am not claiming those tests demonstrate an issue in that supported operating configuration.

I prepared a narrow, source-pinned improvement that makes the database operation one conditional `INSERT ... ON CONFLICT ... DO UPDATE ... WHERE last_signed_slot < excluded.last_signed_slot` statement and checks its affected-row count. The claim commits before the XMSS signature. This also removes the old unrestricted writer from the database protocol so other callers do not accidentally bypass the invariant. The candidate includes three native tests: same-slot concurrent claims, refusal of a lower-slot write, and independence of proposal versus attestation keys.

- [Four-file diff stacked on your exact PR head](https://github.com/fraware/lean-project-evidence/blob/research/ethereum-xmss-pr1204-atomic-handoff-20261012/handoff_pr1204/pr1204-atomic-reservation.patch)
- [Patch application and exact Git blob witness](https://github.com/fraware/lean-project-evidence/actions/runs/38319568933): passed
- [Lean 4 reservation model and SQLite schedule tests](https://github.com/fraware/lean-project-evidence/actions/runs/38317050285): completed successfully; this abstract model does not certify the Python/SQLite implementation.
- [Exact-PR adversarial reproducer](https://github.com/fraware/lean-project-evidence/actions/runs/38317231036): two schedule tests passed, illustrating the pre-correction issue
- [Strict candidate native CI](https://github.com/fraware/lean-project-evidence/actions/runs/38319468627): **passed**; Ruff lint/format, whole-project `ty check`, **69 focused tests**, and **2,964 standard tests** at **92% coverage**. This run used the committed candidate with no runtime formatter.

This proposed fix only strengthens serialization for **one shared SQLite file**. It does not coordinate independent replicas, reverse an already rolled-back backup, or bind reservations to the underlying cryptographic secret if logical keys alias. Those are separate security-design obligations. I would appreciate your view on whether multi-process shared-file safety is within this PR's intended scope and whether the atomic writer is a useful defense-in-depth improvement.
