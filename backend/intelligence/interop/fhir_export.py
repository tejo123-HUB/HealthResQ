"""Read-only HL7 FHIR R4 export surface, for external/government health-platform integration —
this is an export endpoint, not a FHIR server (no `_search` parameters, no write operations, no
full resource-type coverage). Exports OPS-01 facilities as FHIR R4 `Location` resources wrapped in
a `Bundle`, the standard shape an external system consuming a facility registry over FHIR expects.

Hand-rolled JSON rather than the `fhir.resources` PyPI package: its current major version (8.x)
defaults to FHIR R5 and only ships an R4B variant (a later technical-correction release, not
identical to R4 4.0.1) — genuine R4 support was dropped after v6.x, which is old enough to need a
Pydantic v1-era release that would conflict with this project's Pydantic v2 pin. The shape needed
here (resourceType, id, status, name, position, physicalType) is small enough that hand-rolling it
directly against the published spec (hl7.org/fhir/R4/location.html) is safer than fighting that
dependency conflict.

`status` is hardcoded to `"active"` for every facility — OPS-01 has no facility-status column to
reflect a real inactive/suspended state, so this isn't derived from anything; a reader shouldn't
assume it means the facility was actually checked.
"""

from backend.ops import models

_PHYSICAL_TYPE = {
    models.FacilityType.PHC: ("bu", "Building"),
    models.FacilityType.SHC: ("bu", "Building"),
    models.FacilityType.WAREHOUSE: ("bu", "Building"),
    models.FacilityType.REFERRAL_HOSPITAL: ("bu", "Building"),
}

# FHIR extensions are identified by a canonical URL under the defining organization's own domain —
# this project has no real registered domain, so it uses the IETF-reserved example domain
# (RFC 2606), the same convention most published FHIR implementation guides use during development.
_FACILITY_TYPE_EXTENSION_URL = "https://healthresq.example.org/fhir/StructureDefinition/facility-type"


def _facility_to_fhir_location(facility: models.Facility) -> dict:
    code, display = _PHYSICAL_TYPE[facility.type]
    location = {
        "resourceType": "Location",
        "id": str(facility.id),
        "status": "active",
        "name": facility.name,
        "physicalType": {
            "coding": [
                {
                    "system": "http://terminology.hl7.org/CodeSystem/location-physical-type",
                    "code": code,
                    "display": display,
                }
            ]
        },
        "extension": [{"url": _FACILITY_TYPE_EXTENSION_URL, "valueCode": facility.type.value}],
    }
    if facility.latitude is not None and facility.longitude is not None:
        location["position"] = {"latitude": facility.latitude, "longitude": facility.longitude}
    return location


def export_locations_bundle(facilities: list[models.Facility]) -> dict:
    """A minimal valid FHIR R4 `Bundle` of type `collection` — required fields only
    (`resourceType`, `type`, `entry[].resource`); `total` is included as a convenience, not a
    `searchset`-only requirement."""
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "total": len(facilities),
        "entry": [{"resource": _facility_to_fhir_location(f)} for f in facilities],
    }
