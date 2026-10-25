"""Candidatures : mini-ATS personnel (contrat §6)."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services.applications import STATUS_LABELS as _STATUS_LABELS

router = APIRouter(prefix="/api/applications", tags=["applications"])


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
        "apply_channel": app.apply_channel or "",
        "submitted_at": app.submitted_at,
        "cover_note": app.cover_note or "",
        "apply_instructions": job.apply_instructions or "",
        "apply_email": job.apply_email or "",
        "apply_url": job.source_url or "",
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


def _job_channel(db: Session, job: models.Job) -> str:
    """Canal de candidature : « platform » si un recruteur OrientSkill AI
    est rattaché à l'offre (compte actif), sinon « external »."""
    if job.apply_channel:
        return job.apply_channel
    if job.company_id:
        company = db.get(models.Company, job.company_id)
        if company is not None:
            owner = db.get(models.User, company.owner_user_id)
            if owner is not None and owner.role == "recruiter":
                return "platform"
    return "external"


def _notify_recruiter(db: Session, user: models.User, job: models.Job,
                      application: models.Application, cv_title: str,
                      letter_title: str) -> None:
    """Prévient le recruteur par messagerie interne (canal plateforme).

    Le recruteur retrouve le CV et la lettre dans son espace : la réponse
    repart au candidat via la même messagerie, l'échange reste tracé.
    """
    from app.services.profile_store import get_profile_row, profile_to_dict

    company = db.get(models.Company, job.company_id) if job.company_id else None
    if company is None:
        return
    recruiter = db.get(models.User, company.owner_user_id)
    if recruiter is None or recruiter.role != "recruiter":
        return
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    headline = (profile or {}).get("title") or "Candidat OrientSkill AI"
    lines = [
        f"Nouvelle candidature pour « {job.title} ».",
        f"Candidat : {user.full_name} · {headline}",
        f"CV : {cv_title}",
    ]
    if letter_title:
        lines.append(f"Lettre : {letter_title}")
    if application.cover_note:
        lines.append(f"Message du candidat : {application.cover_note}")
    lines.append("Répondez depuis la messagerie OrientSkill AI : votre réponse "
                 "ira directement au candidat.")
    db.add(models.Message(
        sender_id=user.id,
        recipient_id=recruiter.id,
        body="\n".join(lines),
        job_id=job.id,
    ))


def _send_external_application(db: Session, user: models.User, job: models.Job,
                               cv: models.Document,
                               letter: Optional[models.Document],
                               note: str) -> tuple[bool, str]:
    """Transmet la candidature au publieur par e-mail (CV + lettre PDF).

    L'expéditeur est la plateforme, la réponse est adressée au candidat
    (``Reply-To``) : le recruteur externe répond directement chez lui.
    Un échec ne casse jamais la soumission ; la candidature reste tracée
    et le candidat peut finaliser via les instructions du publieur.
    """
    from app.services import notifications
    from app.services.document_pdf import build_document_pdf, safe_pdf_filename

    if not job.apply_email:
        return False, "Aucune adresse de candidature renseignée."

    attachments: list[tuple[str, bytes]] = []
    cv_bytes = build_document_pdf(db, cv, user)
    if cv_bytes:
        attachments.append((safe_pdf_filename(cv.title), cv_bytes))
    if letter is not None:
        letter_bytes = build_document_pdf(db, letter, user)
        if letter_bytes:
            attachments.append((safe_pdf_filename(letter.title), letter_bytes))

    lines = [
        "Bonjour,",
        "",
        f"Une candidature a été déposée via OrientSkill AI pour l'offre "
        f"« {job.title} ».",
        f"Candidat : {user.full_name}",
    ]
    if note:
        lines += ["", "Message du candidat :", note]
    if job.source_url:
        lines += ["", f"Offre : {job.source_url}"]
    lines += [
        "",
        "Le CV" + (" et la lettre sont joints" if letter else " est joint")
        + " en PDF.",
        "Répondez à cet e-mail : la réponse parvient directement à "
        f"{user.full_name} ({user.email}).",
        "",
        "Message envoyé automatiquement par OrientSkill AI.",
    ]
    return notifications.send_application_email(
        db,
        job.apply_email,
        f"Candidature : {job.title} - {user.full_name}",
        "\n".join(lines),
        reply_to=user.email,
        attachments=attachments,
    )


