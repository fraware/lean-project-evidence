# GitHub labels

Canonical label names live in `backlog/github_labels.txt` (one label per line).

## Types

- `type:epic`
- `type:feature`
- `type:bug`
- `type:research`
- `type:docs`

## Areas

- `area:foundation`
- `area:schema`
- `area:contract`
- `area:provenance`
- `area:ledger`
- `area:metrics`
- `area:evidence`
- `area:execution`
- `area:security`
- `area:git`
- `area:policy`
- `area:reporting`
- `area:review`
- `area:github`
- `area:lean`
- `area:semantic`
- `area:repository`
- `area:downstream`
- `area:pilot`
- `area:ml`
- `area:synthesis`

## Priority and status

- `priority:critical`
- `priority:high`
- `status:blocked`

## Apply labels on GitHub

When `gh` is authenticated against the target repository:

```bash
python scripts/github_launch.py labels --apply
```

Or create labels manually following `docs/16_REPOSITORY_LAUNCH.md` section 3.
