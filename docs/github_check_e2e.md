# GitHub Check E2E (operator runbook)

Live `gh api` Check POST is **opt-in**. Default CI and local pytest keep the
mocked / dry-run path.

## Prerequisites

1. `gh` authenticated (`gh auth status`).
2. A throwaway repository you own (or a branch with Checks write permission).
3. A real commit SHA on that repo (never `mock-sha`).

## Run

```bash
export LPE_GH_CHECK_E2E=1
export LPE_GH_CHECK_REPO=owner/throwaway-repo
export LPE_GH_CHECK_SHA=$(gh api repos/owner/throwaway-repo/commits --jq '.[0].sha')
pytest -q tests/integration/test_github_check_e2e.py
```

Or via CLI (dry-run first):

```bash
lpe github submit-check PACKET.json --repo owner/throwaway-repo
lpe github submit-check PACKET.json --repo owner/throwaway-repo --post
```

## CI policy

Default `ci.yml` does **not** set `LPE_GH_CHECK_E2E`. Mock unit tests in
`tests/unit/test_github_submit.py` remain the merge gate.
