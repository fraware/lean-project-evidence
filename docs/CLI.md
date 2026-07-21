# CLI and API contract

## CLI conventions

- human-readable output by default;
- `--json` for machine output;
- nonzero exit on invalid input or hard execution failure;
- no interactive prompts in CI;
- paths resolved and printed;
- secrets never printed.

## Common workflows

Validate a project contract:

```bash
lpe contract validate examples/minimal-project
```

Compile evidence:

```bash
lpe evidence compile \
  --project examples/minimal-project \
  --candidate examples/candidates/R3-definition-change.json \
  --output .lpe/evidence/example.json
```

Doctor / research honesty surfaces:

```bash
lpe doctor
lpe research status
```

Ledger verify / archive / seal:

```bash
lpe ledger verify <ledger.sqlite3>
lpe ledger archive <ledger.sqlite3> --output <archive/events.jsonl>
lpe ledger seal <ledger.sqlite3> --seal <off-host/seal.json>
```

Pilot instrumentation (not §21 clearance):

```bash
lpe pilot init-partner --dir ./partner-pilot
lpe pilot record ...
lpe pilot summary --ledger <ledger.sqlite3>
```

## Future HTTP service

The OpenAPI document (`openapi/openapi.yaml`) is an interoperability contract.
It is not authorization to build a service before the CLI and scientific
workflow are validated.

## Related

- Security controls operators must know: [`SECURITY_AND_PRIVACY.md`](SECURITY_AND_PRIVACY.md)
- Root security policy: [`../SECURITY.md`](../SECURITY.md)