@router.post("/jobs/{job_id}/submit", response_model=schemas.ApplicationOut)
def submit_application(
    job_id: int,
    payload: schemas.ApplicationSubmitIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Soumission RÉELLE de la candidature (bouton « Soumettre ma candidature »).

    - Canal « platform » (offre publiée par un recruteur OrientSkill AI) :
      les documents sont transmis au recruteur via la messagerie interne,
      il répond directement au candidat, l'échange reste tracé.
    - Canal « external » avec adresse de candidature (« apply_email ») :
      OrientSkill AI transmet elle-même la candidature par e-mail au
      publieur, CV et lettre en PDF, avec réponse adressée au candidat.
      Sans adresse ou sans SMTP configuré, la candidature est horodatée
      et le candidat suit les instructions du publieur (URL, e-mail).

    Le CV doit appartenir au candidat ; la lettre est facultative.
    """
    from datetime import timezone as _tz

    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")

    # ---- Documents transmis : vérifiés, jamais inventés (§47)
    cv = db.get(models.Document, payload.cv_document_id)
    if cv is None or cv.user_id != user.id or cv.kind != "cv":
        raise HTTPException(
            status_code=422,
            detail="CV invalide : choisissez un CV de votre bibliothèque.",
        )
    letter = None
    if payload.cover_letter_document_id:
        letter = db.get(models.Document, payload.cover_letter_document_id)
        if letter is None or letter.user_id != user.id or letter.kind != "cover_letter":
            raise HTTPException(
                status_code=422,
                detail="Lettre invalide : choisissez une lettre de votre bibliothèque.",
            )

    note = (payload.cover_note or "").strip()[:2000]
    channel = _job_channel(db, job)

    # ---- Application : mise à jour ou création directe en « envoyee »
    app = (
        db.query(models.Application)
        .filter(models.Application.user_id == user.id, models.Application.job_id == job.id)
        .first()
    )
    sent_doc_ids = [cv.id] + ([letter.id] if letter else [])
    now_iso = _now_iso()
    if app is None:
        app = models.Application(
            user_id=user.id,
            job_id=job.id,
            status="envoyee",
            timeline=[{"at": now_iso, "event": _STATUS_LABELS["identifiee"]}],
        )
        db.add(app)
    else:
        if app.submitted_at is not None:
            raise HTTPException(
                status_code=400,
                detail="Candidature déjà envoyée pour cette offre.",
            )
        app.status = "envoyee"
    app.apply_channel = channel
    app.submitted_at = datetime.now(_tz.utc).replace(tzinfo=None)
    app.submitted_documents = sent_doc_ids
    app.cover_note = note

    if channel == "platform":
        event = "Candidature envoyée via OrientSkill AI au recruteur"
    else:
        sent, _detail = _send_external_application(
            db, user, job, cv, letter, note
        )
        if sent:
            event = (
                "Candidature transmise automatiquement par e-mail "
                f"à {job.apply_email}"
            )
        else:
            event = (
                "Candidature enregistrée ; transmission automatique non "
                "effectuée. Suivez les instructions du publieur."
            )
    timeline = list(app.timeline or [])
    timeline.append({"at": now_iso, "event": event})
    app.timeline = timeline

    # ---- Notification recruteur (canal plateforme uniquement)
    if channel == "platform":
        _notify_recruiter(db, user, job, app, cv.title, letter.title if letter else "")

    db.commit()
    db.refresh(app)
    documents = (
        db.query(models.Document)
        .filter(models.Document.user_id == user.id, models.Document.job_id == app.job_id)
        .all()
    )
    return _to_out(app, documents)


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
