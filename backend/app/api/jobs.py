"""Job Intelligence + Matching explicable (§10-12)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services import job_parser
from app.services.matching import compute_match
from app.services.profile_store import get_profile_row, profile_to_dict
from app.services.skills_taxonomy import load_taxonomy

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _company_branding(db: Session, job: models.Job) -> Optional[dict]:
    """Branding de l'entreprise si l'offre est publiée via l'espace recruteur."""
    if not job.company_id:
        return None
    company = db.get(models.Company, job.company_id)
    if company is None:
        return None
    return {
        "id": company.id,
        "name": company.name,
        "sector": company.sector,
        "description": company.description,
        "has_logo": bool(company.logo_path),
    }


def _job_summary(db: Session, job: models.Job, match_score: Optional[int]) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "sector": job.sector,
        "contract_type": job.contract_type,
        "published_at": job.published_at,
        "source": {"name": job.source_name, "url": job.source_url},
        "match_score": match_score,
        "company_branding": _company_branding(db, job),
    }


def _job_detail(db: Session, job: models.Job) -> dict:
    return {
        **_job_summary(db, job, None),
        "description": job.description,
        "requirements": job.requirements,
        "required_skills": job.required_skills,
        "deadline": job.deadline,
        "salary": job.salary,
    }


@router.get("", response_model=list[schemas.JobSummary])
def list_jobs(
    search: Optional[str] = None,
    sector: Optional[str] = None,
    location: Optional[str] = None,
    contract_type: Optional[str] = None,
    min_score: Optional[int] = Query(default=None, ge=0, le=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: Optional[models.User] = Depends(security.get_optional_user),
    db: Session = Depends(get_db),
):
    taxonomy = load_taxonomy()
    profile = profile_to_dict(get_profile_row(db, user.id), user.id) if user else None
    skills = profile.get("skills", []) if profile else []

    query = db.query(models.Job)
    if search:
        needle = f"%{search.lower()}%"
        query = query.filter(
            models.Job.title.ilike(needle)
            | models.Job.company.ilike(needle)
            | models.Job.description.ilike(needle)
        )
    if sector:
        query = query.filter(models.Job.sector.ilike(f"%{sector}%"))
    if location:
        query = query.filter(models.Job.location.ilike(f"%{location}%"))
    if contract_type:
        query = query.filter(models.Job.contract_type == contract_type)
    jobs = query.order_by(models.Job.published_at.desc()).all()

    summaries = []
    for job in jobs:
        score = None
        if profile:
            score = compute_match(skills, job.required_skills, taxonomy)["score"]
        summaries.append((job, score))

    if min_score is not None:
        summaries = [(j, s) for j, s in summaries if s is not None and s >= min_score]
    return [_job_summary(db, j, s) for j, s in summaries[skip: skip + limit]]


@router.post("/parse", response_model=dict)
def parse_job(
    payload: schemas.JobParseIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Aide à la saisie IA : transforme une brève description en offre
    structurée (brouillon à vérifier avant publication). Disponible pour
    les recruteurs et les administrateurs."""
    if user.role not in ("recruiter", "admin"):
        raise HTTPException(status_code=403, detail="Réservé aux recruteurs et administrateurs")
    return job_parser.parse_job_description(payload.description)


@router.get("/{job_id}", response_model=schemas.JobDetailResponse)
def get_job(
    job_id: int,
    user: Optional[models.User] = Depends(security.get_optional_user),
    db: Session = Depends(get_db),
):
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    match = None
    if user:
        profile = profile_to_dict(get_profile_row(db, user.id), user.id)
        if profile:
            match = compute_match(
                profile.get("skills", []), job.required_skills, load_taxonomy()
            )
    return {"job": _job_detail(db, job), "match": match}
