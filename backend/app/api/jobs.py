"""Job Intelligence + Matching explicable (§10-12)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services import email_routing, job_media, job_parser
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
        "domain_id": job.domain_id,
        "specialty_id": job.specialty_id,
        "contract_type": job.contract_type,
        "published_at": job.published_at,
        # Date limite exposée dès la liste : les cartes peuvent afficher
        # une échéance réelle sans requête supplémentaire.
        "deadline": job.deadline,
        "source": {"name": job.source_name, "url": job.source_url},
        "match_score": match_score,
        # Les compétences requises accompagnent la liste : les cartes
        # d'offres peuvent ainsi afficher de vrais mots-clés (§47).
        "required_skills": job.required_skills or [],
        "company_branding": _company_branding(db, job),
        "photo_url": job_media.photo_url(job),
    }


def _job_detail(db: Session, job: models.Job) -> dict:
    return {
        **_job_summary(db, job, None),
        "description": job.description,
        "requirements": job.requirements,
        "required_skills": job.required_skills,
        "deadline": job.deadline,
        "salary": job.salary,
        "apply_channel": job.apply_channel or "",
        "apply_email": job.apply_email,
        "apply_keywords": job.apply_keywords or [],
        "email_reference": email_routing.reference_for(job),
        "email_apply_address": email_routing.inbound_address(db),
        "poster_url": email_routing.public_poster_path(job),
    }


def report_to_dict(report: models.JobReport) -> dict:
    return {
        "id": report.id,
        "job_id": report.job_id,
        "reason": report.reason,
        "details": report.details,
        "status": report.status,
        "admin_note": report.admin_note,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "job_title": report.job.title if report.job else None,
        "company": report.job.company if report.job else None,
    }


@router.get("", response_model=list[schemas.JobSummary])
def list_jobs(
    search: Optional[str] = None,
    sector: Optional[str] = None,
    domain_id: Optional[int] = None,
    specialty_id: Optional[int] = None,
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
    if domain_id is not None:
        query = query.filter(models.Job.domain_id == domain_id)
    if specialty_id is not None:
        query = query.filter(models.Job.specialty_id == specialty_id)
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
    my_report = None
    if user:
        profile = profile_to_dict(get_profile_row(db, user.id), user.id)
        if profile:
            match = compute_match(
                profile.get("skills", []), job.required_skills, load_taxonomy()
            )
        my_report = (
            db.query(models.JobReport)
            .filter(
                models.JobReport.user_id == user.id,
                models.JobReport.job_id == job.id,
            )
            .order_by(models.JobReport.created_at.desc())
            .first()
        )
    return {
        "job": _job_detail(db, job),
        "match": match,
        "my_report": report_to_dict(my_report) if my_report else None,
    }


@router.post("/{job_id}/reports", status_code=201, response_model=schemas.JobReportOut)
def report_job(
    job_id: int,
    payload: schemas.JobReportIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Signale une offre frauduleuse, trompeuse, expirée ou discriminante.

    Le signalement est conservé et traité dans la console d'administration.
    Un même candidat ne peut pas empiler plusieurs signalements ouverts sur
    la même offre : il peut suivre le premier depuis la fiche.
    """
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if user.role not in ("candidate", "recruiter", "admin"):
        raise HTTPException(status_code=403, detail="Signalement réservé aux utilisateurs connectés")
    if payload.reason not in schemas.REPORT_REASONS:
        raise HTTPException(status_code=422, detail="Motif de signalement invalide")
    details = (payload.details or "").strip()
    if len(details) > 2000:
        raise HTTPException(status_code=422, detail="Précisions trop longues (2000 caractères maximum)")
    if payload.reason == "autre" and len(details) < 10:
        raise HTTPException(
            status_code=422,
            detail="Précisez le problème (au moins 10 caractères) pour le motif « Autre ».",
        )
    existing = (
        db.query(models.JobReport)
        .filter(
            models.JobReport.user_id == user.id,
            models.JobReport.job_id == job.id,
            models.JobReport.status.in_(["nouveau", "en_cours"]),
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="Vous avez déjà signalé cette offre. Son traitement est en cours.",
        )
    report = models.JobReport(
        user_id=user.id,
        job_id=job.id,
        reason=payload.reason,
        details=details,
        status="nouveau",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report_to_dict(report)


@router.get("/{job_id}/photo")
def get_job_photo(job_id: int, db: Session = Depends(get_db)):
    """Photo d'illustration de l'offre (facultative, servie sans compte)."""
    job = db.get(models.Job, job_id)
    if job is None or not job.photo_path:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    return FileResponse(job_media.path_for(job))
