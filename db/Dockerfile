# Postgres + PostGIS + Apache AGE in one image (INT-06). No official image ships both PostGIS
# and AGE together, so this layers AGE's openCypher extension on top of the official PostGIS
# image. Pin to PG16 — AGE has a mature stable release for it and postgis/postgis:16-* is on
# the more mature Debian Bullseye base (vs. Trixie for PG18+ tags).
FROM postgis/postgis:16-3.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        postgresql-server-dev-16 \
        git \
        flex \
        bison \
        ca-certificates \
        clang-13 \
        llvm-13 \
    && git clone --branch release/PG16/1.6.0 --depth 1 https://github.com/apache/age.git /tmp/age \
    && make -C /tmp/age PG_CONFIG=/usr/lib/postgresql/16/bin/pg_config \
    && make -C /tmp/age install PG_CONFIG=/usr/lib/postgresql/16/bin/pg_config \
    && rm -rf /tmp/age \
    && rm -rf /var/lib/apt/lists/*

# Deliberately no docker-entrypoint-initdb.d script here: CREATE EXTENSION / create_graph() need
# to run per-database (dev DB, and pytest's throwaway healthresq_test DB created after this
# container has already started) — that idempotent setup lives in
# backend/intelligence/graph/schema.py:ensure_graph_ready(), called from app startup and from the
# test suite, not baked into the image.
