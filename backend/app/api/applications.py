"""Candidatures : mini-ATS personnel (contrat §6)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db

router = APIRouter(prefix="/api/applications", tags=["applications"])

_STATUS_LABELS = {
    "identifiee": "Candidature identifiée",
    "cv_prepare": "CV ciblé préparé",
    "envoyee": "Candidature envoyée",
    "en_attente": "En attente de réponse",
    "entretien": "Entretien à préparer",
    "offre": "Offre reçue",
    "acceptee": "Candidature acceptée",
    "refusee": "Candidature refusée",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _to_out(app: models.Application, documents: list[models.Document]) -> dict:
    job = app.job
    return {
        "id": app.id,
        "user_id": app.user_id,
        "job_id": app.job_id,
        "job": {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "sector": job.sector,
            "contract_type": job.contract_type,
            "published_at": job.published_at,
            "source": {"name": job.source_name, "url": job.source_url},
            "match_score": None,
        },
        "status": app.status,
        "timeline": app.timeline or [],
        "documents": [
            {"id": d.id, "kind": d.kind, "title": d.title} for d in documents
        ],
    }


@router.get("", response_model=list[schemas.ApplicationOut])
def list_applications(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    apps = (
        db.query(models.Application)
        .filter(models.Application.user_id == user.id)
        .order_by(models.Application.created_at.desc())
        .offset(skip).limit(limit)
        .all()
    )
    return [
        _to_out(
            app,
            db.query(models.Document)
            .filter(
                models.Document.user_id == user.id,
                models.Document.job_id == app.job_id,
            )
            .all(),
        )
        for app in apps
    ]


@router.post("", status_code=201, response_model=schemas.ApplicationOut)
def create_application(
    payload: schemas.ApplicationCreateIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    job = db.get(models.Job, payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    existing = (
        db.query(models.Application)
        .filter(
            models.Application.user_id == user.id,
            models.Application.job_id == payload.job_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Candidature déjà suivie pour cette offre")
    app = models.Application(
        user_id=user.id,
        job_id=payload.job_id,
        status="identifiee",
        timeline=[{"at": _now_iso(), "event": _STATUS_LABELS["identifiee"]}],
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return _to_out(app, [])


@router.patch("/{application_id}", response_model=schemas.ApplicationOut)
def update_application(
    application_id: int,
    payload: schemas.ApplicationStatusIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if payload.status not in schemas.APPLICATION_STATUSES:
        raise HTTPException(status_code=422, detail="Statut de candidature invalide")
    app = db.get(models.Application, application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    if app.user_id != user.id:
        raise HTTPException(status_code=403, detail="Accès interdit")

    app.status = payload.status
    timeline = list(app.timeline or [])
    timeline.append({"at": _now_iso(), "event": _STATUS_LABELS[payload.status]})
    app.timeline = timeline
    db.commit()
    db.refresh(app)
    documents = (
        db.query(models.Document)
        .filter(models.Document.user_id == user.id, models.Document.job_id == app.job_id)
        .all()
    )
    return _to_out(app, documents)
