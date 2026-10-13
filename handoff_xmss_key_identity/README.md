# Scoped XMSS declared-public-key uniqueness (review candidate)

Pinned upstream source: `leanEthereum/leanSpec` PR #1204
at `e8f9c29da3c2b725b988ed85dac8dce3d89d0012`.

This is an **independent two-file patch** for the validator manifest loader.
It detects public keys declared under more than one locally controlled
`(validator_index, role)` identity before loading any secret file. The
four regression cases cover all cross-validator role combinations; another
node's manifest entries stay outside this local loader's scope.

The change does not update slot reservation storage or signing behavior.
It is intended as a separate reviewable hardening proposal, dependent on
maintainer agreement about policy. It is **not** upstream-approved.

| Path | Original Git blob | Candidate Git blob |
|---|---|---|
| `src/lean_spec/node/validator/registry.py` | `c3336437260d35a1c41c4589734e73625191b74f` | `ba46ce42f0c5457a4862d331cc67948a30f10196` |
| `tests/node/validator/test_registry.py` | `5ac8e77b2a6be6b2579ae51064f51bac9c8ec5de` | `b3c53b66294ee8801f2871a6ed81c29ec7d112c6` |

### Reproduction

Clone leanSpec and detach at the exact PR #1204 commit, then:

```bash
git apply --check local-public-key-uniqueness.patch
git apply local-public-key-uniqueness.patch
git diff --check
uv sync --frozen --group test --group lint
uv run --no-sync --group lint ruff check --no-fix src/lean_spec/node/validator/registry.py tests/node/validator/test_registry.py
uv run --no-sync --group lint ruff format --check src/lean_spec/node/validator/registry.py tests/node/validator/test_registry.py
uv run --no-sync --group test pytest tests/node/validator/test_registry.py -q --no-cov
```

### Exact guarantee boundary

The check only compares public-key **declarations** in one local YAML
loader invocation. It cannot prove correspondence between the declared
public key and the decoded secret, prevent copying secrets to another node,
control `ValidatorRegistry.add` calls, or prevent database rollback.
It should not be presented as complete XMSS key-custody enforcement.

The [combined signer-and-registry run](https://github.com/fraware/lean-project-evidence/actions/runs/38484185368)
is a separate gate; only its final result counts. No upstream PR was
created by preparing this handoff.
