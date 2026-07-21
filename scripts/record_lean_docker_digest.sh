#!/usr/bin/env bash
# Record local lpe-lean image digest and print publish-by-digest recipe.
# Does NOT require registry login. Push steps are documented only.
#
# Usage:
#   ./scripts/record_lean_docker_digest.sh [tag] [out-dir]
#   ./scripts/record_lean_docker_digest.sh lpe-lean:4.14 artifacts/sbom
#
# After a real registry push (operator):
#   docker push "$REGISTRY/$IMAGE"
#   pin runtime / CI to:  "$REGISTRY/$IMAGE@sha256:..."

set -euo pipefail

TAG="${1:-lpe-lean:4.14}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${2:-${REPO_ROOT}/artifacts/sbom}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found on PATH. Install Docker and retry." >&2
  exit 1
fi

mkdir -p "${OUT_DIR}"

if ! docker image inspect "${TAG}" >/dev/null 2>&1; then
  cat > "${OUT_DIR}/lpe-lean.digest.README.txt" <<EOF
Image ${TAG} is not present locally.
Build first:
  ./scripts/build_lean_docker_image.sh ${TAG}
Then re-run:
  ./scripts/record_lean_docker_digest.sh ${TAG} ${OUT_DIR}
EOF
  echo "Image ${TAG} missing; wrote ${OUT_DIR}/lpe-lean.digest.README.txt" >&2
  exit 2
fi

IMAGE_ID="$(docker image inspect --format '{{.Id}}' "${TAG}")"
REPO_DIGEST="$(docker image inspect --format '{{index .RepoDigests 0}}' "${TAG}" 2>/dev/null || true)"
CREATED="$(docker image inspect --format '{{.Created}}' "${TAG}")"

DIGEST_FILE="${OUT_DIR}/lpe-lean.digest.txt"
{
  echo "tag=${TAG}"
  echo "image_id=${IMAGE_ID}"
  echo "repo_digest=${REPO_DIGEST:-none_until_pushed}"
  echo "created=${CREATED}"
  echo "recorded_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${DIGEST_FILE}"

RECIPE="${OUT_DIR}/lpe-lean.publish-by-digest.md"
cat > "${RECIPE}" <<EOF
# Publish \`lpe-lean\` by digest (operator recipe)

Local image identity recorded in \`lpe-lean.digest.txt\`.

## Pin for local use (no registry)

\`\`\`bash
export LPE_DOCKER_IMAGE=${TAG}
# Prefer content address when available:
# export LPE_DOCKER_IMAGE=${IMAGE_ID}
\`\`\`

\`RepoDigests\` is empty until the image is pushed to a registry.

## Publish and pin by digest (requires registry login)

\`\`\`bash
REGISTRY=ghcr.io/example   # replace with your org registry
NAME=lpe-lean
VERSION=4.14

docker tag ${TAG} "\${REGISTRY}/\${NAME}:\${VERSION}"
docker push "\${REGISTRY}/\${NAME}:\${VERSION}"

# Resolve immutable digest after push:
DIGEST=\$(docker image inspect --format '{{index .RepoDigests 0}}' "\${REGISTRY}/\${NAME}:\${VERSION}")
echo "Pin CI / runtime to: \${DIGEST}"

# Example pin (immutable):
#   LPE_DOCKER_IMAGE=ghcr.io/example/lpe-lean@sha256:...
\`\`\`

## SBOM

\`\`\`bash
python scripts/generate_sbom.py --image ${TAG} --out-dir ${OUT_DIR}
\`\`\`

Do not promote a floating tag to automatic acceptance without a digest pin.
EOF

echo "Wrote ${DIGEST_FILE}"
echo "Wrote ${RECIPE}"
if [[ -z "${REPO_DIGEST}" || "${REPO_DIGEST}" == "<no value>" ]]; then
  echo "Note: repo digest unavailable until the image is pushed to a registry."
fi
