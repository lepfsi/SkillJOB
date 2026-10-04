"""Career + Orientation Intelligence (§9, §9bis)."""
import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services.orientation import match_career
from app.services.profile_store import get_profile_row, profile_to_dict
from app.services.skills_taxonomy import load_taxonomy

router = APIRouter(prefix="/api/careers", tags=["careers"])


def _related_jobs(career: models.Career, jobs: list[models.Job], n: int = 3) -> list[dict]:
    """Offres actives liées au métier (mots-clés du titre, tous > 3 lettres)."""
    tokens = [
        t.lower() for t in re.findall(r"[A-Za-zÀ-ÿ]{4,}", career.title)
        if t.lower() not in {"avec", "pour", "dans", "chef", "senior", "junior"}
    ]
    out = []
    for job in jobs:
        hay = f"{job.title} {job.sector}".lower()
        if tokens and any(t in hay for t in tokens):
            out.append({
                "id": job.id,
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "contract_type": job.contract_type,
            })
    return out[:n]


@router.get("", response_model=list[schemas.CareerOut])
def list_careers(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    taxonomy = load_taxonomy()
    profile = profile_to_dict(get_profile_row(db, user.id), user.id) or {}
    skills = profile.get("skills", [])
    jobs = db.query(models.Job).all()

    results = []
    for career in db.query(models.Career).all():
        match = match_career(skills, career, taxonomy)
        results.append({
            "id": career.id,
            "title": career.title,
            "family": career.family,
            "description": career.description,
            "required_skills": career.required_skills,
            "match": {
                "score": match["score"],
                "covered": match["covered"],
                "missing": match["missing"],
                "accessibility": match["accessibility"],
                "recommended_actions": match["recommended_actions"],
            },
            "related_jobs": _related_jobs(career, jobs),
        })
    results.sort(key=lambda c: c["match"]["score"], reverse=True)
    return results
