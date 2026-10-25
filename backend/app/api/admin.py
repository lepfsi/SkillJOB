"""Console d'administration : statistiques, paramètres (SMTP, LLM,
agrégateurs), tests de connexion, gestion de la base d'offres, vue
globale sur les utilisateurs (MFA, vérifications).

Accès réservé au rôle ``admin`` (§55 : la gestion opérationnelle reste
dans le périmètre administrateur, pas candidat).
"""
import smtplib
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import config, models, schemas, security
from app.database import get_db
from app.services import (
    email_routing, inbound_email, job_media, llm_client, settings_store, uploads,
)

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
        "open_reports": (
            db.query(models.JobReport)
            .filter(models.JobReport.status.in_(["nouveau", "en_cours"]))
            .count()
        ),
        "llm_enabled": llm_conf["enabled"],
        "smtp_enabled": bool(smtp_raw.get("enabled") and smtp_raw.get("host")),
    }


# --------------------------------------- Sources & collecte (§50, V2)

def _clean_source_url(value: str) -> str:
    url = (value or "").strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400,
            detail="L'URL doit commencer par http:// ou https://.",
        )
    return url


def _source_payload(source) -> dict[str, Any]:
    """Vue API d'une source : fiabilité, santé et prochaine collecte."""
    runs = int(source.runs or 0)
    failures = int(source.failures or 0)
    rate = (runs - failures) / runs if runs else None
    reliability_pct = round(rate * 100) if rate is not None else None
    reliability = (
        f"{reliability_pct} % de réussite" if reliability_pct is not None
        else "non testée"
    )
    interval = max(5, int(source.interval_minutes or 60))
    now = datetime.utcnow()
    if source.last_run_at is None:
        next_run_at = now
        is_due = bool(source.enabled)
    else:
        next_run_at = source.last_run_at + timedelta(minutes=interval)
        is_due = bool(source.enabled and next_run_at <= now)
    if not source.enabled:
        health = "off"
    elif source.last_error:
        health = "error"
    elif runs == 0:
        health = "idle"
    elif reliability_pct is not None and reliability_pct < 70:
        health = "warning"
    else:
        health = "ok"
    return {
        "id": source.id,
        "name": source.name,
        "kind": source.kind,
        "url": source.url,
        "sector": source.sector,
        "enabled": bool(source.enabled),
        "interval_minutes": interval,
        "runs": runs,
        "failures": failures,
        "offers_imported": int(source.offers_imported or 0),
        "offers_skipped": int(source.offers_skipped or 0),
        "last_run_at": source.last_run_at,
        "next_run_at": next_run_at,
        "is_due": is_due,
        "last_status": source.last_status or "",
        "last_error": source.last_error or "",
        "last_items": int(source.last_items or 0),
        "last_duration_ms": int(source.last_duration_ms or 0),
        "reliability": reliability,
        "reliability_pct": reliability_pct,
        "health": health,
        "created_at": source.created_at,
    }


@router.get("/sources", response_model=list[dict])
def admin_sources(db: Session = Depends(get_db)):
    """Connecteurs de collecte multi-source, avec leur fiabilité (§51)."""
    rows = (
        db.query(models.SourceConfig)
        .order_by(models.SourceConfig.created_at.desc())
        .all()
    )
    return [_source_payload(source) for source in rows]


