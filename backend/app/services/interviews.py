"""Invitations à un entretien depuis une shortlist recruteur.

Le recruteur propose une date et une heure ; le candidat reçoit un e-mail
personnalisé (identité du poste et de l'entreprise, créneau en clair) avec
deux liens profonds : accepter le créneau ou demander un autre créneau.
Aucune donnée n'est inventée : tout vient de l'offre et des comptes réels.
"""
import secrets
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app import config, models

JOURS = [
    "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche",
]
MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def new_token() -> str:
    return secrets.token_urlsafe(24)


def slot_label(slot: datetime) -> str:
    """Créneau en clair, sans dépendre de la locale du serveur."""
    return (
        f"{JOURS[slot.weekday()]} {slot.day:02d} {MOIS[slot.month - 1]} "
        f"{slot.year} à {slot.hour:02d}h{slot.minute:02d}"
    )


def deep_links(token: str) -> tuple[str, str]:
    base = config.PUBLIC_BASE_URL.rstrip("/")
    return (
        f"{base}/entretiens/{token}?reponse=accepte",
        f"{base}/entretiens/{token}?reponse=refuse",
    )


def calendar_url(token: str) -> str:
    """Téléchargement public du calendrier (le jeton fait office de secret)."""
    return f"/api/interviews/{token}/calendar.ics"


def compose_body(invite: models.InterviewInvite, job: models.Job) -> str:
    """Corps texte de l'e-mail : message du recruteur + faits vérifiables."""
    accept, decline = deep_links(invite.token)
    return (
        f"{invite.message.strip()}\n\n"
        "---\n"
        f"Poste : {job.title}\n"
        f"Entreprise : {job.company}\n"
        f"Lieu : {job.location}\n"
        f"Créneau proposé : {slot_label(invite.slot_at)} "
        f"({invite.duration_min} minutes)\n\n"
        f"Accepter ce créneau : {accept}\n"
        f"Demander un autre créneau : {decline}\n\n"
        "Ces liens vous ramènent sur OrientSkill AI : connectez-vous avec "
        "votre compte pour répondre. Vous pouvez aussi répondre depuis "
        "votre espace, rubrique Entretiens.\n"
    )


def compose_response_body(
    invite: models.InterviewInvite,
    job: models.Job,
    candidate: models.User,
) -> tuple[str, str]:
    """Objet + corps de l'e-mail envoyé au recruteur après la réponse.

    Le fichier .ics joint est produit par ``services.calendar`` avec le
    statut réel (confirmé ou annulé) : l'agenda du recruteur reste juste.
    """
    decision = (
        "a accepté le créneau"
        if invite.status == "accepted"
        else "demande un autre créneau"
    )
    subject = (
        f"Entretien confirmé : {job.title}"
        if invite.status == "accepted"
        else f"Autre créneau demandé : {job.title}"
    )
    lines = [
        f"Bonjour {job.company},",
        "",
        f"{candidate.full_name} {decision} pour « {job.title} ».",
        f"Créneau proposé : {slot_label(invite.slot_at)} "
        f"({invite.duration_min} minutes).",
    ]
    if invite.candidate_note:
        lines += ["", f"Message du candidat : {invite.candidate_note}"]
    lines += [
        "",
        f"Fiche de l'invitation : "
        f"{config.PUBLIC_BASE_URL.rstrip('/')}/entretiens/{invite.token}",
        "",
        "Le calendrier au format .ics est joint à cet e-mail.",
        "",
        "OrientSkill AI",
    ]
    return subject, "\n".join(lines)


def invite_dict(
    db: Session,
    invite: models.InterviewInvite,
    email_sent: bool = False,
) -> dict[str, Any]:
    job = db.get(models.Job, invite.job_id)
    candidate = db.get(models.User, invite.candidate_id)
    recruiter = db.get(models.User, invite.recruiter_id)
    return {
        "id": invite.id,
        "token": invite.token,
        "candidate_id": invite.candidate_id,
        "candidate_name": candidate.full_name if candidate else "",
        "job_id": invite.job_id,
        "job_title": job.title if job else f"offre #{invite.job_id}",
        "company": job.company if job else "",
        "recruiter_name": recruiter.full_name if recruiter else "",
        "slot_at": invite.slot_at,
        "duration_min": invite.duration_min,
        "subject": invite.subject,
        "message": invite.message,
        "status": invite.status,
        "candidate_note": invite.candidate_note,
        "created_at": invite.created_at,
        "responded_at": invite.responded_at,
        "email_sent": email_sent,
        "calendar_url": calendar_url(invite.token),
    }
