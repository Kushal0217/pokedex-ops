# Postgres 17 + hypopg (hypothetical indexes) + pg_stat_statements.
# The official image already ships the PGDG apt repo, so hypopg is one package.

# Placeholder stage, overridden only by scripts/build_db_image.sh (see below).
FROM scratch AS ca

FROM postgres:17

# Default build (laptop, CI): plain apt, nothing special.
#
# Behind an HTTPS-only egress proxy (cloud sessions), apt's default http://
# sources are refused, so scripts/build_db_image.sh sets APT_HTTPS=1 and mounts
# the proxy's CA certificate as the `ca` build context. apt is then pointed at
# that certificate for this one RUN and switched to https://. Nothing is left
# behind in the image.
ARG APT_HTTPS=0
RUN --mount=type=bind,from=ca,target=/ca \
    set -eu; \
    APT_OPTS=""; \
    if [ "$APT_HTTPS" = 1 ]; then \
        find /etc/apt -type f \( -name '*.list' -o -name '*.sources' \) \
            -exec sed -i 's|http://|https://|g' {} +; \
        APT_OPTS="-o Acquire::https::CaInfo=/ca/ca-bundle.crt"; \
    fi; \
    apt-get $APT_OPTS update; \
    apt-get $APT_OPTS install -y --no-install-recommends postgresql-17-hypopg; \
    rm -rf /var/lib/apt/lists/*

COPY init/ /docker-entrypoint-initdb.d/
