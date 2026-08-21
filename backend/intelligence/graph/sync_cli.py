"""Re-sync the persisted graph (INT-06) from OPS's current geography/facility tables.

`backend.seed` calls `sync_graph_from_ops` itself as part of seeding, so this script is for the
other case: OPS geography or facility rows changed by some other path (a future `POST /facilities`
endpoint, a manual DB fix, a migration) and the graph needs to catch up. There is no automatic
trigger for that yet — `healthresq-interface-shapes.md`'s OPS-09 surface has no facility-creation
endpoint in this build, only `GET /facilities`, so there's currently nowhere else to hook this into.
Whoever adds that endpoint should call `sync_graph_from_ops` at the end of it, the same way
`backend.seed` does, rather than requiring an operator to remember to run this script.

Run with: python -m backend.intelligence.graph.sync_cli
"""

from backend.db import SessionLocal, engine
from backend.intelligence.graph.build import sync_graph_from_ops
from backend.intelligence.graph.schema import ensure_graph_ready


def run() -> None:
    ensure_graph_ready(engine)
    db = SessionLocal()
    try:
        sync_graph_from_ops(db)
        db.commit()
        print("Graph re-synced from current OPS geography/facility data.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