@router.post("/sources", status_code=201, response_model=dict)
def admin_add_source(payload: schemas.SourceCreateIn, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=400, detail="Le nom de la source est obligatoire."
        )
    source = models.SourceConfig(
        name=name,
        kind=payload.kind,
        url=_clean_source_url(payload.url),
        sector=payload.sector.strip(),
        enabled=payload.enabled,
        interval_minutes=payload.interval_minutes,
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
    changes = payload.model_dump(exclude_unset=True)
    if "url" in changes:
        changes["url"] = _clean_source_url(changes["url"])
    if "name" in changes:
        changes["name"] = (changes["name"] or "").strip()
        if not changes["name"]:
            raise HTTPException(
                status_code=400,
                detail="Le nom de la source est obligatoire.",
            )
    if "sector" in changes:
        changes["sector"] = (changes["sector"] or "").strip()
    for field, value in changes.items():
        setattr(source, field, value)
    if "url" in changes or "kind" in changes:
        # Un nouveau flux ne doit pas réutiliser l'ETag de l'ancien.
        source.etag = ""
        source.last_modified = ""
    db.commit()
    return {"ok": True, "source": _source_payload(source)}


@router.delete("/sources/{source_id}")
def admin_delete_source(source_id: int, db: Session = Depends(get_db)):
    source = db.get(models.SourceConfig, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source introuvable")
    db.delete(source)
    db.commit()
    return {"ok": True}


@router.post("/sources/test", response_model=dict)
def admin_test_source(payload: schemas.SourceTestIn):
    """Lit un flux avant enregistrement, sans créer de source."""
    from app.services import ingestion
    return ingestion.test_source(
        payload.kind, _clean_source_url(payload.url)
    )


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
    if group == "inbound":
        # La relève IMAP démarre ou s'arrête sans redémarrage du serveur.
        inbound_email.inbound_service.restart_if_configured()
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


@router.post("/test-imap", response_model=schemas.TestResult)
def test_imap(
    payload: schemas.AdminSettingsUpdate | None = None,
    db: Session = Depends(get_db),
):
    """Vérifie la boîte IMAP avec les valeurs du formulaire, même non
    enregistrées. Un mot de passe vide réutilise le secret stocké."""
    overrides = payload.data if payload else None
    ok, detail = inbound_email.test_imap(db, overrides)
    return {"ok": ok, "detail": detail}


@router.get("/inbound-emails", response_model=list[dict])
def admin_inbound_emails(
    status: str = "",
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Journal des candidatures reçues par e-mail, routées ou non."""
    query = db.query(models.InboundEmail)
    if status:
        query = query.filter(models.InboundEmail.status == status)
    rows = query.order_by(models.InboundEmail.created_at.desc()).limit(limit).all()
    out = []
    for row in rows:
        job = db.get(models.Job, row.job_id) if row.job_id else None
        user = db.get(models.User, row.user_id) if row.user_id else None
        attachments = row.attachments or []
        out.append({
            "id": row.id,
            "message_id": row.message_id,
            "source": row.source,
            "sender_email": row.sender_email,
            "sender_name": row.sender_name,
            "subject": row.subject,
            "status": row.status,
            "routing": row.routing,
            "job_id": row.job_id,
            "job_title": job.title if job else "",
            "company": job.company if job else "",
            "application_id": row.application_id,
            "user_id": row.user_id,
            "user_email": user.email if user else "",
            "account_created": bool(row.account_created),
            "forwarded_to": row.forwarded_to,
            "forward_email_sent": bool(row.forward_email_sent),
            "access_email_sent": bool(row.access_email_sent),
            "attachments_count": len(attachments),
            "attachment_names": [
                str(item.get("filename") or "") for item in attachments
            ],
            "detail": row.detail,
            "created_at": row.created_at,
            "processed_at": row.processed_at,
        })
    return out


@router.post(
    "/inbound-emails/{row_id}/resend-access",
    response_model=schemas.TestResult,
)
def admin_resend_inbound_access(row_id: int, db: Session = Depends(get_db)):
    """Renvoie des accès à un candidat créé automatiquement par e-mail."""
    row = db.get(models.InboundEmail, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Message entrant introuvable")
    ok, detail = inbound_email.resend_access(db, row)
    return {"ok": ok, "detail": detail}


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
            "is_banned": bool(getattr(u, "is_banned", False)),
            "ban_reason": getattr(u, "ban_reason", None) or "",
            "created_at": u.created_at,
            "has_profile": db.query(models.Profile).filter(
                models.Profile.user_id == u.id).first() is not None,
            "applications_count": db.query(models.Application).filter(
                models.Application.user_id == u.id).count(),
            "documents_count": db.query(models.Document).filter(
                models.Document.user_id == u.id).count(),
        })
    return out


@router.get("/users/{user_id}/photo")
def admin_user_photo(user_id: int, db: Session = Depends(get_db)):
    """Photo d'un utilisateur, vue administrateur."""
    user = db.get(models.User, user_id)
    if user is None or not user.photo_path:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    full = uploads.resolve(user.photo_path)
    if not full.exists():
        raise HTTPException(status_code=404, detail="Photo introuvable")
    return FileResponse(full)


@router.put("/users/{user_id}/ban")
def admin_ban_user(
    user_id: int,
    payload: schemas.BanIn,
    admin: models.User = Depends(security.require_admin),
    db: Session = Depends(get_db),
):
    """Suspend un compte (candidat ou recruteur) avec son motif.

    Le compte banni ne peut plus se connecter : le motif lui est
    communiqué à la connexion. Un administrateur ne peut être banni,
    et personne ne peut se bannir soi-même.
    """
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    if user.role == "admin" or user.id == admin.id:
        raise HTTPException(status_code=400, detail="Un compte administrateur ne peut être suspendu")
    reason = (payload.reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=422, detail="Motif obligatoire (au moins 5 caractères)")
    user.is_banned = True
    user.ban_reason = reason[:500]
    db.commit()
    return {
        "ok": True,
        "detail": f"Compte de {user.full_name} suspendu.",
        "is_banned": True,
    }


@router.delete("/users/{user_id}/ban")
def admin_unban_user(
    user_id: int,
    db: Session = Depends(get_db),
):
    """Lève la suspension d'un compte : l'utilisateur peut se reconnecter."""
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.is_banned = False
    user.ban_reason = None
    db.commit()
    return {"ok": True, "detail": f"Suspension levée pour {user.full_name}.", "is_banned": False}


# ------------------------------------------------ Recours après suspension

def _appeal_out(db: Session, row: models.BanAppeal) -> dict:
    user = db.get(models.User, row.user_id)
    return {
        "id": row.id,
        "user_id": row.user_id,
        "user_name": user.full_name if user else f"utilisateur #{row.user_id}",
        "user_email": user.email if user else "",
        "ban_reason": (user.ban_reason or "") if user else "",
        "status": row.status,
        "message": row.message,
        "created_at": row.created_at,
        "reviewed_at": row.reviewed_at,
        "admin_note": row.admin_note,
    }


@router.get("/appeals", response_model=list[schemas.AdminAppealOut])
def admin_appeals(
    status: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Recours des comptes suspendus, du plus récent au plus ancien."""
    query = db.query(models.BanAppeal)
    if status:
        query = query.filter(models.BanAppeal.status == status)
    rows = query.order_by(models.BanAppeal.created_at.desc()).limit(200).all()
    return [_appeal_out(db, row) for row in rows]


@router.put("/appeals/{appeal_id}", response_model=schemas.AdminAppealOut)
def admin_decide_appeal(
    appeal_id: int,
    payload: schemas.AppealDecisionIn,
    admin: models.User = Depends(security.require_admin),
    db: Session = Depends(get_db),
):
    """Traite un recours : l'acceptation lève la suspension et conserve
    le compte (profil, candidatures, documents restent intacts)."""
    row = db.get(models.BanAppeal, appeal_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Recours introuvable")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Ce recours a déjà été traité")
    row.status = payload.decision
    row.reviewed_at = models.utcnow()
    row.reviewed_by = admin.id
    note = (payload.note or "").strip()
    row.admin_note = note[:1000] or None
    if payload.decision == "accepted":
        user = db.get(models.User, row.user_id)
        if user is not None:
            user.is_banned = False
            user.ban_reason = None
    db.commit()
    db.refresh(row)
    return _appeal_out(db, row)


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
    full = uploads.resolve(target.identity_doc_path)
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


# ------------------------------------------- Domaines et spécialités
# Référentiel commun éditable : les ajouts de l'administration restent en
# base. Une entrée référencée par une offre ou un profil n'est jamais
# supprimée physiquement : elle est désactivée pour ne plus être proposée.

@router.get("/domains", response_model=list[schemas.DomainOut])
def admin_domains(db: Session = Depends(get_db)):
    from app.services import domains as domains_service

    return domains_service.domain_tree(db, include_inactive=True)


@router.post("/domains", status_code=201, response_model=schemas.DomainOut)
def admin_create_domain(payload: schemas.DomainIn, db: Session = Depends(get_db)):
    from app.services import domains as domains_service

    row = domains_service.create_domain(db, payload)
    return next(
        item for item in domains_service.domain_tree(db, include_inactive=True)
        if item["id"] == row.id
    )


@router.put("/domains/{domain_id}", response_model=schemas.DomainOut)
def admin_update_domain(
    domain_id: int, payload: schemas.DomainIn, db: Session = Depends(get_db)
):
    from app.services import domains as domains_service

    row = db.get(models.Domain, domain_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Domaine introuvable")
    domains_service.update_domain(db, row, payload)
    return next(
        item for item in domains_service.domain_tree(db, include_inactive=True)
        if item["id"] == row.id
    )


@router.delete("/domains/{domain_id}")
def admin_delete_domain(domain_id: int, db: Session = Depends(get_db)):
    """Désactive le domaine sans casser les offres et profils qui le citent."""
    row = db.get(models.Domain, domain_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Domaine introuvable")
    row.active = False
    db.commit()
    return {"ok": True, "id": domain_id, "active": False}


@router.post(
    "/domains/{domain_id}/specialties",
    status_code=201,
    response_model=schemas.SpecialtyOut,
)
def admin_create_specialty(
    domain_id: int, payload: schemas.SpecialtyIn, db: Session = Depends(get_db)
):
    from app.services import domains as domains_service

    domain = db.get(models.Domain, domain_id)
    if domain is None:
        raise HTTPException(status_code=404, detail="Domaine introuvable")
    row = domains_service.create_specialty(db, domain, payload)
    return {
        "id": row.id, "slug": row.slug, "name": row.name,
        "description": row.description, "aliases": row.aliases or [],
        "sort_order": row.sort_order, "active": row.active,
    }


@router.put(
    "/domains/{domain_id}/specialties/{specialty_id}",
    response_model=schemas.SpecialtyOut,
)
def admin_update_specialty(
    domain_id: int,
    specialty_id: int,
    payload: schemas.SpecialtyIn,
    db: Session = Depends(get_db),
):
    from app.services import domains as domains_service

    domain = db.get(models.Domain, domain_id)
    row = db.get(models.Specialty, specialty_id)
    if domain is None or row is None or row.domain_id != domain.id:
        raise HTTPException(status_code=404, detail="Spécialité introuvable")
    domains_service.update_specialty(db, domain, row, payload)
    return {
        "id": row.id, "slug": row.slug, "name": row.name,
        "description": row.description, "aliases": row.aliases or [],
        "sort_order": row.sort_order, "active": row.active,
    }


@router.delete("/domains/{domain_id}/specialties/{specialty_id}")
def admin_delete_specialty(
    domain_id: int, specialty_id: int, db: Session = Depends(get_db)
):
    row = db.get(models.Specialty, specialty_id)
    if row is None or row.domain_id != domain_id:
        raise HTTPException(status_code=404, detail="Spécialité introuvable")
    row.active = False
    db.commit()
    return {"ok": True, "id": specialty_id, "active": False}


# --------------------------------------------------- Signalements d'offres
# Un signalement n'est jamais supprimé : il passe par un statut de
# traitement et conserve la note de l'administrateur (traçabilité).

def _report_admin_dict(report: models.JobReport, user: models.User) -> dict:
    return {
        "id": report.id,
        "job_id": report.job_id,
        "reason": report.reason,
        "details": report.details,
        "status": report.status,
        "admin_note": report.admin_note,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "job_title": report.job.title if report.job else None,
        "company": report.job.company if report.job else None,
        "user_id": user.id,
        "user_name": user.full_name or "",
        "user_email": user.email or "",
    }


@router.get("/applications")
def admin_applications(
    status: str = "",
    channel: str = "",
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Suivi de TOUTES les candidatures envoyées via la plateforme.

    Le candidat voit son propre suivi ; l'admin voit l'ensemble : qui a
    postulé où, par quel canal, avec quels documents, et quand.
    """
    query = (
        db.query(models.Application)
        .join(models.User, models.User.id == models.Application.user_id)
    )
    if status:
        query = query.filter(models.Application.status == status)
    if channel:
        query = query.filter(models.Application.apply_channel == channel)
    rows = (
        query.order_by(models.Application.submitted_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for app in rows:
        candidate = db.get(models.User, app.user_id)
        job = app.job
        out.append({
            "id": app.id,
            "candidate_name": candidate.full_name if candidate else "",
            "candidate_email": candidate.email if candidate else "",
            "candidate_photo_url": (
                f"/api/admin/users/{candidate.id}/photo"
                if candidate and candidate.photo_path else ""
            ),
            "job_title": job.title if job else "",
            "job_company": job.company if job else "",
            "job_id": app.job_id,
            "status": app.status,
            "apply_channel": app.apply_channel or "",
            "apply_url": job.source_url if job else "",
            "apply_email": job.apply_email if job else "",
            "apply_instructions": job.apply_instructions if job else "",
            "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
            "cover_note": app.cover_note or "",
            "document_count": len(app.submitted_documents or []),
            "timeline": app.timeline or [],
        })
    return out


@router.get("/reports", response_model=list[schemas.JobReportAdminOut])
def admin_reports(
    status: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(models.JobReport, models.User).join(
        models.User, models.User.id == models.JobReport.user_id
    )
    if status:
        if status not in schemas.REPORT_STATUSES:
            raise HTTPException(status_code=422, detail="Statut de signalement invalide")
        query = query.filter(models.JobReport.status == status)
    rows = query.order_by(models.JobReport.created_at.desc()).limit(300).all()
    return [_report_admin_dict(report, user) for report, user in rows]


@router.put("/reports/{report_id}", response_model=schemas.JobReportAdminOut)
def admin_update_report(
    report_id: int,
    payload: schemas.JobReportUpdateIn,
    admin: models.User = Depends(security.require_admin),
    db: Session = Depends(get_db),
):
    if payload.status not in schemas.REPORT_STATUSES:
        raise HTTPException(status_code=422, detail="Statut de signalement invalide")
    report = db.get(models.JobReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Signalement introuvable")
    report.status = payload.status
    report.admin_note = (payload.admin_note or "").strip()[:2000]
    report.handled_by = admin.id
    db.commit()
    db.refresh(report)
    user = db.get(models.User, report.user_id)
    return _report_admin_dict(report, user)


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
        "domain_id": job.domain_id,
        "specialty_id": job.specialty_id,
        "contract_type": job.contract_type,
        "description": job.description,
        "requirements": job.requirements,
        "required_skills": job.required_skills,
        "published_at": job.published_at,
        "deadline": job.deadline,
        "source_name": job.source_name,
        "source_url": job.source_url,
        "apply_channel": job.apply_channel or "",
        "apply_instructions": job.apply_instructions or "",
        "apply_email": job.apply_email or "",
        "apply_keywords": job.apply_keywords or [],
        "email_reference": email_routing.reference_for(job),
        "poster_url": email_routing.public_poster_path(job),
        "salary": job.salary,
        "photo_url": job_media.photo_url(job),
    }


@router.get("/jobs", response_model=list[dict])
def admin_list_jobs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    jobs = db.query(models.Job).order_by(models.Job.published_at.desc()).offset(skip).limit(limit).all()
    return [_job_admin_dict(j) for j in jobs]


@router.post("/jobs", status_code=201, response_model=dict)
def admin_create_job(payload: schemas.AdminJobCreate, db: Session = Depends(get_db)):
    domain = db.get(models.Domain, payload.domain_id) if payload.domain_id else None
    if payload.specialty_id:
        specialty = db.get(models.Specialty, payload.specialty_id)
        if specialty is None or (domain and specialty.domain_id != domain.id):
            raise HTTPException(status_code=422, detail="Spécialité incompatible avec le domaine")
    job = models.Job(
        title=payload.title.strip(),
        company=payload.company.strip(),
        location=payload.location.strip(),
        sector=payload.sector.strip() or (domain.name if domain else ""),
        domain_id=domain.id if domain else None,
        specialty_id=payload.specialty_id,
        contract_type=payload.contract_type,
        description=payload.description,
        requirements=payload.requirements,
        required_skills=[r.model_dump() for r in payload.required_skills],
        published_at=datetime.utcnow(),
        deadline=payload.deadline,
        source_name=payload.source_name or "Saisie manuelle",
        source_url=payload.source_url,
        apply_channel=(payload.apply_channel or "").strip(),
        apply_instructions=(payload.apply_instructions or "").strip(),
        apply_email=(payload.apply_email or "").strip() or None,
        apply_keywords=[
            str(word).strip() for word in (payload.apply_keywords or [])
            if str(word).strip()
        ],
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
    if "domain_id" in data or "specialty_id" in data:
        domain_id = data.get("domain_id", job.domain_id)
        specialty_id = data.get("specialty_id", job.specialty_id)
        domain = db.get(models.Domain, domain_id) if domain_id else None
        specialty = db.get(models.Specialty, specialty_id) if specialty_id else None
        if specialty and (domain is None or specialty.domain_id != domain.id):
            raise HTTPException(status_code=422, detail="Spécialité incompatible avec le domaine")
        if domain and not (data.get("sector") or job.sector or "").strip():
            data["sector"] = domain.name
    for field, value in data.items():
        if field == "required_skills" and value is not None:
            value = [r if isinstance(r, dict) else r for r in value]
        if field == "apply_keywords" and value is not None:
            value = [str(word).strip() for word in value if str(word).strip()]
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
    job_media.remove(job)
    db.delete(job)
    db.commit()
    return {"ok": True}


# --------------------------------------------- Formations (§19, console)

def _learning_dict(row: models.LearningResource) -> dict:
    return {
        "id": row.id,
        "skill": row.skill,
        "title": row.title,
        "provider": row.provider or "",
        "type": row.type,
        "url": row.url or "",
        "source": row.source or "referentiel",
        "hidden": bool(row.hidden),
    }


@router.get("/learning", response_model=list[dict])
def admin_list_learning(
    skill: str = "",
    db: Session = Depends(get_db),
):
    """Référentiel des formations : entrées du JSON (« referentiel ») et
    celles ajoutées en console (« admin », jamais écrasées par la
    synchronisation du démarrage)."""
    query = db.query(models.LearningResource).order_by(
        models.LearningResource.skill, models.LearningResource.title
    )
    if skill.strip():
        query = query.filter(
            models.LearningResource.skill.ilike(f"%{skill.strip()}%")
        )
    return [_learning_dict(r) for r in query.limit(500).all()]


@router.post("/learning", status_code=201, response_model=dict)
def admin_create_learning(
    payload: schemas.LearningResourceIn,
    db: Session = Depends(get_db),
):
    """Ajoute une formation au catalogue proposé aux candidats.

    La compétence doit rester lisible (c'est la clé du plan
    d'apprentissage) ; le lien peut être une formation exacte, un
    catalogue ou une recherche : sa nature est déduite honnêtement.
    """
    skill = payload.skill.strip()
    title = payload.title.strip()
    if not skill or not title:
        raise HTTPException(status_code=422, detail="Compétence et intitulé obligatoires")
    duplicate = (
        db.query(models.LearningResource)
        .filter(
            models.LearningResource.skill == skill,
            models.LearningResource.title == title,
        )
        .first()
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=400,
            detail="Cette formation existe déjà pour cette compétence.",
        )
    row = models.LearningResource(
        skill=skill,
        title=title,
        provider=payload.provider.strip(),
        type=payload.type,
        url=payload.url.strip() or None,
        source="admin",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _learning_dict(row)


@router.put("/learning/{resource_id}", response_model=dict)
def admin_update_learning(
    resource_id: int,
    payload: schemas.LearningResourceUpdateIn,
    db: Session = Depends(get_db),
):
    """Modifie une formation, y compris une ligne du référentiel.

    Une ligne « referentiel » modifiée devient une ligne « admin » : la
    synchronisation du démarrage ne peut plus réécrire le lien cassé.
    Si la compétence ou l'intitulé change, une tombstone masquée conserve
    l'ancienne clé pour empêcher le référentiel de ressusciter l'entrée
    d'origine.
    """
    from app.services.learning import load_resources

    row = db.get(models.LearningResource, resource_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Formation introuvable")
    original = {
        "skill": row.skill,
        "title": row.title,
        "provider": row.provider or "",
        "type": row.type,
        "url": row.url,
    }
    original_key = (original["skill"], original["title"])
    data = payload.model_dump(exclude_unset=True)
    for field in ("skill", "title", "provider", "url"):
        if data.get(field) is not None:
            setattr(row, field, data[field].strip())
    if data.get("type") is not None:
        row.type = data["type"]
    if not row.skill.strip() or not row.title.strip():
        raise HTTPException(status_code=422, detail="Compétence et intitulé obligatoires")
    if data.get("hidden") is not None:
        row.hidden = bool(data["hidden"])
    edited_fields = ("skill", "title", "provider", "type", "url")
    was_referentiel = (row.source or "referentiel") == "referentiel"
    if was_referentiel and any(field in data for field in edited_fields):
        # Retouche volontaire de la console : on protège la ligne pour
        # que le référentiel JSON ne l'écrase pas au prochain démarrage.
        row.source = "admin"
        referential_keys = {
            (skill, item.get("title", ""))
            for skill, items in load_resources().items()
            for item in items
        }
        new_key = (row.skill, row.title)
        if new_key != original_key and original_key in referential_keys:
            db.flush()
            existing = (
                db.query(models.LearningResource)
                .filter(
                    models.LearningResource.skill == original_key[0],
                    models.LearningResource.title == original_key[1],
                )
                .first()
            )
            if existing is None:
                db.add(models.LearningResource(
                    skill=original["skill"],
                    title=original["title"],
                    provider=original["provider"],
                    type=original["type"],
                    url=original["url"],
                    source="referentiel",
                    hidden=True,
                ))
    db.commit()
    db.refresh(row)
    return _learning_dict(row)


@router.delete("/learning/{resource_id}")
def admin_delete_learning(resource_id: int, db: Session = Depends(get_db)):
    """Retire une formation du catalogue proposé aux candidats.

    Une ligne « admin » est supprimée définitivement, sauf si elle
    correspond encore à une entrée du référentiel JSON (cas d'une ligne
    « referentiel » corrigée en console) : elle est alors masquée pour
    ne pas réapparaître au prochain démarrage. L'admin peut la rétablir.
    """
    from app.services.learning import load_resources

    row = db.get(models.LearningResource, resource_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Formation introuvable")

    referential_keys = {
        (skill, item.get("title", ""))
        for skill, items in load_resources().items()
        for item in items
    }
    if (row.source or "referentiel") == "referentiel" or (
        row.skill, row.title
    ) in referential_keys:
        row.source = "referentiel"
        row.hidden = True
        db.commit()
        return {"ok": True, "hidden": True}

    db.delete(row)
    db.commit()
    return {"ok": True, "hidden": False}


@router.post("/learning/{resource_id}/restore", response_model=dict)
def admin_restore_learning(resource_id: int, db: Session = Depends(get_db)):
    """Rétablit une formation retirée du catalogue."""
    row = db.get(models.LearningResource, resource_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Formation introuvable")
    row.hidden = False
    db.commit()
    db.refresh(row)
    return _learning_dict(row)


@router.post("/jobs/{job_id}/photo", response_model=dict)
def admin_upload_job_photo(
    job_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """Photo d'illustration FACULTATIVE de l'offre (publication admin)."""
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    job_media.save(job, file)
    db.commit()
    db.refresh(job)
    return {"ok": True, "photo_url": job_media.photo_url(job)}


@router.delete("/jobs/{job_id}/photo")
def admin_delete_job_photo(job_id: int, db: Session = Depends(get_db)):
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    job_media.remove(job)
    db.commit()
    return {"ok": True}
