"""Calendriers iCalendar (.ics) des entretiens.

Le créneau est saisi en heure locale camerounaise (Africa/Douala, UTC+1,
sans heure d'été). Le fichier est produit en UTC pour être compris par
tous les agendas, sans dépendre de la configuration du poste.

Deux usages :
- invitation ou confirmation téléchargée depuis la page Entretiens ;
- pièce jointe des e-mails d'invitation et de réponse au recruteur.
"""
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Optional

from app import config, models

# Le Cameroun reste à UTC+1 toute l'année : la conversion est stable.
CAMEROON_OFFSET = timedelta(hours=1)
UID_DOMAIN = "orientskill.cm"


def _utc(slot: datetime) -> datetime:
    """Heure locale du créneau -> instant UTC (naïf -> aware)."""
    return (slot - CAMEROON_OFFSET).replace(tzinfo=timezone.utc)


def _stamp(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%SZ")


def _escape(value: str) -> str:
    """Échappement RFC 5545 des valeurs texte."""
    text = (value or "").replace("\\", "\\\\")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", "\\n")
    text = text.replace(";", "\\;").replace(",", "\\,")
    return text


def _fold(line: str) -> str:
    """Replie une ligne à 75 octets (UTF-8) avec continuations."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    chunks: list[bytes] = []
    start = 0
    while start < len(raw):
        end = min(start + 75, len(raw))
        # Ne jamais couper au milieu d'un caractère UTF-8.
        while end < len(raw) and (raw[end] & 0xC0) == 0x80:
            end -= 1
        if end <= start:  # sécurité : caractère isolé trop long
            end = min(start + 75, len(raw))
        chunks.append(raw[start:end])
        start = end
    return "\r\n ".join(chunk.decode("utf-8") for chunk in chunks)


def _slug(value: str, fallback: str = "entretien") -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    return slug[:60] or fallback


def filename(invite: models.InterviewInvite, job: Optional[models.Job]) -> str:
    title = job.title if job else f"offre-{invite.job_id}"
    return f"{_slug(title)}-{invite.slot_at.strftime('%Y%m%d')}.ics"


def status_for(invite: models.InterviewInvite, status: Optional[str] = None) -> str:
    return status or invite.status or "pending"


def build(
    invite: models.InterviewInvite,
    job: Optional[models.Job],
    candidate: Optional[models.User],
    recruiter: Optional[models.User],
    status: Optional[str] = None,
) -> bytes:
    """Construit le fichier .ics complet, prêt à être joint ou téléchargé."""
    current = status_for(invite, status)
    start = _utc(invite.slot_at)
    end = start + timedelta(minutes=max(15, invite.duration_min or 45))
    now = datetime.now(timezone.utc)

    if current == "accepted":
        method, event_status, sequence = "REQUEST", "CONFIRMED", 1
        summary = f"Entretien : {job.title if job else 'Poste'}"
    elif current in ("declined", "refused"):
        method, event_status, sequence = "CANCEL", "CANCELLED", 2
        summary = f"Annulé - Entretien : {job.title if job else 'Poste'}"
    else:
        method, event_status, sequence = "REQUEST", "TENTATIVE", 0
        summary = f"Entretien proposé : {job.title if job else 'Poste'}"

    company = job.company if job else ""
    location = (job.location if job else "") or "Lieu à confirmer"
    recruiter_name = recruiter.full_name if recruiter else "Recruteur"
    recruiter_email = recruiter.email if recruiter else f"no-reply@{UID_DOMAIN}"
    candidate_name = candidate.full_name if candidate else "Candidat"
    candidate_email = candidate.email if candidate else ""
    invite_url = f"{config.PUBLIC_BASE_URL.rstrip('/')}/entretiens/{invite.token}"

    description_parts = [
        invite.message.strip(),
        f"Poste : {job.title if job else ''}",
        f"Entreprise : {company}",
        f"Créneau : {invite.slot_at.strftime('%d/%m/%Y %H:%M')} (heure du Cameroun)",
        f"Durée : {invite.duration_min} minutes",
        f"Recruteur : {recruiter_name}",
    ]
    if current in ("declined", "refused") and invite.candidate_note:
        description_parts.append(f"Message du candidat : {invite.candidate_note}")
    description_parts.append(f"Invitation : {invite_url}")
    description = "\n".join(part for part in description_parts if part)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OrientSkill AI//Entretiens//FR",
        "CALSCALE:GREGORIAN",
        f"METHOD:{method}",
        "BEGIN:VEVENT",
        f"UID:entretien-{invite.token}@{UID_DOMAIN}",
        f"DTSTAMP:{_stamp(now)}",
        f"DTSTART:{_stamp(start)}",
        f"DTEND:{_stamp(end)}",
        f"SEQUENCE:{sequence}",
        f"STATUS:{event_status}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        f"LOCATION:{_escape(location)}",
        f"ORGANIZER;CN={_escape(recruiter_name)}:mailto:{recruiter_email}",
    ]
    if candidate_email:
        lines.append(
            f"ATTENDEE;CN={_escape(candidate_name)};RSVP=TRUE:mailto:{candidate_email}"
        )
    lines += [
        f"URL:{invite_url}",
        "TRANSP:OPAQUE",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    content = "\r\n".join(_fold(line) for line in lines) + "\r\n"
    return content.encode("utf-8")


def attachment(
    invite: models.InterviewInvite,
    job: Optional[models.Job],
    candidate: Optional[models.User],
    recruiter: Optional[models.User],
    status: Optional[str] = None,
) -> dict:
    """Pièce jointe prête pour ``notifications.send_email``."""
    return {
        "filename": filename(invite, job),
        "content": build(invite, job, candidate, recruiter, status),
        "maintype": "text",
        "subtype": "calendar",
    }
