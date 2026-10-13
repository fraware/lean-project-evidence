# Scope-bounded XMSS manifest-identity hardening

**Source:** `leanEthereum/leanSpec` PR #1204 at `e8f9c29da3c2b725b988ed85dac8dce3d89d0012`.
The six previously tested candidate files are unchanged, combined with only
`src/lean_spec/node/validator/registry.py` and its native test file.

**Hypothesis:** The signing reservation ledger indexes
`(validator_index, key_role)`, while the upstream registry validates that
attestation and proposal keys differ only **within each validator**.
A manifest declaring the **same public key** under two locally controlled
validator/role combinations can bypass that manifest-level uniqueness
assumption. This experiment rejects such duplicated declared identities
before decoding any private key files.

**Scope:** One invocation of `from_yaml`, one locally controlled set,
and the **declared** public keys. This does **not** prove that loaded secret
material corresponds to a declared public key, prevent copied secrets on
another node, or enforce cross-host anti-rollback. `ValidatorRegistry.add`
permits programmatic entries, another distinct interface.
A manifest from other nodes is left untouched by the local loader.

The added parameterized test checks same-role and cross-role duplicates.
A control test confirms another node's manifest identity remains outside
this local loading check. All results require a passing native pinned CI run
before being described as verified.

This is an exploratory hardening patch, NOT an upstream-reviewed policy.
