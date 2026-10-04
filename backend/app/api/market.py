"""Marché : tendances déterministes calculées sur les offres (§13)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services.market import market_trends

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/trends", response_model=schemas.MarketTrendsOut)
def trends(db: Session = Depends(get_db)):
    return market_trends(db.query(models.Job).all())
