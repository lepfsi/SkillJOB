"""Messagerie interne : les recruteurs contactent directement les
talents depuis leur dashboard, et les talents répondent. Tout passe
par la plateforme. Le talent voit TOUJOURS qui lui écrit : le nom,
le rôle et l'entreprise du recruteur (pas de fantôme)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db

router = APIRouter(prefix="/api/messages", tags=["messages"])


def _identity(db: Session, user_id: int) -> dict:
    """Identité lisible d'un interlocuteur (recruteur : + entreprise)."""
    user = db.get(models.User, user_id)
    if user is None:
        return {"name": "?", "role": "?", "company": None}
    company = db.query(models.Company).filter(
        models.Company.owner_user_id == user.id).first()
    return {
        "name": user.full_name,
        "role": user.role,
        "company": {
            "id": company.id,
            "name": company.name,
            "sector": company.sector,
            "description": company.description,
            "location": company.location,
        } if company else None,
    }


def _thread_summary(db: Session, user_id: int, other_id: int) -> dict:
    identity = _identity(db, other_id)
    messages = (
        db.query(models.Message)
        .filter(
            ((models.Message.sender_id == user_id) & (models.Message.recipient_id == other_id))
            | ((models.Message.sender_id == other_id) & (models.Message.recipient_id == user_id))
        )
        .order_by(models.Message.created_at.desc())
        .all()
    )
    unread = sum(1 for m in messages if m.recipient_id == user_id and not m.read)
    return {
        "other_user_id": other_id,
        "other_name": identity["name"],
        "other_role": identity["role"],
        "other_company": identity["company"],
        "last_body": messages[0].body if messages else "",
        "last_at": messages[0].created_at if messages else None,
        "unread": unread,
    }


@router.post("", status_code=201, response_model=schemas.MessageOut)
def send_message(
    payload: schemas.MessageCreateIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Envoi d'un message. Un recruteur ne peut contacter que des candidats ;
    un candidat peut répondre à un recruteur ou écrire au support (admin)."""
    recipient = db.get(models.User, payload.recipient_id)
    if recipient is None:
        raise HTTPException(status_code=404, detail="Destinataire introuvable")
    if user.role == "recruiter" and recipient.role != "candidate":
        raise HTTPException(status_code=403, detail="Un recruteur contacte uniquement des candidats")
    if user.role == "candidate" and recipient.role not in ("recruiter", "admin"):
        raise HTTPException(status_code=403, detail="Destinataire non autorisé")
    if not (payload.body or "").strip():
        raise HTTPException(status_code=422, detail="Message vide")
    message = models.Message(
        sender_id=user.id,
        recipient_id=recipient.id,
        body=payload.body.strip(),
        job_id=payload.job_id,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    # Notification multi-canaux du destinataire (best effort, §25)
    from app.services.notifications import dispatch

    company = db.query(models.Company).filter(
        models.Company.owner_user_id == user.id).first()
    sender_label = user.full_name + (
        f" ({company.name})" if company else ""
    )
    dispatch(
        db, recipient,
        f"OrientSkill AI : nouveau message de {sender_label}",
        f"{user.full_name}"
        + (f" de {company.name}" if company else "")
        + f" vous a écrit : « {message.body[:200]} ». "
          "Répondez depuis votre messagerie OrientSkill.",
    )
    return message


@router.get("", response_model=list[schemas.ThreadOut])
def my_threads(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Liste des conversations (dernier message + non-lus)."""
    sent = db.query(models.Message).filter(models.Message.sender_id == user.id)
    received = db.query(models.Message).filter(models.Message.recipient_id == user.id)
    other_ids = {m.recipient_id for m in sent} | {m.sender_id for m in received}
    threads = [_thread_summary(db, user.id, oid) for oid in other_ids]
    threads.sort(key=lambda t: t["last_at"] or "", reverse=True)
    return threads


@router.get("/unread-count")
def unread_count(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    count = (
        db.query(models.Message)
        .filter(models.Message.recipient_id == user.id, models.Message.read == False)  # noqa: E712
        .count()
    )
    return {"count": count}


@router.get("/{other_user_id}", response_model=schemas.ThreadViewOut)
def thread(
    other_user_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Fil complet avec un interlocuteur ; marque les messages comme lus."""
    messages = (
        db.query(models.Message)
        .filter(
            ((models.Message.sender_id == user.id) & (models.Message.recipient_id == other_user_id))
            | ((models.Message.sender_id == other_user_id) & (models.Message.recipient_id == user.id))
        )
        .order_by(models.Message.created_at.asc())
        .all()
    )
    if not messages:
        raise HTTPException(status_code=404, detail="Aucune conversation avec cet utilisateur")
    for m in messages:
        if m.recipient_id == user.id and not m.read:
            m.read = True
    db.commit()
    return {
        "messages": messages,
        "identity": _identity(db, other_user_id),
    }
