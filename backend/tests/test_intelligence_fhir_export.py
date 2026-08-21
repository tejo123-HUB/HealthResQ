from backend.intelligence.interop.fhir_export import export_locations_bundle
from backend.ops import models
from backend.tests.conftest import make_facility


def test_bundle_is_minimally_valid_fhir_r4(db, geo):
    facility = make_facility(
        db, geo, name="PHC-FHIR-A", ftype=models.FacilityType.PHC, district=geo["district_a"],
        latitude=16.5, longitude=80.6,
    )
    bundle = export_locations_bundle([facility])

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert bundle["total"] == 1
    location = bundle["entry"][0]["resource"]
    assert location["resourceType"] == "Location"
    assert location["id"] == str(facility.id)
    assert location["status"] == "active"
    assert location["position"] == {"latitude": 16.5, "longitude": 80.6}
    assert location["physicalType"]["coding"][0]["code"] == "bu"


def test_facility_without_coordinates_omits_position(db, geo):
    facility = make_facility(db, geo, name="PHC-FHIR-NoCoords", ftype=models.FacilityType.SHC, district=geo["district_a"])
    bundle = export_locations_bundle([facility])
    location = bundle["entry"][0]["resource"]
    assert "position" not in location


def test_empty_facility_list_gives_empty_bundle():
    bundle = export_locations_bundle([])
    assert bundle == {"resourceType": "Bundle", "type": "collection", "total": 0, "entry": []}
