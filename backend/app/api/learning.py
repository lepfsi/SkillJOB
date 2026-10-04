"""Learning & Upskilling (§19) : plan personnalisé (métiers recommandés,
perfectionnement du domaine, écarts) + progression vérifiable."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services.learning import learning_plan
from app.services.profile_store import get_profile_row, profile_to_dict
from app.services.skills_taxonomy import load_taxonomy

router = APIRouter(prefix="/api/learning", tags=["learning"])


@router.get("", response_model=schemas.LearningOut)
def learning(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    if not profile:
        return {"learn_now": [], "improve": [], "learn_next": [], "progress": []}
    jobs = db.query(models.Job).all()
    careers = db.query(models.Career).all()
    return learning_plan(profile, jobs, load_taxonomy(), careers=careers)
