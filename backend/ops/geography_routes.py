from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, get_current_user
from backend.ops.schemas import Country, District, State

router = APIRouter(tags=["geography"])


@router.get("/geography/hierarchy", response_model=list[Country])
def get_hierarchy(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> list[Country]:
    """OPS-01: every facility resolves to exactly one Country/State/District chain. Scope
    filtering isn't applied here — the hierarchy shape itself is not facility-level data — but
    every other OPS-09 endpoint enforces OPS-02 scope on the data it actually returns."""
    countries = (
        db.query(models.Country)
        .options(
            selectinload(models.Country.states)
            .selectinload(models.State.districts)
            .selectinload(models.District.facilities)
        )
        .all()
    )

    return [
        Country(
            id=str(country.id),
            name=country.name,
            states=[
                State(
                    id=str(state.id),
                    name=state.name,
                    districts=[
                        District(
                            id=str(district.id),
                            name=district.name,
                            facility_ids=[str(f.id) for f in district.facilities],
                        )
                        for district in state.districts
                    ],
                )
                for state in country.states
            ],
        )
        for country in countries
    ]
