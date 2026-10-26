"""Assistant conversationnel (§26) : règles + LLM optionnel + ressources."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services import assistant as assistant_service
from app.services.profile_store import get_profile_row, profile_to_dict
from app.services.skills_taxonomy import load_taxonomy

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


@router.get("/status", response_model=dict)
def assistant_status(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """État du moteur : strictement réservé à l'admin.
    Les utilisateurs reçoivent un mode neutre « orientskill » : ils ne
    savent pas s'il y a un modèle derrière, ni lequel."""
    from app.services import llm_client

    if user.role != "admin":
        return {"mode": "orientskill"}
    conf = llm_client.get_llm_config(db)
    return {
        "llm_enabled": conf["enabled"],
        "model": conf["model"] if conf["enabled"] else "",
        "mode": "llm" if conf["enabled"] else "local",
    }


def _resources_map(db: Session) -> dict[str, list[dict]]:
    """Ressources d'apprentissage réelles (titres + URLs) pour l'assistant.

    Le catalogue est lu en base : une ligne masquée ou corrigée par
    l'admin n'est jamais contredite par le référentiel JSON. La nature
    du lien reste explicite (formation exacte, catalogue, recherche…)."""
    from app.services.learning import visible_resources

    return visible_resources(db)


def _history_mode(user: models.User) -> str:
    return getattr(user, "agent_history_mode", "persist") or "persist"


def _retention_days(user: models.User) -> int:
    value = getattr(user, "agent_history_retention_days", 30) or 30
    return max(1, int(value))


def _conversation_dict(db: Session, row: models.AgentConversation) -> dict:
    query = db.query(models.AssistantMessage).filter(
        models.AssistantMessage.conversation_id == row.id
    )
    count = query.count()
    last = query.order_by(models.AssistantMessage.created_at.desc()).first()
    return {
        "id": row.id,
        "title": row.title,
        "history_mode": row.history_mode or "persist",
        "retention_days": row.retention_days or 30,
        "created_at": row.created_at,
        "updated_at": row.updated_at or row.created_at,
        "message_count": count,
        "last_message": last.content if last else None,
    }


