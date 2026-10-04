"""Console d'administration : statistiques, paramètres (SMTP, LLM,
agrégateurs), tests de connexion, gestion de la base d'offres, vue
globale sur les utilisateurs (MFA, vérifications).

Accès réservé au rôle ``admin`` (§55 : la gestion opérationnelle reste
dans le périmètre administrateur, pas candidat).
"""
import smtplib
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import config, models, schemas, security
from app.database import get_db
from app.services import llm_client, settings_store

router = APIRouter(prefix="/api/admin", tags=["admin"],
                   dependencies=[Depends(security.require_admin)])


@router.get("/stats", response_model=schemas.AdminStats)
def stats(db: Session = Depends(get_db)):
    llm_conf = llm_client.get_llm_config(db)
    smtp_raw = settings_store.get_raw_group(db, "smtp")
    return {
        "users": db.query(models.User).count(),
        "profiles": db.query(models.Profile).count(),
        "jobs": db.query(models.Job).count(),
        "applications": db.query(models.Application).count(),
        "documents": db.query(models.Document).count(),
        "learning_resources": db.query(models.LearningResource).count(),
        "llm_enabled": llm_conf["enabled"],
        "smtp_enabled": bool(smtp_raw.get("enabled") and smtp_raw.get("host")),
    }


# --------------------------------------- Sources & collecte (§50, V2)

@router.get("/sources", response_model=list[dict])
def admin_sources(db: Session = Depends(get_db)):
    """Connecteurs de collecte multi-source, avec leur fiabilité (§51)."""
    out = []
    for s in db.query(models.SourceConfig).order_by(models.SourceConfig.created_at.desc()).all():
        reliability = "non testée"
        if s.runs > 0:
            rate = (s.runs - s.failures) / s.runs
            reliability = f"{round(rate * 100)} % de réussite"
        out.append({
            "id": s.id, "name": s.name, "kind": s.kind, "url": s.url,
            "sector": s.sector, "enabled": bool(s.enabled),
            "runs": s.runs, "failures": s.failures,
            "offers_imported": s.offers_imported,
            "offers_skipped": s.offers_skipped,
            "last_run_at": s.last_run_at, "last_status": s.last_status,
            "reliability": reliability,
        })
    return out


