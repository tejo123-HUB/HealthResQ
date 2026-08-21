"""INT-13: H3 hexagonal binning of the risk map, for a regional/geographic rollup that a flat
per-facility marker list can't give directly — "what's the worst severity in this area" answered
by a fixed geographic grid cell, not an ad-hoc district/state administrative boundary (a state can
span a huge area with sparse facilities in one corner and dense ones in another; a hex grid rolls
up by actual geographic proximity instead).

Resolution 5 (~9.85km average edge length) is the project's default — fine enough to separate
sub-state regions without exploding cell count at this prototype's facility density; callers can
override for a coarser (lower number) or finer (higher number) view.

Facilities with no recorded `location` (OPS-01's lat/lng columns are nullable) are skipped — there
is no cell to bin them into, and guessing one would misrepresent real geography."""

import h3
from sqlalchemy.orm import Session

from backend.intelligence.visualization import risk_map

DEFAULT_RESOLUTION = 5
_SEVERITY_RANK = {"NORMAL": 0, "WATCH": 1, "HIGH": 2, "CRITICAL": 3}


def get_hex_map(db: Session, scope_level: str, scope_id: str, *, resolution: int = DEFAULT_RESOLUTION) -> list[dict]:
    markers = risk_map.get_risk_map(db, scope_level, scope_id)
    by_cell: dict[str, list[dict]] = {}
    for marker in markers:
        location = marker.get("location")
        if location is None:
            continue
        cell = h3.latlng_to_cell(location["lat"], location["lng"], resolution)
        by_cell.setdefault(cell, []).append(marker)

    hexes = []
    for cell, cell_markers in by_cell.items():
        worst = max(cell_markers, key=lambda m: _SEVERITY_RANK[m["worstSeverity"]])["worstSeverity"]
        boundary = [{"lat": lat, "lng": lng} for lat, lng in h3.cell_to_boundary(cell)]
        hexes.append(
            {
                "hexId": cell,
                "resolution": resolution,
                "facilityCount": len(cell_markers),
                "facilityIds": [m["facilityId"] for m in cell_markers],
                "worstSeverity": worst,
                "boundary": boundary,
            }
        )
    return hexes
