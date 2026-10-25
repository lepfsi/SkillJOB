"""Assistant conversationnel (§26) : règles + LLM optionnel + ressources."""
from datetime import timedelta

from fastapi import APIRouter, Depends
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


def _cleanup_history(db: Session, user: models.User) -> None:
    """Rétention : supprime les messages plus anciens que la période."""
    cutoff = models.utcnow() - timedelta(days=_retention_days(user))
    db.query(models.AssistantMessage).filter(
        models.AssistantMessage.user_id == user.id,
        models.AssistantMessage.created_at < cutoff,
    ).delete(synchronize_session=False)
    db.commit()


@router.get("/history", response_model=schemas.AssistantHistoryOut)
def assistant_history(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Historique de conversation de l'utilisateur, borné à la rétention."""
    _cleanup_history(db, user)
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

    # Historique : conservé 30 jours par défaut, jamais écrit en mode
    # éphémère. L'utilisateur garde la main (effacement possible).
    if _history_mode(user) == "persist":
        _cleanup_history(db, user)
        now = models.utcnow()
        db.add_all([
            models.AssistantMessage(
                user_id=user.id, role="user", content=payload.message,
                created_at=now,
            ),
            models.AssistantMessage(
                user_id=user.id, role="assistant", content=result["reply"],
                created_at=now,
            ),
        ])
        db.commit()
    return result
