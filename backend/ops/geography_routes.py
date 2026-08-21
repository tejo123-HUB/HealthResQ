from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, get_current_user
from backend.ops.schemas import Country, District, State

router = APIRouter(tags=["geography"])


def _district_out(district: models.District, *, facility_filter=None) -> District:
    facilities = district.facilities
    if facility_filter is not None:
        facilities = [f for f in facilities if facility_filter(f)]
    return District(id=str(district.id), name=district.name, facility_ids=[str(f.id) for f in facilities])


def _state_out(state: models.State, *, district_filter=None, facility_filter=None) -> State:
    districts = state.districts
    if district_filter is not None:
        districts = [d for d in districts if district_filter(d)]
    return State(
        id=str(state.id),
        name=state.name,
        districts=[_district_out(d, facility_filter=facility_filter) for d in districts],
    )


def _country_out(country: models.Country, *, state_filter=None, district_filter=None, facility_filter=None) -> Country:
    states = country.states
    if state_filter is not None:
        states = [s for s in states if state_filter(s)]
    return Country(
        id=str(country.id),
        name=country.name,
        states=[_state_out(s, district_filter=district_filter, facility_filter=facility_filter) for s in states],
    )


@router.get("/geography/hierarchy", response_model=list[Country])
def get_hierarchy(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[Country]:
    """OPS-01/OPS-02: every facility resolves to exactly one Country/State/District chain, and
    the response never crosses the caller's own scope branch — a FACILITY/DISTRICT/STATE-scoped
    user sees only their own subtree (kept nested under its ancestors for breadcrumb context); a
    NATIONAL-scoped user sees only their own country, since the federation demo topology means
    more than one `countries` row can legitimately exist in this single database."""
    countries = (
        db.query(models.Country)
        .options(
            selectinload(models.Country.states)
            .selectinload(models.State.districts)
            .selectinload(models.District.facilities)
        )
        .all()
    )

    level, scope_id = user.scope_level, user.scope_id

    if level == models.ScopeLevel.NATIONAL:
        countries = [c for c in countries if c.id == scope_id]
        return [_country_out(c) for c in countries]

    if level == models.ScopeLevel.STATE:
        for country in countries:
            match = next((s for s in country.states if s.id == scope_id), None)
            if match is not None:
                return [_country_out(country, state_filter=lambda s: s.id == scope_id)]
        return []

    if level == models.ScopeLevel.DISTRICT:
        for country in countries:
            for state in country.states:
                if any(d.id == scope_id for d in state.districts):
                    return [
                        _country_out(
                            country,
                            state_filter=lambda s: s.id == state.id,
                            district_filter=lambda d: d.id == scope_id,
                        )
                    ]
        return []

    # FACILITY
    for country in countries:
        for state in country.states:
            for district in state.districts:
                if any(f.id == scope_id for f in district.facilities):
                    return [
                        _country_out(
                            country,
                            state_filter=lambda s: s.id == state.id,
                            district_filter=lambda d: d.id == district.id,
                            facility_filter=lambda f: f.id == scope_id,
                        )
                    ]
    return []
