# Engineering runbook

## Start a task

1. Identify the milestone and issue.
2. State the invariant affected.
3. Add or update tests before implementation.
4. Keep external systems behind protocols.
5. Record schema or ADR implications.
6. Run `make check`.
7. Include evidence in the pull request.

## Pull request requirements

- one primary objective;
- linked issue;
- tests;
- documentation;
- migration note for schema changes;
- security note for execution or provider changes;
- benchmark note for performance-sensitive work.

## Release

1. freeze schemas;
2. run unit and integration tests;
3. validate examples;
4. verify ledger migrations;
5. generate changelog;
6. tag;
7. publish package;
8. retain build provenance.

## Operational debugging

Never edit ledger events.

Reproduce from recorded hashes and commands.

Provider failures should be converted to explicit findings before retrying.

## Ledger retention (archive)

Do not DELETE or rewrite live events. Archive with:

```bash
lpe ledger archive path/to/live.sqlite3 --output path/to/archive/events.jsonl
```

Then optionally `lpe ledger init path/to/fresh.sqlite3` for a new working set. See `docs/06_UTILITY_LEDGER_SPEC.md` and `docs/25_LEDGER_THREAT_MODEL.md`.
