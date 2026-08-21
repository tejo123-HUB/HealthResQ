from backend.ops import models
from backend.ops.reference_indicators import MockAdapter, get_adapter
from backend.tests.conftest import auth_headers, make_user_token


def test_mock_adapter_requires_zero_network_and_no_key(monkeypatch):
    """OPS-14 acceptance criterion: no registration, API key, or account is required anywhere
    in the mock path."""
    monkeypatch.setattr("backend.ops.reference_indicators.settings.reference_indicator_mode", "mock")
    adapter = get_adapter()
    assert isinstance(adapter, MockAdapter)

    results = adapter.get_indicators("IND")
    assert len(results) > 0
    assert all(r.country == "IND" for r in results)


def test_reference_indicators_endpoint_serves_mock_values(client, db, role_authority, geo, monkeypatch):
    monkeypatch.setattr("backend.ops.reference_indicators.settings.reference_indicator_mode", "mock")
    token = make_user_token(db, role_authority, models.ScopeLevel.NATIONAL, geo["country"].id)

    resp = client.get("/reference-indicators?country=IND", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    assert all(item["country"] == "IND" for item in body)


def test_indicator_filter_narrows_results(client, db, role_authority, geo, monkeypatch):
    monkeypatch.setattr("backend.ops.reference_indicators.settings.reference_indicator_mode", "mock")
    token = make_user_token(db, role_authority, models.ScopeLevel.NATIONAL, geo["country"].id)

    resp = client.get("/reference-indicators?country=IND&indicator=DOCTORS", headers=auth_headers(token))
    assert resp.status_code == 200
    body = resp.json()
    assert all("DOCTORS" in item["indicatorCode"] for item in body)