def _default_conversation(db: Session, user: models.User) -> models.AgentConversation:
    """Conversation principale : créée au premier accès, puis réutilisée."""
    conversation = (
        db.query(models.AgentConversation)
        .filter(models.AgentConversation.user_id == user.id)
        .order_by(models.AgentConversation.updated_at.desc())
        .first()
    )
    if conversation is None:
        conversation = models.AgentConversation(
            user_id=user.id,
            title="Conversation principale",
            history_mode=_history_mode(user),
            retention_days=_retention_days(user),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        # Les anciens messages (avant la multi-conversation) rejoignent la
        # conversation principale : rien n'est perdu, rien n'est dupliqué.
        db.query(models.AssistantMessage).filter(
            models.AssistantMessage.user_id == user.id,
            models.AssistantMessage.conversation_id.is_(None),
        ).update(
            {models.AssistantMessage.conversation_id: conversation.id},
            synchronize_session=False,
        )
        db.commit()
    return conversation


def _conversation_or_404(
    db: Session, user: models.User, conversation_id: int
) -> models.AgentConversation:
    row = db.get(models.AgentConversation, conversation_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation introuvable")
    return row


def _cleanup_history(db: Session, user: models.User) -> None:
    """Rétention des messages hors conversation (anciens historiques)."""
    cutoff = models.utcnow() - timedelta(days=_retention_days(user))
    db.query(models.AssistantMessage).filter(
        models.AssistantMessage.user_id == user.id,
        models.AssistantMessage.conversation_id.is_(None),
        models.AssistantMessage.created_at < cutoff,
    ).delete(synchronize_session=False)
    db.commit()


def _cleanup_conversation(db: Session, row: models.AgentConversation) -> None:
    """Rétention propre à la conversation : 30 jours par défaut."""
    cutoff = models.utcnow() - timedelta(days=max(1, row.retention_days or 30))
    db.query(models.AssistantMessage).filter(
        models.AssistantMessage.conversation_id == row.id,
        models.AssistantMessage.created_at < cutoff,
    ).delete(synchronize_session=False)
    db.commit()


@router.get("/conversations", response_model=list[schemas.AssistantConversationOut])
def assistant_conversations(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Pile des conversations de l'agent, de la plus récente à la plus ancienne."""
    _default_conversation(db, user)
    _cleanup_history(db, user)
    rows = (
        db.query(models.AgentConversation)
        .filter(models.AgentConversation.user_id == user.id)
        .order_by(models.AgentConversation.updated_at.desc())
        .all()
    )
    for row in rows:
        _cleanup_conversation(db, row)
    return [_conversation_dict(db, row) for row in rows]


@router.post(
    "/conversations",
    status_code=201,
    response_model=schemas.AssistantConversationOut,
)
def assistant_create_conversation(
    payload: schemas.AssistantConversationCreateIn | None = None,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Ouvre une nouvelle conversation, empilée au-dessus des précédentes."""
    title = (payload.title if payload and payload.title else "Nouvelle conversation").strip()
    row = models.AgentConversation(
        user_id=user.id,
        title=title or "Nouvelle conversation",
        history_mode=_history_mode(user),
        retention_days=_retention_days(user),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _conversation_dict(db, row)


@router.get(
    "/conversations/{conversation_id}",
    response_model=schemas.AssistantConversationHistoryOut,
)
def assistant_conversation_history(
    conversation_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Messages d'une conversation précise."""
    row = _conversation_or_404(db, user, conversation_id)
    _cleanup_history(db, user)
    _cleanup_conversation(db, row)
    messages = (
        db.query(models.AssistantMessage)
        .filter(models.AssistantMessage.conversation_id == row.id)
        .order_by(models.AssistantMessage.created_at.asc())
        .limit(200)
        .all()
    )
    return {
        "conversation": _conversation_dict(db, row),
        "messages": [
            {"role": m.role, "content": m.content, "created_at": m.created_at}
            for m in messages
        ],
    }


@router.put(
    "/conversations/{conversation_id}",
    response_model=schemas.AssistantConversationOut,
)
def assistant_update_conversation(
    conversation_id: int,
    payload: schemas.AssistantConversationUpdateIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Renomme une conversation ou change ses réglages d'historique."""
    row = _conversation_or_404(db, user, conversation_id)
    data = payload.model_dump(exclude_unset=True)
    if data.get("title") is not None:
        title = str(data["title"]).strip()
        if not title:
            raise HTTPException(status_code=422, detail="Titre obligatoire.")
        row.title = title
    if data.get("history_mode") is not None:
        row.history_mode = data["history_mode"]
    if data.get("retention_days") is not None:
        row.retention_days = max(1, int(data["retention_days"]))
    db.commit()
    db.refresh(row)
    return _conversation_dict(db, row)


@router.delete("/conversations/{conversation_id}", response_model=dict)
def assistant_delete_conversation(
    conversation_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Supprime une conversation et ses messages."""
    row = _conversation_or_404(db, user, conversation_id)
    db.query(models.AssistantMessage).filter(
        models.AssistantMessage.conversation_id == row.id
    ).delete(synchronize_session=False)
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.get("/history", response_model=schemas.AssistantHistoryOut)
def assistant_history(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Historique de conversation de l'utilisateur, borné à la rétention."""
    _cleanup_history(db, user)
    for conversation in (
        db.query(models.AgentConversation)
        .filter(models.AgentConversation.user_id == user.id)
        .all()
    ):
        _cleanup_conversation(db, conversation)
    rows = (
        db.query(models.AssistantMessage)
        .filter(models.AssistantMessage.user_id == user.id)
        .order_by(models.AssistantMessage.created_at.asc())
        .limit(200)
        .all()
    )
    return {
        "messages": [
            {"role": row.role, "content": row.content, "created_at": row.created_at}
            for row in rows
        ],
        "mode": _history_mode(user),
        "retention_days": _retention_days(user),
    }


@router.put("/history/settings", response_model=schemas.AssistantHistoryOut)
def assistant_history_settings(
    payload: schemas.AssistantHistorySettingsIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Bascule l'historique entre « conservé » et « éphémère ».

    Le mode éphémère cesse d'écrire les nouveaux messages. L'utilisateur
    peut toujours effacer l'existant avec `DELETE /history`.
    """
    user.agent_history_mode = payload.mode
    # Le réglage global sert de défaut : on l'applique aux conversations
    # existantes. Chaque conversation peut ensuite être ajustée seule.
    db.query(models.AgentConversation).filter(
        models.AgentConversation.user_id == user.id
    ).update(
        {models.AgentConversation.history_mode: payload.mode},
        synchronize_session=False,
    )
    db.commit()
    db.refresh(user)
    return assistant_history(user=user, db=db)


@router.delete("/history", response_model=dict)
def assistant_clear_history(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Efface l'historique de conversation de l'utilisateur."""
    db.query(models.AssistantMessage).filter(
        models.AssistantMessage.user_id == user.id
    ).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}


@router.post("", response_model=schemas.AssistantOut)
def chat(
    payload: schemas.AssistantIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    jobs = db.query(models.Job).all()
    careers = db.query(models.Career).all()
    applications = [
        {
            "job_id": app.job_id,
            "job_title": app.job.title,
            "status": app.status,
        }
        for app in db.query(models.Application)
        .filter(models.Application.user_id == user.id)
        .all()
    ]
    history = [m.model_dump() for m in payload.history]
    from app.services import entrepreneurship as entrepreneurship_service
    from app.services.domains import resolve_names
    from app.services.learning_tracking import to_dict as enrollment_dict

    enrollments = [
        enrollment_dict(row)
        for row in db.query(models.LearningEnrollment)
        .filter(models.LearningEnrollment.user_id == user.id)
        .order_by(models.LearningEnrollment.updated_at.desc())
        .all()
    ]
    documents = [
        {
            "id": row.id,
            "kind": row.kind,
            "title": row.title,
            "job_id": row.job_id,
            "template": row.template,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in db.query(models.Document)
        .filter(models.Document.user_id == user.id)
        .order_by(models.Document.created_at.desc())
        .limit(12)
        .all()
    ]

    # Libellés du référentiel : l'agent peut nommer le domaine et les
    # spécialités visés, sans reconstruire un texte approximatif.
    if profile:
        prefs = profile.setdefault("preferences", {})
        domain_name, specialty_names = resolve_names(
            db, prefs.get("domain_id"), prefs.get("specialty_ids")
        )
        prefs["domain_name"] = domain_name
        prefs["specialty_names"] = specialty_names

    # Conversation ciblée : celle du fil affiché, ou la plus récente.
    if payload.conversation_id:
        conversation = _conversation_or_404(db, user, payload.conversation_id)
    else:
        conversation = _default_conversation(db, user)

    # Titre automatique : la première question de l'utilisateur nomme le fil.
    if conversation.title in ("Nouvelle conversation", "Conversation principale"):
        conversation.title = payload.message.strip()[:80] or conversation.title

    result = assistant_service.answer(
        payload.message, history, profile, jobs, careers, load_taxonomy(),
        db=db, resources=_resources_map(db), role=user.role,
        applications=applications,
        verified=user.verification_status == "verified",
        entrepreneur_resources=entrepreneurship_service.list_resources(db),
        financing=entrepreneurship_service.FINANCING_INSTITUTIONS,
        enrollments=enrollments,
        documents=documents,
        agent_mode=getattr(user, "agent_mode", "preparation") or "preparation",
        user=user,
        context=payload.context,
    )

    # Historique : conservé selon le réglage de LA conversation. Le mode
    # éphémère n'écrit rien ; l'effacement reste possible à tout moment.
    now = models.utcnow()
    conversation.updated_at = now
    if (conversation.history_mode or "persist") == "persist":
        _cleanup_history(db, user)
        _cleanup_conversation(db, conversation)
        db.add_all([
            models.AssistantMessage(
                user_id=user.id,
                conversation_id=conversation.id,
                role="user",
                content=payload.message,
                created_at=now,
            ),
            models.AssistantMessage(
                user_id=user.id,
                conversation_id=conversation.id,
                role="assistant",
                content=result["reply"],
                created_at=now,
            ),
        ])
    db.commit()
    return result
