# Postgres 17 + hypopg (hypothetical indexes) + pg_stat_statements.
# The official image already ships the PGDG apt repo, so hypopg is one package.
FROM postgres:17

RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-17-hypopg \
 && rm -rf /var/lib/apt/lists/*

COPY init/ /docker-entrypoint-initdb.d/
