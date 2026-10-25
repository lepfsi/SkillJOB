"""Candidature publique depuis le lien d'une offre.

Un candidat externe (non inscrit) découvre une offre via son lien public,
saisit nom, e-mail et téléphone : son compte est créé automatiquement, sa
candidature est enregistrée, et ses accès lui sont envoyés par e-mail.
Il complète son profil ensuite (aucune donnée n'est inventée).
"""
import re
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app import config, models, schemas, security
from app.api.jobs import _company_branding
from app.database import get_db
from app.services import (
    email_routing, inbound_email, job_media, notifications, poster,
    settings_store,
)

router = APIRouter(prefix="/api/public", tags=["public"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TEMP_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _temp_password() -> str:
    return "Ori-" + "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(6))


def _apply_channel(db: Session, job: models.Job) -> str:
    """Canal réel : direct plateforme si un recruteur gère l'offre."""
    if job.apply_channel:
        return job.apply_channel
    if job.company_id:
        company = db.get(models.Company, job.company_id)
        if company is not None:
            owner = db.get(models.User, company.owner_user_id)
            if owner is not None and owner.role == "recruiter":
                return "platform"
    return "external"


@router.get("/jobs/{job_id}", response_model=dict)
def public_job(job_id: int, db: Session = Depends(get_db)):
    """Fiche publique minimale de l'offre (aucune donnée personnelle)."""
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "sector": job.sector,
        "contract_type": job.contract_type,
        "description": job.description,
        "requirements": job.requirements,
        "required_skills": job.required_skills or [],
        "published_at": job.published_at,
        "deadline": job.deadline,
        "salary": job.salary,
        "photo_url": job_media.photo_url(job),
        "company_branding": _company_branding(db, job),
        "apply_channel": _apply_channel(db, job),
        "apply_instructions": job.apply_instructions or "",
        "email_apply_address": email_routing.inbound_address(db),
        "email_reference": email_routing.reference_for(job),
        "poster_url": email_routing.public_poster_path(job),
        "source": {"name": job.source_name, "url": job.source_url},
    }


@router.get("/jobs/{job_id}/poster.svg")
def public_job_poster(job_id: int, db: Session = Depends(get_db)):
    """Visuel autonome 1200 x 1500 pour LinkedIn, WhatsApp ou e-mail.

    L'adresse interne et la référence de l'offre sont les seules données
    nécessaires : aucune information personnelle n'est exposée.
    """
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    conf = settings_store.get_raw_group(db, "inbound")
    address = str(conf.get("address") or "").strip()
    if not address:
        raise HTTPException(
            status_code=503,
            detail=(
                "Adresse de réception e-mail non configurée : "
                "voir Paramètres, Réception des candidatures."
            ),
        )
    reference = email_routing.reference_for(job)
    public_url = f"{config.PUBLIC_BASE_URL.rstrip('/')}/postuler/{job.id}"
    svg = poster.build_svg(job, address, reference, public_url)
    return Response(
        content=svg,
        media_type="image/svg+xml; charset=utf-8",
        headers={
            "Content-Disposition": f'inline; filename="visuel-{reference}.svg"',
            "Cache-Control": "public, max-age=300",
        },
    )


@router.post("/inbound-email", response_model=dict)
def inbound_email_webhook(
    payload: schemas.InboundEmailIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Webhook signé d'un fournisseur de boîte mail.

    Le fournisseur pousse un message normalisé (expéditeur, objet, texte,
    pièces jointes en base64). La signature se fait par en-tête
    ``X-OrientSkill-Secret`` ou par jeton dans l'URL. Un message non routé
    reste un succès HTTP : le fournisseur ne doit pas réessayer en boucle.
    """
    conf = settings_store.get_raw_group(db, "inbound")
    if not conf.get("webhook_secret"):
        raise HTTPException(
            status_code=503,
            detail="Webhook non configuré (voir Paramètres, Réception des candidatures).",
        )
    provided = (
        request.headers.get("X-OrientSkill-Secret")
        or request.headers.get("X-Webhook-Secret")
        or request.query_params.get("secret", "")
    )
    authorization = request.headers.get("Authorization", "")
    if not provided and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    if not inbound_email.verify_webhook_secret(db, provided):
        raise HTTPException(status_code=401, detail="Signature webhook invalide")
    message = inbound_email.from_webhook(payload.model_dump())
    if not message.sender_email:
        raise HTTPException(status_code=400, detail="Adresse d'expéditeur invalide")
    try:
        return inbound_email.process_inbound(db, message)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Traitement de la candidature impossible.",
        ) from exc


@router.post("/jobs/{job_id}/apply", status_code=201,
             response_model=schemas.PublicApplyOut)
def public_apply(
    job_id: int,
    payload: schemas.PublicApplyIn,
    db: Session = Depends(get_db),
):
    """Crée le compte + la candidature, puis envoie les accès par e-mail."""
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    if job.deadline and job.deadline < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=400,
            detail="Les candidatures sont closes pour cette offre.",
        )
    if _apply_channel(db, job) != "platform":
        raise HTTPException(
            status_code=400,
            detail=(
                "Cette offre se postule directement auprès de l'entreprise : "
                "utilisez le lien de candidature indiqué sur la fiche."
            ),
        )

    email = payload.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Adresse e-mail invalide")
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(
            status_code=409,
            detail=(
                "Un compte existe déjà avec cet e-mail. Connectez-vous pour "
                "postuler : votre profil et vos candidatures vous attendent."
            ),
        )

    password = _temp_password()
    user = models.User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=security.hash_password(password),
        role="candidate",
        phone=payload.phone.strip(),
    )
    db.add(user)
    db.flush()

    now = models.utcnow()
    application = models.Application(
        user_id=user.id,
        job_id=job.id,
        status="envoyee",
        apply_channel="platform",
        submitted_at=now,
        cover_note=payload.motivation.strip(),
        timeline=[{
            "at": now.isoformat(timespec="seconds"),
            "event": (
                "Candidature déposée depuis le lien public de l'offre ; "
                "profil à compléter par le candidat"
            ),
        }],
    )
    db.add(application)
    db.commit()
    db.refresh(user)
    db.refresh(application)

    base = config.PUBLIC_BASE_URL.rstrip("/")
    body = (
        f"Bonjour {user.full_name},\n\n"
        f"Votre candidature pour « {job.title} » chez {job.company} est "
        "bien enregistrée.\n\n"
        "Un compte OrientSkill AI a été créé pour vous :\n"
        f"E-mail : {email}\n"
        f"Mot de passe provisoire : {password}\n\n"
        f"Se connecter : {base}/login\n"
        f"Compléter votre profil : {base}/profil\n\n"
        "Votre profil est incomplet pour l'instant : ajoutez vos "
        "compétences et expériences pour améliorer vos chances. Vous "
        "pouvez changer votre mot de passe dans les paramètres du compte.\n\n"
        "À bientôt,\nOrientSkill AI\n"
    )
    email_sent, _detail = notifications.send_email(
        db, email, f"Candidature reçue : {job.title}", body
    )
    return {
        "token": security.create_token(user.id),
        "user": user,
        "application_id": application.id,
        "email_sent": email_sent,
    }
