"""Network-structure questions that `graph/queries.py`'s reachability/ranking primitives don't
answer: which facilities does the supply network actually depend on structurally, and which ones
are single points of failure? Both are graph-topology properties (betweenness centrality, cut
vertices) with no sensible openCypher formulation, so the persisted graph is pulled into an
in-memory `networkx.Graph` and analyzed there instead. `SUPPLY_ROUTE` edges are always created in
both directions for a pair (`graph/build.py`'s `_build_supply_routes`), so the graph is treated as
undirected here.
"""

import networkx as nx
from sqlalchemy.orm import Session

from backend.intelligence.graph.session import run_cypher


def _supply_route_graph(db: Session) -> nx.Graph:
    facility_rows = run_cypher(db, "MATCH (f:Facility) RETURN f.id", columns=("facilityId",))
    edge_rows = run_cypher(
        db,
        "MATCH (a:Facility)-[:SUPPLY_ROUTE]->(b:Facility) RETURN a.id, b.id",
        columns=("sourceId", "destId"),
    )
    graph = nx.Graph()
    graph.add_nodes_from(row[0] for row in facility_rows)
    graph.add_edges_from((source_id, dest_id) for source_id, dest_id in edge_rows)
    return graph


def facility_criticality_scores(db: Session) -> dict[str, float]:
    """Betweenness centrality over the supply-route network — how often a facility sits on the
    shortest path between two other facilities, i.e. how load-bearing it is even though it may
    never appear as a donor or destination itself. Facilities with no route at all still get an
    entry, at 0.0."""
    graph = _supply_route_graph(db)
    scores = {node: 0.0 for node in graph.nodes}
    scores.update(nx.betweenness_centrality(graph))
    return scores


def find_articulation_points(db: Session) -> list[str]:
    """Cut vertices of the supply-route network: facilities whose loss would split their
    component into disconnected pieces. `nx.articulation_points` requires a connected graph, so
    it's run per connected component (single-node and already-disconnected components trivially
    have none)."""
    graph = _supply_route_graph(db)
    cut_vertices: set[str] = set()
    for component in nx.connected_components(graph):
        if len(component) > 1:
            cut_vertices.update(nx.articulation_points(graph.subgraph(component)))
    return sorted(cut_vertices)
