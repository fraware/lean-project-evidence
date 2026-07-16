#!/usr/bin/env bash
# Build the local Lean-capable sandbox image for LPE (Linux / macOS / Git Bash).
# Usage: ./scripts/build_lean_docker_image.sh [tag] [toolchain]

set -euo pipefail

TAG="${1:-lpe-lean:4.14}"
TOOLCHAIN="${2:-leanprover/lean4:v4.14.0}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKERFILE_DIR="${REPO_ROOT}/docker/lpe-lean"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found on PATH. Install Docker and retry." >&2
  exit 1
fi

echo "Building ${TAG} (toolchain=${TOOLCHAIN}) from ${DOCKERFILE_DIR}"
echo "This downloads elan + Lean; expect several minutes on first run."

docker build \
  --build-arg "LEAN_TOOLCHAIN=${TOOLCHAIN}" \
  -t "${TAG}" \
  "${DOCKERFILE_DIR}"

echo
echo "Built ${TAG}. Verify:"
echo "  docker run --rm ${TAG} lean --version"
echo "  docker run --rm ${TAG} lake --version"
echo
echo "Use with LPE:"
echo "  export LPE_DOCKER_IMAGE=${TAG}"
