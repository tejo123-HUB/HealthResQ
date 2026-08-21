"""INT-07: the five documented graph query types, all answered directly against the persisted
graph via openCypher — nothing here is reconstructed in memory from a relational join. Every
result list is ordered by graph cost = distanceKm + estimatedMinutes * DELAY_WEIGHT +
(BOUNDARY_PENALTY if crossBoundary else 0), per healthresq-architecture.md's INT-07 acceptance
criterion.

These are graph-only primitives (reachability, ranking, authority chains) — `backend.intelligence
.tools` composes them with forecasting/stock data to build the frozen tool functions
(`find_safe_donors`, `get_dependency_impact`, `generate_redistribution_options`).
"""

from sqlalchemy.orm import Session

from backend.intelligence.graph.session import run_cypher

DELAY_WEIGHT = 0.1
BOUNDARY_PENALTY = 25.0


def _cost(distance_km: float, estimated_minutes: float, cross_boundary: bool) -> float:
    return distance_km + estimated_minutes * DELAY_WEIGHT + (BOUNDARY_PENALTY if cross_boundary else 0.0)


def nearest_safe_donor_candidates(db: Session, destination_id: str) -> list[dict]:
    """Query 1: every facility with a direct SUPPLY_ROUTE into `destination_id`, ranked by cost."""
    rows = run_cypher(
        db,
        "MATCH (a:Facility)-[r:SUPPLY_ROUTE]->(b:Facility {id: $destinationId}) "
        "RETURN a.id, r.distanceKm, r.estimatedMinutes, r.crossBoundary",
        {"destinationId": destination_id},
        columns=("sourceId", "distanceKm", "estimatedMinutes", "crossBoundary"),
    )
    candidates = [
        {
            "facilityId": source_id,
            "distanceKm": distance_km,
            "estimatedMinutes": estimated_minutes,
            "crossBoundary": cross_boundary,
            "cost": _cost(distance_km, estimated_minutes, cross_boundary),
        }
        for source_id, distance_km, estimated_minutes, cross_boundary in rows
    ]
    return sorted(candidates, key=lambda c: c["cost"])


def dependency_impact(db: Session, facility_id: str) -> list[str]:
    """Query 2: facilities that have a SUPPLY_ROUTE *from* `facility_id` — the ones that lose a
    donor option if this facility becomes unavailable."""
    rows = run_cypher(
        db,
        "MATCH (:Facility {id: $facilityId})-[:SUPPLY_ROUTE]->(dependent:Facility) RETURN dependent.id",
        {"facilityId": facility_id},
        columns=("dependentId",),
    )
    return sorted({row[0] for row in rows})


def alternative_supply_paths(db: Session, destination_id: str, *, max_alternatives: int = 5) -> list[dict]:
    """Query 3: direct (1-hop) and relayed (2-hop, through one intermediate facility) supply
    paths into `destination_id`, ranked by cumulative cost — the options beyond the single
    nearest donor."""
    direct = [
        {"path": [c["facilityId"], destination_id], "cost": c["cost"]}
        for c in nearest_safe_donor_candidates(db, destination_id)
    ]

    two_hop_rows = run_cypher(
        db,
        "MATCH (a:Facility)-[r1:SUPPLY_ROUTE]->(mid:Facility)-[r2:SUPPLY_ROUTE]->(b:Facility {id: $destinationId}) "
        "WHERE a.id <> $destinationId "
        "RETURN a.id, mid.id, r1.distanceKm, r1.estimatedMinutes, r1.crossBoundary, "
        "r2.distanceKm, r2.estimatedMinutes, r2.crossBoundary",
        {"destinationId": destination_id},
        columns=("sourceId", "midId", "d1", "m1", "cb1", "d2", "m2", "cb2"),
    )
    relayed = [
        {
            "path": [source_id, mid_id, destination_id],
            "cost": _cost(d1, m1, cb1) + _cost(d2, m2, cb2),
        }
        for source_id, mid_id, d1, m1, cb1, d2, m2, cb2 in two_hop_rows
    ]

    combined = sorted(direct + relayed, key=lambda p: p["cost"])
    return combined[:max_alternatives]


def get_required_authority(db: Session, source_facility_id: str, dest_facility_id: str) -> dict:
    """Query 4: the lowest authority that can authorize a movement between two facilities, per
    CMD-02's rule — same district = DISTRICT, same state (different district) = STATE, otherwise
    NATIONAL — computed only from persisted ADMIN_PARENT edges, never from an agent's say-so."""
    rows = run_cypher(
        db,
        "MATCH (f:Facility {id: $facilityId})-[:ADMIN_PARENT]->(d:AuthorityLevel {level: 'DISTRICT'})"
        "-[:ADMIN_PARENT]->(s:AuthorityLevel {level: 'STATE'})-[:ADMIN_PARENT]->(n:AuthorityLevel {level: 'NATIONAL'}) "
        "RETURN d.id, s.id, n.id",
        {"facilityId": source_facility_id},
        columns=("districtId", "stateId", "nationalId"),
    )
    dest_rows = run_cypher(
        db,
        "MATCH (f:Facility {id: $facilityId})-[:ADMIN_PARENT]->(d:AuthorityLevel {level: 'DISTRICT'})"
        "-[:ADMIN_PARENT]->(s:AuthorityLevel {level: 'STATE'})-[:ADMIN_PARENT]->(n:AuthorityLevel {level: 'NATIONAL'}) "
        "RETURN d.id, s.id, n.id",
        {"facilityId": dest_facility_id},
        columns=("districtId", "stateId", "nationalId"),
    )
    if not rows or not dest_rows:
        return {"requiredAuthority": "NATIONAL", "path": [source_facility_id, dest_facility_id]}

    src_district, src_state, src_national = rows[0]
    dst_district, dst_state, dst_national = dest_rows[0]

    if src_district == dst_district:
        authority, authority_id = "DISTRICT", src_district
    elif src_state == dst_state:
        authority, authority_id = "STATE", src_state
    elif src_national == dst_national:
        authority, authority_id = "NATIONAL", src_national
    else:
        authority, authority_id = "NATIONAL", src_national

    return {
        "requiredAuthority": authority,
        "authorityId": authority_id,
        "path": [source_facility_id, dest_facility_id],
    }


def cluster_risk_facility_ids(db: Session, scope_level: str, scope_id: str) -> list[str]:
    """Query 5: every facility whose ADMIN_PARENT chain reaches the given authority scope — the
    persisted-graph source of truth for a dashboard rollup (CMD-09), so a district/state/national
    scope's facility membership is answered by the same graph everything else queries, not a
    second, possibly-diverging relational hierarchy walk."""
    if scope_level == "FACILITY":
        return [scope_id]
    rows = run_cypher(
        db,
        "MATCH (f:Facility)-[:ADMIN_PARENT*1..3]->(a:AuthorityLevel {id: $scopeId}) RETURN DISTINCT f.id",
        {"scopeId": scope_id},
        columns=("facilityId",),
    )
    return sorted({row[0] for row in rows})
