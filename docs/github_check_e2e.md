# GitHub Check E2E (operator runbook)

Live `gh api` Check POST is **opt-in**. Default CI (`python` job in
`.github/workflows/ci.yml`) and local pytest keep the mocked / dry-run path.
Missing secrets never fail the default merge gate.

## Fail-closed required check (ADR 0003)

`lpe github submit-check` maps recommendation **ESCALATE** to Check conclusion
**`failure`** by default (`--escalate-as failure`). That is intentional for
branch protection: a required Check named `lean-project-evidence` blocks merge
until a human resolves the escalate path.

This aligns with [ADR 0003](adr/0003-human-authority.md): high-risk semantics
stay under human authority. Do **not** treat a green Check as R3/R4 ACCEPT —
Check output is evidence signaling only; ledger `lpe review record` remains the
authority path. Override with `--escalate-as neutral` only when the Check is
informational (not required).

## Prerequisites

1. `gh` on PATH and authenticated (`gh auth status`).
2. Token / `gh` session with **`checks:write`** on the target repo.
3. A **throwaway** repository (never point E2E at a production protected main
   until you understand branch protection below).
4. A real commit SHA on that repo (never `mock-sha` or `unavailable-sha`).

## Throwaway repo setup

```bash
# Create an empty public throwaway (or use an existing sandbox repo)
gh repo create YOUR_ORG/lpe-check-sandbox --public --clone
cd lpe-check-sandbox
echo "# LPE Check sandbox" > README.md
git add README.md && git commit -m "chore: seed commit for check-runs" && git push -u origin HEAD

export LPE_GH_CHECK_REPO=YOUR_ORG/lpe-check-sandbox
export LPE_GH_CHECK_SHA=$(gh api "repos/${LPE_GH_CHECK_REPO}/commits" --jq '.[0].sha')
```

Optional: open a throwaway PR and use that head SHA so the Check appears on the
PR Checks tab.

## CLI (dry-run first)

Produce or reuse an evidence packet JSON, then:

```bash
# Prints exact gh api argv, command_preview, and JSON payload — no network
lpe github submit-check PACKET.json --repo "$LPE_GH_CHECK_REPO"

# Live POST (refuses sentinel SHAs; clear errors if gh missing / auth fails)
lpe github submit-check PACKET.json --repo "$LPE_GH_CHECK_REPO" --post
```

Dry-run output includes:

- `argv` — exact argument vector passed to `gh`
- `command_preview` — shell-readable form (`… --input -` with JSON on stdin)
- `payload` — Checks API body (`name`, `head_sha`, `conclusion`, `output`, …)
- `dry_run: true` / `posted: false`

## Pytest E2E (env-gated)

```bash
export LPE_GH_CHECK_E2E=1
export LPE_GH_CHECK_REPO=YOUR_ORG/lpe-check-sandbox
export LPE_GH_CHECK_SHA=$(gh api "repos/${LPE_GH_CHECK_REPO}/commits" --jq '.[0].sha')
pytest -q tests/integration/test_github_check_e2e.py
```

Without `LPE_GH_CHECK_E2E=1`, the live test is **skipped** (exit 0).

## Branch protection tip

On the throwaway (or later on a real protected branch):

1. Settings → Branches → Branch protection rule.
2. Enable **Require status checks to pass before merging**.
3. Add required check name: **`lean-project-evidence`** (must match payload
   `name` from `packet_to_github_check`).
4. Push a commit whose packet recommends **ESCALATE** with default
   `--escalate-as failure` → required Check fails → merge blocked.
5. Re-run with ACCEPT / success conclusion (or remove the required Check) to
   unblock — confirming fail-closed behavior.

Do not enable this on a production default branch until operators have practiced
on the sandbox.

## Optional CI job (secrets / vars gated)

Default `python` CI **never** sets `LPE_GH_CHECK_E2E` and **never** fails for
missing GitHub Check secrets.

An optional job `github-check-e2e-optional` in `.github/workflows/ci.yml` runs
only when repository variable **`LPE_GH_CHECK_E2E=1`**. Configure:

| Kind | Name | Purpose |
| --- | --- | --- |
| Variable | `LPE_GH_CHECK_E2E` | Must be `1` to enable the optional job |
| Variable | `LPE_GH_CHECK_REPO` | `owner/throwaway-repo` |
| Variable | `LPE_GH_CHECK_SHA` | Real commit SHA (or leave empty to skip cleanly) |
| Secret | `LPE_GH_CHECK_TOKEN` or `GH_TOKEN` | PAT with `checks:write` (falls back to `github.token` for same-repo) |

If the job is enabled but repo/SHA vars are incomplete, the step **skips with
success** (prints a message; does not fail the workflow).

### Documented composite (local / reusable)

Equivalent to the optional job — paste into a workflow or run locally:

```yaml
# Composite-style steps (not a published action; copy as needed)
- uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
- uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
  with:
    python-version: "3.12"
- run: pip install -e ".[dev]"
- name: Live GitHub Check E2E
  env:
    LPE_GH_CHECK_E2E: "1"
    LPE_GH_CHECK_REPO: ${{ vars.LPE_GH_CHECK_REPO }}
    LPE_GH_CHECK_SHA: ${{ vars.LPE_GH_CHECK_SHA }}
    GH_TOKEN: ${{ secrets.LPE_GH_CHECK_TOKEN || secrets.GH_TOKEN || github.token }}
  run: |
    if [ -z "$LPE_GH_CHECK_REPO" ] || [ -z "$LPE_GH_CHECK_SHA" ]; then
      echo "LPE_GH_CHECK_REPO/SHA not set — skipping live Check E2E."
      exit 0
    fi
    pytest -q tests/integration/test_github_check_e2e.py
```

## What stays in the merge gate

Mock / dry-run unit tests in `tests/unit/test_github_submit.py` (and Check
mapping in `tests/unit/test_github_check.py`) remain the always-on gate.
