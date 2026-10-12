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
