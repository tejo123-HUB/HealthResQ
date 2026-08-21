"""Apache AGE session plumbing (INT-06) and the openCypher call helper (INT-07).

Two things AGE needs that plain SQLAlchemy doesn't give you for free:

1. `LOAD 'age'; SET search_path = ag_catalog, "$user", public;` on every *physical* connection,
   not baked into the extension by `CREATE EXTENSION` alone. Registered globally on the
   `Engine` class's `"connect"` event so it fires for any engine created anywhere in the
   process — the app's shared `backend.db.engine` and pytest's own `test_engine` alike —
   without either of those modules needing to know AGE exists.
2. `agtype` results don't cleanly cast to jsonb server-side (a known, unresolved AGE gap —
   github.com/apache/age/issues/1225): every `vertex`/`edge`/`path` value comes back as text
   with a trailing `::vertex`/`::edge`/`::path` suffix. `parse_agtype` strips it and parses the
   rest as JSON.
"""

import json
import re
import uuid

from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.intelligence.graph import GRAPH_NAME

_installed = False


def install_age_session_setup() -> None:
    """Idempotent — safe to call from every module that touches the graph."""
    global _installed
    if _installed:
        return

    @event.listens_for(Engine, "connect")
    def _load_age(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("LOAD 'age';")
            cursor.execute('SET search_path = ag_catalog, "$user", public;')
        except Exception:
            # Non-AGE databases (e.g. a plain Postgres used in an unrelated test) shouldn't be
            # broken by this — the extension may simply not be installed there yet.
            dbapi_connection.rollback()
        else:
            dbapi_connection.commit()
        finally:
            cursor.close()

    _installed = True


_AGTYPE_SUFFIX_RE = re.compile(r"::(vertex|edge|path)$")


def parse_agtype(value):
    """Strip AGE's `::vertex`/`::edge`/`::path` suffix (if present) and parse the remainder as
    JSON. Scalars (plain numbers/booleans already decoded by the driver) pass through unchanged."""
    if value is None or isinstance(value, (dict, list, int, float, bool)):
        return value
    return json.loads(_AGTYPE_SUFFIX_RE.sub("", str(value)))


def run_cypher(
    session: Session, cypher_query: str, params: dict | None = None, *, columns: tuple[str, ...] = ("result",)
) -> list[list]:
    """Run an openCypher query against `GRAPH_NAME` and return rows with every column parsed via
    `parse_agtype`. `columns` is the mandatory `AS (col agtype, ...)` spec — its arity must match
    the query's `RETURN` clause exactly, and AGE requires it even for a `CREATE`-only query with no
    `RETURN` at all.

    Parameters are passed through AGE's documented `PREPARE ... EXECUTE` form (a bare bind
    parameter in `cypher()`'s third argument position raises "third argument of cypher function
    must be a parameter" for some driver/parameter-style combinations) — `params` becomes one
    `agtype` map, referenced in `cypher_query` as `$key`.

    `cypher_query` is embedded into a SQLAlchemy `text()` string, whose own bind-parameter syntax
    also uses a leading colon — colliding with Cypher's `:Label` syntax (`CREATE (:Facility {...})`
    reads as a required bind parameter named `Facility` otherwise). Every literal colon in
    `cypher_query` is escaped with a backslash before it reaches `text()`, per SQLAlchemy's
    documented escaping for literal colons.
    """
    escaped_query = cypher_query.replace(":", "\\:")
    col_spec = ", ".join(f"{c} agtype" for c in columns)
    if params:
        stmt_name = f"cy_{uuid.uuid4().hex[:12]}"
        session.execute(
            text(
                f"PREPARE {stmt_name}(agtype) AS "
                f"SELECT * FROM cypher('{GRAPH_NAME}', $$ {escaped_query} $$, $1) AS ({col_spec})"
            )
        )
        # No try/finally DEALLOCATE here: once EXECUTE fails, the transaction is aborted and any
        # further statement on it (including DEALLOCATE) fails too, masking the real error under
        # a confusing "current transaction is aborted" one. Let the real exception propagate —
        # cleanup is moot until the transaction rolls back anyway.
        #
        # The JSON param object is embedded as a quoted SQL string literal, not a driver-level
        # bind parameter: psycopg sends bind parameters over the extended protocol with no type
        # context, and `EXECUTE stmt($1)` can't resolve one for a prepared statement's parameter
        # slot even with an explicit CAST ("could not determine data type of parameter $1") — this
        # is exactly the literal form the AGE manual's own example uses
        # (`EXECUTE cypher_stored_procedure('{"name": "Tobias"}')`). Standard SQL single-quote
        # escaping (doubling `'`) keeps this safe even though the values are our own UUIDs/enums,
        # never raw user text.
        escaped_literal = json.dumps(params).replace("'", "''")
        result = session.execute(text(f"EXECUTE {stmt_name}('{escaped_literal}')"))
        rows = result.fetchall()
        session.execute(text(f"DEALLOCATE {stmt_name}"))
    else:
        result = session.execute(
            text(f"SELECT * FROM cypher('{GRAPH_NAME}', $$ {escaped_query} $$) AS ({col_spec})")
        )
        rows = result.fetchall()
    return [[parse_agtype(v) for v in row] for row in rows]
