from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.db import get_db
from backend.ops import models
from backend.ops.deps import CurrentUser, get_current_user
from backend.ops.schemas import Product

router = APIRouter(tags=["products"])


@router.get("/products", response_model=list[Product])
def list_products(
    db: Session = Depends(get_db),
    _user: CurrentUser = Depends(get_current_user),
) -> list[Product]:
    """Added by Direction 1: the product catalog itself — nothing in the original OPS-09 surface
    exposed valid productIds, so a client had no way to know what to pass into an inventory
    transaction (OPS-04) without this."""
    return [Product(id=str(p.id), name=p.name, unit=p.unit) for p in db.query(models.Product).all()]
