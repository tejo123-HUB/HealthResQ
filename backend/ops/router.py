from fastapi import APIRouter

from backend.ops import (
    auth_routes,
    capacity_routes,
    facilities_routes,
    footfall_routes,
    geography_routes,
    hms_routes,
    instructions_routes,
    inventory_routes,
    products_routes,
    reference_indicators,
    warehouses_routes,
)

router = APIRouter()

for module in (
    auth_routes,
    geography_routes,
    facilities_routes,
    footfall_routes,
    products_routes,
    inventory_routes,
    capacity_routes,
    instructions_routes,
    warehouses_routes,
    hms_routes,
    reference_indicators,
):
    router.include_router(module.router)
