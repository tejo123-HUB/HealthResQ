"""INT-06: bring the persisted graph into existence. Called once per database (app startup, and
once per pytest session against the throwaway `healthresq_test` database) — not per request."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.intelligence.graph import GRAPH_NAME
from backend.intelligence.graph.session import install_age_session_setup


def ensure_graph_ready(engine: Engine) -> None:
    """Idempotent: safe to call against a fresh database or one that already has the extension
    and graph. `create_graph()` itself errors if the graph already exists, so that call is guarded
    explicitly rather than relied on to no-op."""
    install_age_session_setup()
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS age"))
        conn.execute(text("LOAD 'age'"))
        conn.execute(text('SET search_path = ag_catalog, "$user", public'))
        exists = conn.execute(
            text("SELECT 1 FROM ag_catalog.ag_graph WHERE name = :name"), {"name": GRAPH_NAME}
        ).first()
        if not exists:
            conn.execute(text("SELECT ag_catalog.create_graph(:name)"), {"name": GRAPH_NAME})
        conn.commit()
