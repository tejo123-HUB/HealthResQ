"""INT-06: populate the persisted graph from Direction 1's real geography/facility tables.

Full rebuild, not incremental — simplest correct approach for a two-day prototype's data volumes
(dozens of facilities). `sync_graph_from_ops` is idempotent: it clears every node/edge in
`GRAPH_NAME` first, so calling it again after OPS data changes is always safe.

Supply-route topology (there is no real road-network data to route against): every donor-capable
facility pair within the same district gets a `SUPPLY_ROUTE`/`CAN_TRANSFER_TO` edge; every
warehouse additionally connects to every donor-capable facility in its own state (a warehouse is
the cross-district supply hub). Distance is real great-circle (haversine) distance when both
facilities have a recorded lat/lng (OPS-01's `location` field); falls back to a deterministic
hash of the pair's IDs only when one or both coordinates are missing — still not a real road
routing model (no road network data exists), but no longer fabricated when real coordinates exist.
"""

import hashlib
import math
import uuid
from collections import defaultdict

from sqlalchemy.orm import Session

from backend.intelligence import ports
from backend.intelligence.graph.session import run_cypher
from backend.ops import models

EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _synthetic_distance(id_a: str, id_b: str, *, low: float, high: float) -> float:
    key = ":".join(sorted((str(id_a), str(id_b))))
    digest = hashlib.sha256(key.encode()).hexdigest()
    fraction = (int(digest, 16) % 10_000) / 10_000
    return round(low + fraction * (high - low), 1)


def _distance_km(a: models.Facility, b: models.Facility, *, low: float, high: float) -> float:
    if a.latitude is not None and a.longitude is not None and b.latitude is not None and b.longitude is not None:
        return round(_haversine_km(a.latitude, a.longitude, b.latitude, b.longitude), 1)
    return _synthetic_distance(a.id, b.id, low=low, high=high)


def sync_graph_from_ops(db: Session) -> None:
    run_cypher(db, "MATCH (n) DETACH DELETE n", columns=("result",))

    facilities = db.query(models.Facility).all()
    districts = ports.list_districts(db)
    states = ports.list_states(db)
    countries = ports.list_countries(db)

    for f in facilities:
        run_cypher(
            db,
            "CREATE (:Facility {id: $id, type: $type, districtId: $districtId, "
            "stateId: $stateId, countryId: $countryId, latitude: $latitude, longitude: $longitude})",
            {
                "id": str(f.id),
                "type": f.type.value,
                "districtId": str(f.district_id),
                "stateId": str(f.state_id),
                "countryId": str(f.country_id),
                "latitude": f.latitude,
                "longitude": f.longitude,
            },
            columns=("result",),
        )

    for d in districts:
        run_cypher(db, "CREATE (:AuthorityLevel {id: $id, level: $level})", {"id": str(d.id), "level": "DISTRICT"}, columns=("result",))
    for s in states:
        run_cypher(db, "CREATE (:AuthorityLevel {id: $id, level: $level})", {"id": str(s.id), "level": "STATE"}, columns=("result",))
    for c in countries:
        run_cypher(db, "CREATE (:AuthorityLevel {id: $id, level: $level})", {"id": str(c.id), "level": "NATIONAL"}, columns=("result",))

    # ADMIN_PARENT: facility -> district, district -> state, state -> national.
    for f in facilities:
        run_cypher(
            db,
            "MATCH (a:Facility {id: $facilityId}), (b:AuthorityLevel {id: $districtId}) "
            "CREATE (a)-[:ADMIN_PARENT]->(b)",
            {"facilityId": str(f.id), "districtId": str(f.district_id)},
            columns=("result",),
        )
    for d in districts:
        run_cypher(
            db,
            "MATCH (a:AuthorityLevel {id: $districtId, level: 'DISTRICT'}), "
            "(b:AuthorityLevel {id: $stateId, level: 'STATE'}) CREATE (a)-[:ADMIN_PARENT]->(b)",
            {"districtId": str(d.id), "stateId": str(d.state_id)},
            columns=("result",),
        )
    state_country = {s.id: s.country_id for s in states}
    for s in states:
        run_cypher(
            db,
            "MATCH (a:AuthorityLevel {id: $stateId, level: 'STATE'}), "
            "(b:AuthorityLevel {id: $countryId, level: 'NATIONAL'}) CREATE (a)-[:ADMIN_PARENT]->(b)",
            {"stateId": str(s.id), "countryId": str(state_country[s.id])},
            columns=("result",),
        )

    # COMMAND_TO: mirrors ADMIN_PARENT but pointed downward — the authority commands its unit.
    for f in facilities:
        run_cypher(
            db,
            "MATCH (a:AuthorityLevel {id: $districtId, level: 'DISTRICT'}), (b:Facility {id: $facilityId}) "
            "CREATE (a)-[:COMMAND_TO]->(b)",
            {"districtId": str(f.district_id), "facilityId": str(f.id)},
            columns=("result",),
        )
    for d in districts:
        run_cypher(
            db,
            "MATCH (a:AuthorityLevel {id: $stateId, level: 'STATE'}), "
            "(b:AuthorityLevel {id: $districtId, level: 'DISTRICT'}) CREATE (a)-[:COMMAND_TO]->(b)",
            {"stateId": str(d.state_id), "districtId": str(d.id)},
            columns=("result",),
        )
    for s in states:
        run_cypher(
            db,
            "MATCH (a:AuthorityLevel {id: $countryId, level: 'NATIONAL'}), "
            "(b:AuthorityLevel {id: $stateId, level: 'STATE'}) CREATE (a)-[:COMMAND_TO]->(b)",
            {"countryId": str(state_country[s.id]), "stateId": str(s.id)},
            columns=("result",),
        )

    # ESCALATES_TO: district -> state -> national, same chain as ADMIN_PARENT, distinct label.
    for d in districts:
        run_cypher(
            db,
            "MATCH (a:AuthorityLevel {id: $districtId, level: 'DISTRICT'}), "
            "(b:AuthorityLevel {id: $stateId, level: 'STATE'}) CREATE (a)-[:ESCALATES_TO]->(b)",
            {"districtId": str(d.id), "stateId": str(d.state_id)},
            columns=("result",),
        )
    for s in states:
        run_cypher(
            db,
            "MATCH (a:AuthorityLevel {id: $stateId, level: 'STATE'}), "
            "(b:AuthorityLevel {id: $countryId, level: 'NATIONAL'}) CREATE (a)-[:ESCALATES_TO]->(b)",
            {"stateId": str(s.id), "countryId": str(state_country[s.id])},
            columns=("result",),
        )

    _build_supply_routes(db, facilities)


