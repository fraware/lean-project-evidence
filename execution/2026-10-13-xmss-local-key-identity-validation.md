# XMSS locally declared public-key uniqueness: independently checked

Date: 2026-10-13  
Source: `leanEthereum/leanSpec` PR #1204,
`e8f9c29da3c2b725b988ed85dac8dce3d89d0012`.

## Source-grounded risk

The current signing ledger distinguishes `(validator_index, key_role)`,
while the upstream key registry from YAML checks equality of declared
attestation/proposal public keys **within** each validator entry only.

Two **locally controlled** validator entries can declare the same XMSS
public key in different ledger identities. The experimental amendment
checks all declared public keys assigned to the current node before
any secret key decoding, and rejects a duplicate across any of the four
cross-validator attestation/proposal role combinations.

The source patch is strictly two files:
`src/lean_spec/node/validator/registry.py` and
`tests/node/validator/test_registry.py`.

| Source artifact | Git blob SHA |
|---|---|
| Original registry | `c3336437260d35a1c41c4589734e73625191b74f` |
| Amended registry | `ba46ce42f0c5457a4862d331cc67948a30f10196` |
| Original tests | `5ac8e77b2a6be6b2579ae51064f51bac9c8ec5de` |
| Amended tests | `b3c53b66294ee8801f2871a6ed81c29ec7d112c6` |

## Independent verification

[Standalone exact-source CI #38485502716](https://github.com/fraware/lean-project-evidence/actions/runs/38485502716)
was **green**, with original and result blob identity checks, Ruff lint,
exact formatting, whole-project `ty`, and **34 upstream native registry
tests passing**.

[Two-file source-pinned handoff](https://github.com/fraware/lean-project-evidence/tree/research/ethereum-xmss-local-key-identity-handoff-20261013/handoff_xmss_key_identity).

The [larger signing+registry candidate suite #38484185368](https://github.com/fraware/lean-project-evidence/actions/runs/38484185368)
is **a separate run**, whose final conclusion must be observed independently.
It is not implied by the standalone result.

## Limits and external decisions

This guards duplicate **declared** public keys in one `from_yaml`
invocation and leaves keys belonging exclusively to other nodes untouched.
It does not:
- establish that decoded private keys correspond to the manifest declarations;
- detect cloned secret material across hosts or databases;
- validate manual `ValidatorRegistry.add` operations;
- prevent recovery rollback to older signing state;
- establish a distributed key custody invariant.

Whether upstream maintainers want this check in the manifest loader, a
broader key-custody module, or a documented operational assumption remains
undecided. The candidate has not been merged or externally reviewed.

A new test case demonstrating an unsupported declared-key configuration
must not be presented as a demonstrated production exploit.
