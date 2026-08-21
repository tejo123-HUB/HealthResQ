# HealthResQ

Federated agentic health-resource and supply-chain resilience platform. See `AGENTS.md` for the
module layout and the three companion architecture documents for full requirements.

## Direction 1 — Operations & Facility Systems (implemented)

`backend/ops/` implements `OPS-01`–`OPS-14`: geography/auth hierarchy, PHC/SHC/warehouse
terminals, the transactional inventory ledger, hospital-management encounters (admission/ward/OT/
discharge/referral), data freshness classification, and the public reference-indicator adapter.
Package management is via [uv](https://docs.astral.sh/uv/).

### Run with Docker Compose (recommended)

```
cp .env.example .env
docker compose up -d --build
```

This starts PostgreSQL (with PostGIS) and the API (migrations run automatically on container
start). Seed demo data once the stack is up:

```
docker compose exec api python -m backend.seed
```

API is then available at `http://localhost:8000` (`/health`, interactive docs at `/docs`).

### Run locally against `docker compose up -d db`

```
cp .env.example .env
uv sync
docker compose up -d db
uv run alembic upgrade head
uv run python -m backend.seed
uv run uvicorn backend.app:app --reload
```

### Demo login

Every seeded user shares the password in `.env`'s `SEED_DEFAULT_PASSWORD` (default
`demo-pass-123`). Example usernames: `operator.phc-001` (facility scope), `district.krishna`
(district scope), `state.andhra-pradesh` (state scope), `national.india` (national scope).

### Tests

```
uv run pytest backend/tests -v
```

Tests run against a real Postgres database (`healthresq_test`, created automatically) — bring up
`docker compose up -d db` first. Each test runs in its own rolled-back transaction, so nothing
persists between tests or depends on seed data.

### Reference-indicator adapter (`OPS-14`)

`REFERENCE_INDICATOR_MODE=mock` (default) serves fixed sample values with zero network calls.
Set `REFERENCE_INDICATOR_MODE=real` to call the public WHO GHO OData API instead — no API key or
registration required either way.
