# leanSpec XMSS signing precondition correction

Source baseline: `leanEthereum/leanSpec@0b7d33ecbc9ee2435759c92de4da4d08d7faf1c8`.

This directory carries an exact unified diff for the two files in the candidate tested in the hosted GitHub Actions validator job. It is prepared separately from the persistent reservation change in upstream PR #1204.

## Apply in a clean leanSpec checkout

```sh
git checkout --detach 0b7d33ecbc9ee2435759c92de4da4d08d7faf1c8
git apply --check leanSpec-xmss-preconditions.patch
git apply leanSpec-xmss-preconditions.patch
uv sync --frozen --group lint --group test
uv run --no-sync --group lint ruff check --no-fix src/lean_spec/node/validator/service.py tests/node/validator/test_service.py
uv run --no-sync --group lint ruff format --check src/lean_spec/node/validator/service.py tests/node/validator/test_service.py
uv run --no-sync --group lint ty check
uv run --no-sync --group test pytest tests/node/validator/test_service.py -q --no-cov
```

The patch is source-revision-specific and is not a substitute for durable XMSS slot reservations. A hosted full-suite result and multi-node interop evidence are tracked in the separate validation workflow. The original repository has not received a PR.

## Exact source identity

- `src/lean_spec/node/validator/service.py`: original Git blob `3b85c005d49c786f23f49360e2e1117d93b9fa91`, proposed blob `b5b2869c51740baf78de5a829ea36597dc480fec`; 8 hunks, +128/-45 lines.
- `tests/node/validator/test_service.py`: original Git blob `3bbdd2070fcb7188ca1068e87db5a250752653ba`, proposed blob `a055b66048f20d15c6c58c9ddc5954537e76c0b2`; 3 hunks, +63/-0 lines.

## Hosted validation evidence (12 October 2026)

- [Strict validator gate, run 38310950336](https://github.com/fraware/lean-project-evidence/actions/runs/38310950336): Ruff lint, Ruff format, whole-project `ty check`, and **52/52 validator tests passed**.
- [Repository-wide integration gate, run 38311670261](https://github.com/fraware/lean-project-evidence/actions/runs/38311670261): Ruff and ty passed; **52 validator tests**, **2,130 standard pytest tests**, **90.66% coverage** (at least 90% required), and **1 multi-node interoperability test** all passed. Standard pytest runs with the upstream `pyproject.toml` exclusions, so its test count does not include the separately executed interop test or excluded fixture-generation trees.
- [Patch reproduction gate, run 38313259507](https://github.com/fraware/lean-project-evidence/actions/runs/38313259507): real fresh leanSpec clone at the pinned SHA; `git apply --check` and `git apply` passed, both resulting Git blob IDs matched the files in validated CI, `git diff --check` and Python compilation passed.

A separate independent interoperability run is [run 38313058359](https://github.com/fraware/lean-project-evidence/actions/runs/38313058359). Its status is independent of the completed full integration gate above.

## Scope and limits

The change is a validator execution-preconditions patch: bounded XMSS preparation, proposal and attestation public-key binding checks, validation before proposal signing, proposer/participant identity preservation, and pre-signature-only store rollback. The candidate contains three added regression tests in the existing validator test module.

It **does not implement durable, cross-restart XMSS one-time-key reservation** or prove cryptographic state correspondence. See [leanSpec issue #1203](https://github.com/leanEthereum/leanSpec/issues/1203) and [PR #1204](https://github.com/leanEthereum/leanSpec/pull/1204). Distinct storage safety, concurrency, and recovery obligations remain. This is a pinned historical baseline and needs rebasing if upstream main advances.

No upstream leanSpec branch or PR was created. A fork with write access is needed to submit the patch for maintainer review. Independent hosted CI in another writable repository does not equal upstream CI or maintainer approval.


## One-command publication using an authenticated GitHub account

Upstream GitHub API writes from this connected integration return HTTP 403, including branch creation and PR review comments. The supported publication route is the authenticated GitHub CLI on your own machine. The publication helper verifies that the active account is `fraware`, creates the actual `leanEthereum/leanSpec` fork if missing, checks its parent relationship, downloads the immutable tested patch, confirms exact output Git blobs, pushes a separate branch, and opens the pull request against upstream `main`.

Prerequisites: `gh`, `git` and `curl` installed, `gh auth login` completed as `fraware`, and Git commit author information configured.

```bash
curl -fsSLo publish_upstream.sh https://raw.githubusercontent.com/fraware/lean-project-evidence/0f9ac08259db34e2a5c2aa46d1e12ba039f1dc11/handoff/publish_upstream.sh
bash -n publish_upstream.sh
bash publish_upstream.sh
```

Inspect [the publication helper](./publish_upstream.sh) and [the proposed PR description](./PR_BODY.md) before executing. The helper performs public GitHub writes, creates a temporary standalone clone, and does not overwrite an existing upstream branch. It fails closed if the account, fork parent, pinned source, patch hash, or expected file identity is wrong. Local helper syntax and publication guards are exercised in the [patch witness workflow](../.github/workflows/leanspec-xmss-patch-witness.yml); the actual fork and PR operation must run under the account's authentication, which is not available to this integration.

If using the web interface, [create the fork](https://github.com/leanEthereum/leanSpec/fork) under the `fraware` namespace first. The helper accepts an existing correctly related fork, so the remaining steps stay automatic.