def _build_supply_routes(db: Session, facilities: list[models.Facility]) -> None:
    donors = [f for f in facilities if f.type in ports.DONOR_TYPES]
    by_district: dict[uuid.UUID, list[models.Facility]] = defaultdict(list)
    by_state: dict[uuid.UUID, list[models.Facility]] = defaultdict(list)
    for f in donors:
        by_district[f.district_id].append(f)
        by_state[f.state_id].append(f)
    warehouses = [f for f in donors if f.type == models.FacilityType.WAREHOUSE]

    def link(a: models.Facility, b: models.Facility, *, cross_boundary: bool) -> None:
        if a.id == b.id:
            return
        distance = _distance_km(a, b, low=5, high=40 if not cross_boundary else 150)
        minutes = round(distance * 1.5, 1)
        for src, dst in ((a, b), (b, a)):
            run_cypher(
                db,
                "MATCH (a:Facility {id: $srcId}), (b:Facility {id: $dstId}) "
                "CREATE (a)-[:SUPPLY_ROUTE {distanceKm: $distanceKm, estimatedMinutes: $minutes, "
                "enabled: true, crossBoundary: $crossBoundary}]->(b), (a)-[:CAN_TRANSFER_TO]->(b)",
                {
                    "srcId": str(src.id),
                    "dstId": str(dst.id),
                    "distanceKm": distance,
                    "minutes": minutes,
                    "crossBoundary": cross_boundary,
                },
                columns=("result",),
            )

    seen: set[tuple[uuid.UUID, uuid.UUID]] = set()

    def link_once(a: models.Facility, b: models.Facility, *, cross_boundary: bool) -> None:
        key = tuple(sorted((a.id, b.id), key=str))
        if key in seen or a.id == b.id:
            return
        seen.add(key)
        link(a, b, cross_boundary=cross_boundary)

    for district_facilities in by_district.values():
        for i, a in enumerate(district_facilities):
            for b in district_facilities[i + 1 :]:
                link_once(a, b, cross_boundary=False)

    for wh in warehouses:
        for f in by_state.get(wh.state_id, []):
            link_once(wh, f, cross_boundary=f.district_id != wh.district_id)
