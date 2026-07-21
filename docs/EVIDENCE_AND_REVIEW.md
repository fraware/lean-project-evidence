# Evidence compiler and review router

## Evidence compiler

### Input

- validated project contract;
- candidate descriptor;
- target Git repository;
- exact base and head;
- provider registry.

### Output

A canonical evidence packet conforming to `schemas/evidence-packet.schema.json`.

### Deterministic stage order

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

### Idempotency

The evidence run ID is derived from:

- project-contract hash;
- candidate hash;
- compiler version;
- provider-version map;
- execution-policy hash.

Re-running identical inputs must produce the same structured result except timestamps and nondeterministic provider evidence, which must identify its seed and model version.

## Review router

### Objective

Minimize expert minutes required to resolve acceptance-controlling uncertainty.

### Version 0 policy

Use deterministic priority and risk authority.

The selected question must include:

- one concise question;
- why it controls the decision;
- evidence supporting each plausible answer;
- expected answer type;
- required authority;
- estimated review time.

### Prohibited behavior

- asking the reviewer to re-read the entire repository without evidence;
- hiding conflicting evidence;
- converting uncertainty into confidence;
- selecting a stylistic question while semantic uncertainty remains.

### Authority

High-risk acceptance requires human authority per ADR 0003. See
[`adr/0003-human-authority.md`](adr/0003-human-authority.md) and
[`NON_CLAIMS.md`](NON_CLAIMS.md).
