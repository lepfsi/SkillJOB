"""Learning & Upskilling (§19) : plan personnalisé (métiers recommandés,
perfectionnement du domaine, écarts) + formations suivies et leurs preuves.

Le parcours réel d'un jeune : il ouvre une formation recommandée (lien
vérifié), déclare son avancement, fournit sa preuve (certificat,
attestation, badge, portfolio) : et décide de la faire figurer dans son
profil, où elle devient une expérience vérifiable par les recruteurs.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services import learning_tracking as tracking
from app.services.learning import learning_plan, visible_resources
from app.services.profile_store import get_profile_row, profile_to_dict, save_profile
from app.services.skills_taxonomy import load_taxonomy

router = APIRouter(prefix="/api/learning", tags=["learning"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _enrollments(db: Session, user_id: int) -> list[models.LearningEnrollment]:
    return (
        db.query(models.LearningEnrollment)
        .filter(models.LearningEnrollment.user_id == user_id)
        .order_by(models.LearningEnrollment.updated_at.desc())
        .all()
    )


def _stats(rows: list[models.LearningEnrollment]) -> dict:
    return {
        "total": len(rows),
        "in_progress": sum(1 for r in rows if r.status != "terminee"),
        "completed": sum(1 for r in rows if r.status == "terminee"),
        "verifiable": sum(1 for r in rows if tracking.is_verifiable(r)),
        "added_to_profile": sum(1 for r in rows if r.added_to_profile),
    }


def _reference_of(db: Session, user_id: int, enrollment_id: int) -> models.LearningEnrollment:
    row = db.get(models.LearningEnrollment, enrollment_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="Formation suivie introuvable.")
    return row


@router.get("", response_model=schemas.LearningOut)
def learning(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    rows = _enrollments(db, user.id)
    context = {
        "enrollments": [tracking.to_dict(r) for r in rows],
        "stats": _stats(rows),
        "proof_kinds": [
            {"value": kind, "label": tracking.PROOF_LABELS[kind]}
            for kind in tracking.PROOF_KINDS
        ],
        "link_kinds": [
            {"value": kind, "label": tracking.LINK_KIND_LABELS[kind]}
            for kind in tracking.LINK_KINDS
        ],
        "statuses": [
            {"value": status, "label": tracking.STATUS_LABELS[status]}
            for status in tracking.ENROLLMENT_STATUSES
        ],
    }
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    if not profile:
        return {
            "learn_now": [], "improve": [], "learn_next": [], "progress": [],
            **context,
        }
    jobs = db.query(models.Job).all()
    careers = db.query(models.Career).all()
    plan = learning_plan(
        profile, jobs, load_taxonomy(), careers=careers, enrollments=rows,
        resources_map=visible_resources(db),
    )
    return {**plan, **context}


@router.post("/enrollments", response_model=schemas.EnrollmentOut, status_code=201)
def enroll(
    payload: schemas.EnrollmentIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Ouvre le suivi d'une formation réelle (idempotent : pas de doublon
    pour la même compétence et le même intitulé)."""
    skill = load_taxonomy().canonical(payload.skill) or payload.skill
    existing = (
        db.query(models.LearningEnrollment)
        .filter(
            models.LearningEnrollment.user_id == user.id,
            models.LearningEnrollment.skill == skill,
            models.LearningEnrollment.title == payload.title,
        )
        .first()
    )
    if existing is not None:
        if payload.url and existing.url != payload.url:
            existing.url = payload.url
            existing.link_kind = payload.link_kind
        existing.updated_at = _now()
        db.commit()
        db.refresh(existing)
        return tracking.to_dict(existing)

    row = models.LearningEnrollment(
        user_id=user.id,
        skill=skill,
        title=payload.title,
        provider=payload.provider,
        url=payload.url,
        kind=payload.kind,
        link_kind=payload.link_kind,
        status="commencee",
        started_at=_now(),
        updated_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return tracking.to_dict(row)


@router.patch("/enrollments/{enrollment_id}", response_model=schemas.EnrollmentOut)
def update_enrollment(
    enrollment_id: int,
    payload: schemas.EnrollmentPatch,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Avancement et pièce déclarés par le candidat (aucune preuve inventée)."""
    row = _reference_of(db, user.id, enrollment_id)
    data = payload.model_dump(exclude_unset=True)

    status = data.get("status")
    if status:
        row.status = status
        row.completed_at = _now() if status == "terminee" else None
    for field in ("proof_kind", "proof_reference", "proof_note"):
        if field in data and data[field] is not None:
            setattr(row, field, data[field].strip() if isinstance(data[field], str) else data[field])

    if row.status == "terminee" and row.proof_kind in tracking.PROOF_NEEDS_REFERENCE \
            and not (row.proof_reference or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Indiquez la référence de la pièce : lien du certificat, "
                   "numéro du badge ou référence de l'attestation.",
        )

    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return tracking.to_dict(row)


@router.delete("/enrollments/{enrollment_id}")
def delete_enrollment(
    enrollment_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Retire une formation du suivi (les preuves déjà ajoutées au profil
    restent au profil : elles ont été validées par le candidat)."""
    row = _reference_of(db, user.id, enrollment_id)
    db.delete(row)
    db.commit()
    return {"deleted": True, "id": enrollment_id}


@router.post(
    "/enrollments/{enrollment_id}/to-profile",
    response_model=schemas.EnrollmentToProfileOut,
)
def enrollment_to_profile(
    enrollment_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Validation humaine (§47) : la formation terminée AVEC sa preuve
    devient une expérience (et une certification) du profil maître."""
    row = _reference_of(db, user.id, enrollment_id)
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Construisez d'abord votre profil : la formation viendra s'y rattacher.",
        )
    if not tracking.is_verifiable(row):
        raise HTTPException(
            status_code=400,
            detail="Marquez la formation comme terminée et fournissez la preuve "
                   "(certificat, attestation, badge ou portfolio) : c'est elle "
                   "qui rend l'expérience vérifiable.",
        )

    saved = save_profile(db, user.id, tracking.profile_payload(row, profile))
    row.added_to_profile = True
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return {
        "enrollment": tracking.to_dict(row),
        "profile": profile_to_dict(saved, user.id),
    }
