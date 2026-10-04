"""Assistant conversationnel (§26) : règles + LLM optionnel + ressources."""
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
    """État du moteur de l'agent : modèle LLM connecté ou mode local.
    Transparence totale : plus jamais de changement de moteur silencieux."""
    from app.services import llm_client

    conf = llm_client.get_llm_config(db)
    return {
        "llm_enabled": conf["enabled"],
        "model": conf["model"] if conf["enabled"] else "",
        "mode": "llm" if conf["enabled"] else "local",
    }


def _resources_map(db: Session) -> dict[str, list[dict]]:
    """Ressources d'apprentissage réelles (titres + URLs) pour l'assistant."""
    out: dict[str, list[dict]] = {}
    rows = db.query(models.LearningResource).all()
    for row in rows:
        out.setdefault(row.skill, []).append({
            "title": row.title,
            "provider": row.provider,
            "type": row.type,
            "url": row.url,
        })
    return out


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
        {"job_title": app.job.title, "status": app.status}
        for app in db.query(models.Application)
        .filter(models.Application.user_id == user.id)
        .all()
    ]
    history = [m.model_dump() for m in payload.history]
    return assistant_service.answer(
        payload.message, history, profile, jobs, careers, load_taxonomy(),
        db=db, resources=_resources_map(db), role=user.role,
        applications=applications,
        verified=user.verification_status == "verified",
    )
