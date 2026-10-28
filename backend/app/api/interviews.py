"""Invitations à un entretien : vue candidat et réponse au créneau.

La vue par jeton est publique (elle ne révèle que le poste, l'entreprise
et le créneau) : le lien reçu par e-mail fonctionne même avant connexion.
La réponse, elle, exige le compte du candidat invité.
"""
from datetime import timedelta

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
    """Accepte le créneau, demande un autre créneau ou refuse l'entretien.

    Une demande d'autre créneau doit porter au moins une disponibilité
    explicite : le recruteur reçoit ainsi une proposition concrète dans sa
    file dédiée, et non un simple message dans la messagerie générale.
    """
    invite = _by_token(db, token)
    if invite.candidate_id != user.id:
        raise HTTPException(status_code=403, detail="Cette invitation ne vous appartient pas")
    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="Cette invitation a déjà reçu une réponse")
    note = (payload.note or "").strip()[:1000]
    requested = list(payload.requested_slots or [])
    if payload.decision == "declined" and not requested:
        raise HTTPException(
            status_code=422,
            detail=(
                "Pour demander un autre créneau, proposez au moins une "
                "date et une heure."
            ),
        )
    if len(requested) > 5:
        raise HTTPException(
            status_code=422,
            detail="Proposez au maximum 5 créneaux.",
        )
    limit = models.utcnow() - timedelta(hours=1)
    for slot in requested:
        if slot < limit:
            raise HTTPException(
                status_code=422,
                detail="Un des créneaux proposés est déjà passé.",
            )

    invite.status = payload.decision
    invite.responded_at = models.utcnow()
    # Le candidat a répondu au dernier créneau : la décision précédente du
    # recruteur ne doit plus apparaître comme une notification en attente.
    invite.recruiter_responded_at = None
    invite.candidate_note = note or None
    invite.requested_slots = (
        [slot.isoformat(timespec="minutes") for slot in requested]
        if payload.decision == "declined"
        else []
    )
    interview_service.append_history(
        invite,
        actor="candidate",
        action=payload.decision,
        note=note,
    )
    db.commit()
    db.refresh(invite)

    # Le recruteur reçoit un e-mail avec le calendrier au bon statut.
    # Best effort : un SMTP indisponible ne remet jamais la réponse en cause.
    recruiter = db.get(models.User, invite.recruiter_id)
    candidate = db.get(models.User, invite.candidate_id)
    job = db.get(models.Job, invite.job_id)
    if job and recruiter:
        subject, mail_body = interview_service.compose_response_body(
            invite, job, candidate or user
        )
        ics = calendar_service.attachment(
            invite, job, candidate, recruiter, status=invite.status
        )
        notifications.dispatch(
            db, recruiter, subject, mail_body,
            event="interview_response",
            attachments=[ics], reply_to=user.email,
        )
    # Confirmation immédiate au candidat, quel que soit son choix.
    if job and candidate:
        subject, mail_body = interview_service.compose_candidate_response_body(
            invite, job
        )
        ics = calendar_service.attachment(
            invite, job, candidate, recruiter, status=invite.status
        )
        notifications.dispatch(
            db, candidate, subject, mail_body,
            event="interview", attachments=[ics],
        )
    return interview_service.invite_dict(db, invite)
