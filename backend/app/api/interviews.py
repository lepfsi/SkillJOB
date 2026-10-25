"""Invitations à un entretien : vue candidat et réponse au créneau.

La vue par jeton est publique (elle ne révèle que le poste, l'entreprise
et le créneau) : le lien reçu par e-mail fonctionne même avant connexion.
La réponse, elle, exige le compte du candidat invité.
"""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services import calendar as calendar_service
from app.services import interviews as interview_service
from app.services import notifications

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


def _by_token(db: Session, token: str) -> models.InterviewInvite:
    invite = (
        db.query(models.InterviewInvite)
        .filter(models.InterviewInvite.token == token)
        .first()
    )
    if invite is None:
        raise HTTPException(status_code=404, detail="Invitation introuvable")
    return invite


@router.get("", response_model=list[schemas.InterviewInviteOut])
def my_interviews(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Invitations reçues par le candidat connecté, les plus récentes d'abord."""
    rows = (
        db.query(models.InterviewInvite)
        .filter(models.InterviewInvite.candidate_id == user.id)
        .order_by(models.InterviewInvite.created_at.desc())
        .all()
    )
    return [interview_service.invite_dict(db, row) for row in rows]


@router.get("/{token}/calendar.ics")
def invite_calendar(token: str, db: Session = Depends(get_db)):
    """Fichier .ics de l'invitation, téléchargeable sans connexion.

    Le jeton contenu dans le lien e-mail fait office de secret. Le statut
    du calendrier suit la réponse du candidat (proposé, confirmé, annulé).
    """
    invite = _by_token(db, token)
    job = db.get(models.Job, invite.job_id)
    candidate = db.get(models.User, invite.candidate_id)
    recruiter = db.get(models.User, invite.recruiter_id)
    content = calendar_service.build(invite, job, candidate, recruiter)
    name = calendar_service.filename(invite, job)
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/{token}", response_model=schemas.InterviewInviteOut)
def view_invite(token: str, db: Session = Depends(get_db)):
    """Vue publique d'une invitation (lien profond de l'e-mail)."""
    return interview_service.invite_dict(db, _by_token(db, token))


@router.post("/{token}/respond", response_model=schemas.InterviewInviteOut)
def respond(
    token: str,
    payload: schemas.InterviewRespondIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Accepte le créneau ou demande un autre créneau.

    La réponse part aussi en message interne au recruteur : il voit la
    décision dans sa messagerie, sans attendre un e-mail."""
    invite = _by_token(db, token)
    if invite.candidate_id != user.id:
        raise HTTPException(status_code=403, detail="Cette invitation ne vous appartient pas")
    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="Cette invitation a déjà reçu une réponse")
    note = (payload.note or "").strip()[:1000]
    invite.status = payload.decision
    invite.responded_at = models.utcnow()
    invite.candidate_note = note or None

    job = db.get(models.Job, invite.job_id)
    title = job.title if job else f"offre #{invite.job_id}"
    decision = (
        "a accepté le créneau"
        if payload.decision == "accepted"
        else "demande un autre créneau"
    )
    body = (
        f"Réponse à votre invitation pour « {title} » : le candidat "
        f"{decision} ({interview_service.slot_label(invite.slot_at)})."
    )
    if note:
        body += f"\nMessage du candidat : {note}"
    db.add(models.Message(
        sender_id=user.id,
        recipient_id=invite.recruiter_id,
        body=body,
        job_id=invite.job_id,
    ))
    db.commit()
    db.refresh(invite)

    # La réponse part aussi par e-mail au recruteur, avec le calendrier
    # au bon statut : les personnes qui suivent leurs entretiens par mail
    # peuvent ajouter ou annuler le créneau en un clic. Best effort : un
    # SMTP indisponible ne remet jamais la réponse en cause.
    recruiter = db.get(models.User, invite.recruiter_id)
    candidate = db.get(models.User, invite.candidate_id)
    if job and recruiter:
        subject, mail_body = interview_service.compose_response_body(
            invite, job, candidate or user
        )
        ics = calendar_service.attachment(
            invite, job, candidate, recruiter, status=invite.status
        )
        notifications.send_email(
            db, recruiter.email, subject, mail_body,
            attachments=[ics], reply_to=user.email,
        )
    if invite.status == "accepted" and job and candidate:
        ics = calendar_service.attachment(
            invite, job, candidate, recruiter, status="accepted"
        )
        notifications.send_email(
            db, candidate.email,
            f"Entretien confirmé : {job.title}",
            (
                f"Bonjour {candidate.full_name},\n\n"
                f"Votre entretien pour « {job.title} » chez {job.company} "
                f"est confirmé le {interview_service.slot_label(invite.slot_at)} "
                f"({invite.duration_min} minutes).\n\n"
                "Le calendrier au format .ics est joint à cet e-mail.\n\n"
                "OrientSkill AI\n"
            ),
            attachments=[ics],
        )
    return interview_service.invite_dict(db, invite)
