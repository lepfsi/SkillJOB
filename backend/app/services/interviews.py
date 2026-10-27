"""Invitations à un entretien depuis une shortlist recruteur.

Le recruteur propose une date et une heure ; le candidat reçoit un e-mail
personnalisé (identité du poste et de l'entreprise, créneau en clair) avec
trois liens profonds : accepter, demander un autre créneau ou refuser.
Toute demande d'autre créneau porte des disponibilités explicites. Le
recruteur retrouve ces demandes dans une file dédiée, avec l'historique
des propositions et des réponses. Aucune donnée n'est inventée.
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


def deep_links(token: str) -> tuple[str, str, str]:
    base = config.PUBLIC_BASE_URL.rstrip("/")
    return (
        f"{base}/entretiens/{token}?reponse=accepte",
        f"{base}/entretiens/{token}?reponse=autre-creneau",
        f"{base}/entretiens/{token}?reponse=refus",
    )


def calendar_url(token: str) -> str:
    """Téléchargement public du calendrier (le jeton fait office de secret)."""
    return f"/api/interviews/{token}/calendar.ics"


def _iso(slot: datetime) -> str:
    return slot.isoformat(timespec="minutes")


def requested_slot_values(invite: models.InterviewInvite) -> list[datetime]:
    """Créneaux proposés par le candidat, relus sans casser l'existant."""
    slots: list[datetime] = []
    for value in invite.requested_slots or []:
        try:
            slot = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            continue
        if slot.tzinfo is not None:
            slot = slot.replace(tzinfo=None)
        slots.append(slot)
    return slots


def append_history(
    invite: models.InterviewInvite,
    actor: str,
    action: str,
    slot_at: datetime | None = None,
    note: str = "",
) -> None:
    """Ajoute un événement lisible à l'historique de l'invitation."""
    history = list(invite.history or [])
    entry: dict[str, Any] = {
        "at": models.utcnow().isoformat(timespec="seconds"),
        "actor": actor,
        "action": action,
    }
    if slot_at is not None:
        entry["slot_at"] = _iso(slot_at)
    if note:
        entry["note"] = note.strip()[:1000]
    history.append(entry)
    invite.history = history


def compose_body(invite: models.InterviewInvite, job: models.Job) -> str:
    """Corps texte de l'e-mail : message du recruteur + faits vérifiables."""
    accept, reschedule, refuse = deep_links(invite.token)
    return (
        f"{invite.message.strip()}\n\n"
        "---\n"
        f"Poste : {job.title}\n"
        f"Entreprise : {job.company}\n"
        f"Lieu : {job.location}\n"
        f"Créneau proposé : {slot_label(invite.slot_at)} "
        f"({invite.duration_min} minutes)\n\n"
        f"Accepter ce créneau : {accept}\n"
        f"Demander un autre créneau : {reschedule}\n"
        f"Refuser l'entretien : {refuse}\n\n"
        "Ces liens vous ramènent sur OrientSkill AI : connectez-vous avec "
        "votre compte pour répondre. Vous pouvez aussi répondre depuis "
        "votre espace, rubrique Entretiens.\n"
    )


def _decision_label(invite: models.InterviewInvite) -> tuple[str, str]:
    if invite.status == "accepted":
        return "a accepté le créneau", "Entretien confirmé"
    if invite.status == "refused":
        return "a refusé l'entretien", "Entretien refusé"
    return "demande un autre créneau", "Autre créneau demandé"


def compose_response_body(
    invite: models.InterviewInvite,
    job: models.Job,
    candidate: models.User,
) -> tuple[str, str]:
    """Objet + corps de l'e-mail envoyé au recruteur après la réponse.

    Le fichier .ics joint est produit par ``services.calendar`` avec le
    statut réel (confirmé ou annulé) : l'agenda du recruteur reste juste.
    """
    decision, subject_start = _decision_label(invite)
    subject = f"{subject_start} : {job.title}"
    lines = [
        f"Bonjour {job.company},",
        "",
        f"{candidate.full_name} {decision} pour « {job.title} ».",
        f"Créneau proposé : {slot_label(invite.slot_at)} "
        f"({invite.duration_min} minutes).",
    ]
    if invite.status == "declined":
        slots = requested_slot_values(invite)
        if slots:
            lines += ["", "Créneaux proposés par le candidat :"]
            lines += [f"- {slot_label(slot)}" for slot in slots]
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


def compose_candidate_response_body(
    invite: models.InterviewInvite,
    job: models.Job,
) -> tuple[str, str]:
    """Confirmation immédiate au candidat après sa propre réponse."""
    if invite.status == "accepted":
        subject = f"Entretien confirmé : {job.title}"
        intro = (
            f"Votre entretien pour « {job.title} » chez {job.company} est "
            f"confirmé le {slot_label(invite.slot_at)} "
            f"({invite.duration_min} minutes)."
        )
    elif invite.status == "refused":
        subject = f"Entretien refusé : {job.title}"
        intro = (
            f"Votre refus de l'entretien pour « {job.title} » chez "
            f"{job.company} a bien été transmis au recruteur."
        )
    else:
        subject = f"Autre créneau demandé : {job.title}"
        slots = requested_slot_values(invite)
        intro = (
            f"Votre demande d'autre créneau pour « {job.title} » chez "
            f"{job.company} a bien été transmise au recruteur."
        )
        if slots:
            intro += "\n\nCréneaux proposés :\n" + "\n".join(
                f"- {slot_label(slot)}" for slot in slots
            )
    body = (
        f"Bonjour,\n\n{intro}\n\n"
        f"Fiche de l'invitation : "
        f"{config.PUBLIC_BASE_URL.rstrip('/')}/entretiens/{invite.token}\n\n"
        "OrientSkill AI\n"
    )
    return subject, body


def compose_candidate_decision_body(
    invite: models.InterviewInvite,
    job: models.Job,
    action: str,
    slot_at: datetime | None = None,
    note: str = "",
) -> tuple[str, str]:
    """Décision du recruteur sur une demande de créneau, pour le candidat."""
    if action == "accept_requested" and slot_at is not None:
        subject = f"Entretien confirmé : {job.title}"
        intro = (
            f"Le recruteur a accepté votre créneau pour « {job.title} » chez "
            f"{job.company}. L'entretien est confirmé le {slot_label(slot_at)} "
            f"({invite.duration_min} minutes)."
        )
    elif action == "propose" and slot_at is not None:
        subject = f"Nouveau créneau proposé : {job.title}"
        intro = (
            f"Le recruteur vous propose un nouveau créneau pour "
            f"« {job.title} » chez {job.company} : {slot_label(slot_at)} "
            f"({invite.duration_min} minutes). Répondez depuis la rubrique "
            "Entretiens."
        )
    else:
        subject = f"Entretien interrompu : {job.title}"
        intro = (
            f"Le recruteur a mis fin au processus d'entretien pour "
            f"« {job.title} » chez {job.company}."
        )
    if note:
        intro += f"\n\nMessage du recruteur : {note}"
    body = (
        f"Bonjour,\n\n{intro}\n\n"
        f"Fiche de l'invitation : "
        f"{config.PUBLIC_BASE_URL.rstrip('/')}/entretiens/{invite.token}\n\n"
        "OrientSkill AI\n"
    )
    return subject, body


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
        "requested_slots": requested_slot_values(invite),
        "history": invite.history or [],
        "awaiting_recruiter": invite.status == "declined",
        "created_at": invite.created_at,
        "responded_at": invite.responded_at,
        "recruiter_responded_at": invite.recruiter_responded_at,
        "email_sent": email_sent,
        "calendar_url": calendar_url(invite.token),
    }
