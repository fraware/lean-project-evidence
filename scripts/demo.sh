#!/usr/bin/env bash
set -euo pipefail

mkdir -p .lpe/evidence
lpe contract validate examples/minimal-project
lpe evidence compile \
  --project examples/minimal-project \
  --candidate examples/candidates/R3-definition-change.json \
  --output .lpe/evidence/example.json \
  --skip-build
cat .lpe/evidence/example.json
