#!/usr/bin/env sh
# Build the database image. Plain `docker compose build` is right on a laptop.
# In a cloud session behind the HTTPS-only egress proxy, run this instead; then
# `docker compose up -d` uses the image it built.
set -eu
cd "$(dirname "$0")/.."

if [ -n "${HTTPS_PROXY:-}" ] && [ -f /root/.ccr/ca-bundle.crt ]; then
    exec docker build --network=host \
        --build-arg APT_HTTPS=1 \
        --build-arg HTTPS_PROXY="$HTTPS_PROXY" \
        --build-context ca=/root/.ccr \
        -t pokedex-ops-postgres:17 docker/
fi
exec docker build -t pokedex-ops-postgres:17 docker/
