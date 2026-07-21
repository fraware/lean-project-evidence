#!/usr/bin/env bash
# Wrapper around scripts/generate_sbom.py (§8.3 / §19.5).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${PYTHON:-python3}" "${REPO_ROOT}/scripts/generate_sbom.py" "$@"