@router.post("/sources", status_code=201, response_model=dict)
def admin_add_source(payload: schemas.SourceCreateIn, db: Session = Depends(get_db)):
    source = models.SourceConfig(
        name=payload.name.strip(),
        kind=payload.kind,
        url=payload.url.strip(),
        sector=payload.sector.strip(),
        enabled=payload.enabled,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return {"id": source.id, "ok": True}


@router.put("/sources/{source_id}", response_model=dict)
def admin_update_source(source_id: int, payload: schemas.SourceUpdateIn,
                        db: Session = Depends(get_db)):
    source = db.get(models.SourceConfig, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source introuvable")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, field, value)
    db.commit()
    return {"ok": True}


@router.delete("/sources/{source_id}")
def admin_delete_source(source_id: int, db: Session = Depends(get_db)):
    source = db.get(models.SourceConfig, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source introuvable")
    db.delete(source)
    db.commit()
    return {"ok": True}


@router.post("/sources/{source_id}/run", response_model=dict)
def admin_run_source(source_id: int, db: Session = Depends(get_db)):
    """Lance la collecte pour UNE source (dédup incluse)."""
    source = db.get(models.SourceConfig, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source introuvable")
    from app.services import ingestion
    return ingestion.run_source(db, source)


@router.post("/sources/run-all", response_model=list[dict])
def admin_run_all_sources(db: Session = Depends(get_db)):
    from app.services import ingestion
    return ingestion.run_all_sources(db)


@router.post("/import-url", response_model=dict)
def admin_import_url(payload: schemas.ImportUrlIn, db: Session = Depends(get_db)):
    """Import d'une offre depuis une page publique (LinkedIn ou autre)
    via son balisage JSON-LD : BROUILLON à valider avant publication
    (mécanisme autorisé, aucune collecte de masse)."""
    from app.services import ingestion
    draft = ingestion.import_job_from_url(payload.url.strip())
    if "error" in draft:
        raise HTTPException(status_code=400, detail=draft["error"])
    return draft


@router.get("/settings", response_model=schemas.AdminSettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return settings_store.get_settings(db)


@router.put("/settings/{group}", response_model=dict)
def update_settings(group: str, payload: schemas.AdminSettingsUpdate,
                    db: Session = Depends(get_db)):
    if group not in settings_store.DEFAULTS:
        raise HTTPException(status_code=404, detail="Groupe de paramètres inconnu")
    updated = settings_store.update_group(db, group, payload.data)
    return {group: updated}


@router.post("/test-llm", response_model=schemas.TestResult)
def test_llm(db: Session = Depends(get_db)):
    ok, detail = llm_client.test_connection(db)
    return {"ok": ok, "detail": detail}


@router.post("/test-smtp", response_model=schemas.TestResult)
def test_smtp(db: Session = Depends(get_db)):
    """Vérifie la poignée de main SMTP (connexion + STARTTLS + LOGIN)."""
    conf = settings_store.get_raw_group(db, "smtp")
    if not conf.get("enabled"):
        return {"ok": False, "detail": "SMTP désactivé dans les paramètres."}
    if not conf.get("host"):
        return {"ok": False, "detail": "Hôte SMTP manquant."}
    try:
        with smtplib.SMTP(conf["host"], int(conf.get("port") or 587), timeout=8) as server:
            if conf.get("use_tls", True):
                server.starttls()
            if conf.get("username") and conf.get("password"):
                server.login(conf["username"], conf["password"])
        return {"ok": True, "detail": "Connexion SMTP réussie."}
    except Exception as exc:  # smtplib lève des erreurs variées
        return {"ok": False, "detail": f"Échec SMTP : {exc}"}


@router.post("/test-telegram", response_model=schemas.TestResult)
def test_telegram(db: Session = Depends(get_db)):
    """Validation du bot Telegram AU moment de la configuration :
    getMe vérifie le token auprès de Telegram (sans envoyer de message)
    et retourne le nom du bot."""
    from app.services.notifications import validate_telegram_token

    ok, detail, _ = validate_telegram_token(db)
    return {"ok": ok, "detail": detail}


# ------------------------------------------------------------- Connecteurs
# Formalisation produits des évolutions (§56-57, §76) avec leur statut réel.

CONNECTORS: list[dict[str, Any]] = [
    {
        "id": "llm", "name": "Moteur IA (LLM)", "kind": "llm",
        "status": "configure", "phase": "V1",
        "description": "Assistant conversationnel : mode règles local par "
                       "défaut, bascule LLM OpenAI-compatible via les "
                       "paramètres.",
        "configurable": True,
    },
    {
        "id": "smtp", "name": "Notifications e-mail (SMTP)", "kind": "smtp",
        "status": "configure", "phase": "V2",
        "description": "Envoi des alertes et notifications (nouvelles offres, "
                       "correspondances fortes, relances).",
        "configurable": True,
    },
    {
        "id": "telegram", "name": "Telegram", "kind": "messaging",
        "status": "configure", "phase": "V2",
        "description": "Canal conversationnel et notifications via Telegram "
                       "Bot API (canaux d'accès §25bis).",
        "configurable": True,
    },
    {
        "id": "whatsapp", "name": "WhatsApp Business", "kind": "messaging",
        "status": "configure", "phase": "V2",
        "description": "Notifications et assistant via WhatsApp Business API "
                       "(agrégateur officiel requis).",
        "configurable": True,
    },
    {
        "id": "linkedin", "name": "Connecteur LinkedIn", "kind": "jobs",
        "status": "roadmap", "phase": "V2",
        "description": "Collecte d'offres et suivi de pages carrière via les "
                       "mécanismes autorisés uniquement (API officielles, "
                       "programmes partenaires). Voir ROADMAP_V2_V3.md.",
        "configurable": False,
    },
    {
        "id": "multi_source", "name": "Collecte multi-source", "kind": "jobs",
        "status": "roadmap", "phase": "V2",
        "description": "Ingestion automatisée multi-connecteurs : normalisation, "
                       "déduplication, scoring de fiabilité des sources (§50-51).",
        "configurable": False,
    },
    {
        "id": "skill_graph", "name": "Skill Graph national", "kind": "data",
        "status": "roadmap", "phase": "V3",
        "description": "Graphe métiers / compétences / formations / offres / "
                       "talents à l'échelle nationale (§41).",
        "configurable": False,
    },
    {
        "id": "credentials", "name": "Vérification de credentials", "kind": "credentials",
        "status": "roadmap", "phase": "V3",
        "description": "Vérification diplômes et certifications avec partenaires "
                       "habilités, badges numériques (§24).",
        "configurable": False,
    },
]


@router.get("/connectors", response_model=list[schemas.ConnectorStatus])
def connectors(db: Session = Depends(get_db)):
    settings = settings_store.get_settings(db)
    out = []
    for c in CONNECTORS:
        status = c["status"]
        if c["id"] == "llm":
            status = "operationnel" if llm_client.get_llm_config(db)["enabled"] else "configure"
        elif c["id"] == "smtp":
            raw = settings["smtp"]
            status = "operationnel" if raw.get("enabled") and raw.get("host") else "configure"
        elif c["id"] == "telegram":
            raw = settings["aggregators"]["telegram"]
            status = "operationnel" if raw.get("enabled") and raw.get("bot_token_set") else "configure"
        elif c["id"] == "whatsapp":
            raw = settings["aggregators"]["whatsapp"]
            status = "operationnel" if raw.get("enabled") and raw.get("api_key_set") else "configure"
        out.append({**c, "status": status})
    return out


# ------------------------------------------ Utilisateurs (vue sur tout)

@router.get("/users", response_model=list[schemas.AdminUserOut])
def admin_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Vue complète : comptes, MFA, vérification, profils, activité."""
    users = db.query(models.User).order_by(models.User.created_at.desc()).offset(skip).limit(limit).all()
    out = []
    for u in users:
        out.append({
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "role": u.role,
            "gender": u.gender,
            "mfa_enabled": bool(u.mfa_enabled),
            "verification_status": u.verification_status or "none",
            "created_at": u.created_at,
            "has_profile": db.query(models.Profile).filter(
                models.Profile.user_id == u.id).first() is not None,
            "applications_count": db.query(models.Application).filter(
                models.Application.user_id == u.id).count(),
            "documents_count": db.query(models.Document).filter(
                models.Document.user_id == u.id).count(),
        })
    return out


@router.delete("/users/{user_id}/mfa")
def admin_reset_mfa(user_id: int, db: Session = Depends(get_db)):
    """Réinitialisation MFA en cas extrême (perte de l'app + des codes
    de récupération). L'utilisateur reconfigure son MFA à sa prochaine
    connexion ; l'action est réservée à l'administrateur."""
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.mfa_enabled = False
    user.mfa_secret = None
    user.recovery_codes = []
    db.commit()
    return {"ok": True, "detail": "MFA réinitialisé pour cet utilisateur."}


# --------------------------------------- Vérifications de profil

@router.get("/verifications", response_model=list[schemas.AdminVerificationOut])
def admin_verifications(db: Session = Depends(get_db)):
    """Demandes de vérification : pièce d'identité à examiner, avec les
    informations du profil (nom, localisation, diplômes, certifications)
    pour COMPARER avec la pièce."""
    users = db.query(models.User).filter(
        models.User.verification_status.in_(["pending", "verified", "rejected"])
    ).order_by(models.User.created_at.desc()).all()
    out = []
    for u in users:
        profile = db.query(models.Profile).filter(
            models.Profile.user_id == u.id).first()
        profile_summary = None
        if profile is not None:
            profile_summary = {
                "title": profile.title,
                "location": profile.location,
                "geo": " · ".join(filter(None, [u.city, u.department, u.region])),
                "education": [
                    ed.get("degree", "") for ed in (profile.education or [])[:4]
                ],
                "certifications": [
                    c.get("name", "") for c in (profile.certifications or [])[:6]
                ],
            }
        out.append({
            "user_id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "requested_at": u.verified_at,
            "status": u.verification_status,
            "note": u.verification_note,
            "doc_url": f"/api/admin/verifications/{u.id}/document",
            "profile": profile_summary,
        })
    return out


@router.get("/verifications/{user_id}/document")
def admin_verification_doc(
    user_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Télécharge la pièce d'identité déposée (accès administrateur)."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    target = db.get(models.User, user_id)
    if target is None or not target.identity_doc_path:
        raise HTTPException(status_code=404, detail="Aucun document à examiner")
    full = config.BASE_DIR / target.identity_doc_path
    if not full.exists():
        raise HTTPException(status_code=404, detail="Document introuvable")
    return FileResponse(full)


@router.post("/verifications/{user_id}/approve")
def admin_approve_verification(
    user_id: int,
    payload: schemas.VerificationDecisionIn | None = None,
    db: Session = Depends(get_db),
):
    from app.models import utcnow

    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    note = (payload.note if payload and payload.note else "").strip()
    target.verification_status = "verified"
    target.verification_note = note or "Identité confirmée par un administrateur."
    target.verified_at = utcnow()
    db.commit()
    return {"ok": True}


@router.post("/verifications/{user_id}/reject")
def admin_reject_verification(
    user_id: int,
    payload: schemas.VerificationDecisionIn,
    db: Session = Depends(get_db),
):
    """Refus motivé : le motif est OBLIGATOIRE et visible du candidat
    (comparaison profil ↔ pièce, document illisible, nom non concordant…)."""
    note = (payload.note or "").strip()
    if len(note) < 5:
        raise HTTPException(
            status_code=422,
            detail="Motif du rejet requis (au moins 5 caractères) : il sera "
                   "communiqué à l'utilisateur.",
        )
    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    target.verification_status = "rejected"
    target.verification_note = note
    db.commit()
    return {"ok": True}


# ------------------------------------------------------- Offres (contenu)
# Le back-office permet de maintenir la base locale d'opportunités :
# ajouts, corrections, désactivations (traçabilité conservée, §51).

def _job_admin_dict(job: models.Job) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "sector": job.sector,
        "contract_type": job.contract_type,
        "description": job.description,
        "requirements": job.requirements,
        "required_skills": job.required_skills,
        "published_at": job.published_at,
        "deadline": job.deadline,
        "source_name": job.source_name,
        "source_url": job.source_url,
        "salary": job.salary,
    }


@router.get("/jobs", response_model=list[dict])
def admin_list_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    jobs = db.query(models.Job).order_by(models.Job.published_at.desc()).offset(skip).limit(limit).all()
    return [_job_admin_dict(j) for j in jobs]


@router.post("/jobs", status_code=201, response_model=dict)
def admin_create_job(payload: schemas.AdminJobCreate, db: Session = Depends(get_db)):
    job = models.Job(
        title=payload.title.strip(),
        company=payload.company.strip(),
        location=payload.location.strip(),
        sector=payload.sector.strip(),
        contract_type=payload.contract_type,
        description=payload.description,
        requirements=payload.requirements,
        required_skills=[r.model_dump() for r in payload.required_skills],
        published_at=datetime.utcnow(),
        deadline=payload.deadline,
        source_name=payload.source_name or "Saisie manuelle",
        source_url=payload.source_url,
        salary=payload.salary,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _job_admin_dict(job)


@router.put("/jobs/{job_id}", response_model=dict)
def admin_update_job(job_id: int, payload: schemas.AdminJobUpdate,
                     db: Session = Depends(get_db)):
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        if field == "required_skills" and value is not None:
            value = [r if isinstance(r, dict) else r for r in value]
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return _job_admin_dict(job)


@router.delete("/jobs/{job_id}")
def admin_delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    # Les candidatures et documents liés sont supprimés (maintenance back-office).
    db.query(models.Application).filter(models.Application.job_id == job_id).delete()
    db.query(models.Document).filter(models.Document.job_id == job_id).delete()
    db.delete(job)
    db.commit()
    return {"ok": True}
