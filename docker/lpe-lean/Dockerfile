# Lean-capable sandbox image for Lean Project Evidence.
#
# Pre-installs elan + a pinned Lean toolchain so builds can run under
# Docker --network=none (elan cannot download toolchains at runtime).
#
# Default tag: lpe-lean:4.14
# Build: scripts/build_lean_docker_image.ps1  (Windows) or .sh (Linux/macOS)
#
# Usage:
#   set LPE_DOCKER_IMAGE=lpe-lean:4.14
#   lpe evidence compile ...   # network_policy: deny → isolation PASS when build runs
#
# TODO(CLOSURE-004): generate SBOM (e.g. syft/trivy) on image build in CI.
# TODO(CLOSURE-004): publish and pin runtime by digest (not mutable tags) in CI.

FROM ubuntu:22.04

ARG LEAN_TOOLCHAIN=leanprover/lean4:v4.14.0
ARG DEBIAN_FRONTEND=noninteractive

# Pin elan release tarball (linux x86_64) — checksum of elan-x86_64-unknown-linux-gnu.tar.gz
# from https://github.com/leanprover/elan/releases/tag/v4.2.3
ARG ELAN_VERSION=v4.2.3
ARG ELAN_ARCH=x86_64-unknown-linux-gnu
ARG ELAN_SHA256=df0b2b3a439961ffcbb3985214365ffe40f49bc871df04dff268c7d8e21ca8b2

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        build-essential \
        libgmp-dev \
    && rm -rf /var/lib/apt/lists/*

# Checksum-pinned elan installer (no curl|sh). Installer binary is elan-init.
RUN curl -sSfL \
      "https://github.com/leanprover/elan/releases/download/${ELAN_VERSION}/elan-${ELAN_ARCH}.tar.gz" \
      -o /tmp/elan.tar.gz \
    && echo "${ELAN_SHA256}  /tmp/elan.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/elan.tar.gz -C /tmp \
    && /tmp/elan-init -y --default-toolchain none \
    && rm -f /tmp/elan.tar.gz /tmp/elan-init \
    && /root/.elan/bin/elan toolchain install "${LEAN_TOOLCHAIN}" \
    && /root/.elan/bin/elan default "${LEAN_TOOLCHAIN}" \
    && /root/.elan/bin/lean --version \
    && /root/.elan/bin/lake --version

ENV PATH="/root/.elan/bin:/home/lpe/.elan/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ENV HOME="/home/lpe"

# Unprivileged runtime user (CLOSURE-004). Elan remains under /root for
# compatibility with existing local tags; prefer copying toolchain into
# /home/lpe in a follow-up image rebuild published by digest.
RUN useradd --create-home --uid 1000 --shell /bin/bash lpe \
    && mkdir -p /home/lpe/.elan /worktree-output /lake-cache \
    && chown -R lpe:lpe /home/lpe /worktree-output /lake-cache

WORKDIR /work

# Sanity label for `docker image inspect` / docs.
LABEL org.opencontainers.image.title="lpe-lean" \
      org.opencontainers.image.description="elan + Lean for LPE sandboxed Lake builds" \
      lpe.lean.toolchain="${LEAN_TOOLCHAIN}" \
      lpe.elan.version="${ELAN_VERSION}"
