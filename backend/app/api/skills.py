"""Compétences : taxonomie + demande marché (§8, §13)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.services.skills_taxonomy import load_taxonomy
from app.services.market import skills_market

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("/taxonomy", response_model=list[schemas.SkillTaxonomyEntry])
def taxonomy():
    return load_taxonomy().all_entries()


@router.get("/market", response_model=list[schemas.SkillMarketEntry])
def market(db: Session = Depends(get_db)):
    jobs = db.query(models.Job).all()
    return skills_market(jobs)
