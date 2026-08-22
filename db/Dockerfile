# Postgres + PostGIS + Apache AGE in one image (INT-06). No official image ships both PostGIS
# and AGE together, so this layers AGE's openCypher extension on top of the official PostGIS
# image. Pin to PG16 — AGE has a mature stable release for it and postgis/postgis:16-* is on
# the more mature Debian Bullseye base (vs. Trixie for PG18+ tags).
#
# AGE's compiled extension files are copied from the official apache/age image rather than built
# from source here (git clone + apt-get against deb.debian.org/apt.postgresql.org) — some network
# environments (this project's CI/dev sandboxes included) can reach Docker Hub but not arbitrary
# Debian/PGDG package mirrors, so compiling from source is not reliably reproducible. `age.control`
# has no version pin in how the app loads it (`CREATE EXTENSION IF NOT EXISTS age` in
# backend/intelligence/graph/schema.py), so whatever default_version ships in the base image is fine.
FROM apache/age:release_PG16_1.5.0 AS age-src

FROM postgis/postgis:16-3.4

COPY --from=age-src /usr/lib/postgresql/16/lib/age.so /usr/lib/postgresql/16/lib/age.so
COPY --from=age-src /usr/share/postgresql/16/extension/age.control /usr/share/postgresql/16/extension/age.control
COPY --from=age-src /usr/share/postgresql/16/extension/age--*.sql /usr/share/postgresql/16/extension/

# Deliberately no docker-entrypoint-initdb.d script here: CREATE EXTENSION / create_graph() need
# to run per-database (dev DB, and pytest's throwaway healthresq_test DB created after this
# container has already started) — that idempotent setup lives in
# backend/intelligence/graph/schema.py:ensure_graph_ready(), called from app startup and from the
# test suite, not baked into the image.
