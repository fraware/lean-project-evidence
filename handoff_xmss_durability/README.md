# Source-pinned combined XMSS signing candidate — independent reviewer handoff

This directory reconstructs the six-file candidate based on the **open**
`leanEthereum/leanSpec` PR #1204 at
`e8f9c29da3c2b725b988ed85dac8dce3d89d0012`.

The source files are pinned to evidence-repository commit
`79b27bba5154298de32681dcadcc8ec8628de54b`.
The script checks the exact six Git blob identities, `git diff --check`,
and writes a reviewable unified patch in an isolated temporary workspace.
It does not fork, push, create a pull request, or touch an existing checkout.

## Reproduce

```bash
curl -fsSLo review_candidate.sh \
  https://raw.githubusercontent.com/fraware/lean-project-evidence/research/ethereum-xmss-durability-handoff-20261013/handoff_xmss_durability/review_candidate.sh
bash -n review_candidate.sh
bash review_candidate.sh
```

The execution script is public and should be inspected before running it.
The printed checkout contains the exact proposed changes, and
`xmss-combined.patch` is the corresponding diff against PR #1204.

## Evidence and limits

- Existing combined candidate, prior to persistence changes:
  [CI #38377064853](https://github.com/fraware/lean-project-evidence/actions/runs/38377064853)
  passed 73 focused and 2,968 standard tests.
- New persistence-configuration and backup-rollback correction:
  [CI #38464729618](https://github.com/fraware/lean-project-evidence/actions/runs/38464729618)
  targets the exact source commit above. Consult the live CI verdict;
  a queued or executing run does **not** establish test success.
- The limited [threat and claims document](../research/ethereum-xmss/PERSISTENCE_CONTRACT.md)
  disclaims backup-rollback resistance, independent signer key custody,
  hardware/fsync guarantees, and formal implementation refinement.

This candidate stacks the new local-persistence analysis on the combined
atomic reservation and signing-precondition work. It is intended for
independent review; the upstream maintainer must decide whether to split
these concerns into separate upstream patches.
