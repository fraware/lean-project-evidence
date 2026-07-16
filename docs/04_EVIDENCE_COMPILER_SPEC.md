# Evidence Compiler specification

## Input

- validated project contract;
- candidate descriptor;
- target Git repository;
- exact base and head;
- provider registry.

## Output

A canonical evidence packet conforming to `schemas/evidence-packet.schema.json`.

## Deterministic stage order

1. normalize;
2. classify;
3. execute;
4. apply hard gates;
5. collect evidence;
6. assess uncertainty;
7. classify risk;
8. recommend;
9. select review question;
10. persist packet event.

## Idempotency

The evidence run ID is derived from:

- project-contract hash;
- candidate hash;
- compiler version;
- provider-version map;
- execution-policy hash.

Re-running identical inputs must produce the same structured result except timestamps and nondeterministic provider evidence, which must identify its seed and model version.
