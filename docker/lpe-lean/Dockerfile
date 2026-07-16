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

FROM ubuntu:22.04

ARG LEAN_TOOLCHAIN=leanprover/lean4:v4.14.0
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        build-essential \
        libgmp-dev \
    && rm -rf /var/lib/apt/lists/*

# Non-interactive elan install; pin toolchain at image-build time.
RUN curl -sSf https://elan.lean-lang.org/elan-init.sh \
    | sh -s -- -y --default-toolchain none \
    && /root/.elan/bin/elan toolchain install "${LEAN_TOOLCHAIN}" \
    && /root/.elan/bin/elan default "${LEAN_TOOLCHAIN}" \
    && /root/.elan/bin/lean --version \
    && /root/.elan/bin/lake --version

ENV PATH="/root/.elan/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ENV HOME="/root"

WORKDIR /work

# Sanity label for `docker image inspect` / docs.
LABEL org.opencontainers.image.title="lpe-lean" \
      org.opencontainers.image.description="elan + Lean for LPE sandboxed Lake builds" \
      lpe.lean.toolchain="${LEAN_TOOLCHAIN}"
