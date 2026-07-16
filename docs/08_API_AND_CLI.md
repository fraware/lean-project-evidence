# API and CLI contract

## CLI conventions

- human-readable output by default;
- `--json` for machine output;
- nonzero exit on invalid input or hard execution failure;
- no interactive prompts in CI;
- paths resolved and printed;
- secrets never printed.

## Future HTTP service

The OpenAPI document is an interoperability contract. It is not authorization to build a service before the CLI and scientific workflow are validated.
