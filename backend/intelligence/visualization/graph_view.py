"""INT-13: a graph view scoped to only the nodes/edges referenced by an active redistribution
plan. Takes the movement set itself (`generate_redistribution_options`'s `movements`), not a
`recommendationId` — recommendations are Direction 3's (CMD) object, and looking one up here
would give Direction 2 a dependency the whole point of stubbing was to avoid."""

from sqlalchemy.orm import Session

from backend.intelligence.graph.session import run_cypher


def get_scoped_graph_view(db: Session, movements: list[dict]) -> dict:
    facility_ids = sorted({m["from"] for m in movements} | {m["to"] for m in movements})
    if not facility_ids:
        return {"nodes": [], "edges": []}

    node_rows = run_cypher(
        db,
        "MATCH (f:Facility) WHERE f.id IN $ids RETURN f.id, f.type, f.districtId",
        {"ids": facility_ids},
        columns=("id", "type", "districtId"),
    )
    nodes = [{"id": fid, "type": ftype, "districtId": district_id} for fid, ftype, district_id in node_rows]
    edges = [{"from": m["from"], "to": m["to"], "quantity": m["quantity"]} for m in movements]
    return {"nodes": nodes, "edges": edges}
