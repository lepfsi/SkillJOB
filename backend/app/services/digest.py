"""Notifications intelligentes (§52) : alertes d'offres.

Deux fréquences au choix du candidat : immédiate (fenêtre d'une heure)
ou résumé quotidien (fenêtre de 24 h, après l'heure choisie par
l'administrateur). Dans les deux cas, un seul e-mail d'offres par jour :
les autres correspondances restent visibles dans l'application. Le
planificateur léger (thread daemon) tourne toutes les heures et reste
activable/désactivable par l'administrateur.
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal
from app.services import agent_prefs, settings_store
from app.services.matching import compute_match
from app.services.notifications import (
    DEFAULT_EMAIL_MIN_MATCH,
    dispatch,
    job_alert_sent_today,
    normalize_prefs,
)
from app.services.skills_taxonomy import load_taxonomy

logger = logging.getLogger("orientskill.digest")

MATCH_THRESHOLD = 45  # correspondance moyenne minimum : visible in-app
EMAIL_THRESHOLD = DEFAULT_EMAIL_MIN_MATCH  # 61 : strictement plus de 60 % e-mail


WINDOW_DAILY = timedelta(hours=24)
WINDOW_IMMEDIATE = timedelta(hours=1)
DIGEST_LIMIT = 5


def digest_matches_for(
    db: Session,
    user: models.User,
    since,
    exclude_job_ids: Optional[set[int]] = None,
    min_score: int = MATCH_THRESHOLD,
) -> list[tuple[models.Job, dict]]:
    """Offres récentes qui correspondent au profil, hors offres déjà

    envoyées par e-mail. ``min_score`` filtre les offres éligibles à
    l'e-mail (>= 61 par défaut) ; entre 45 % et 60 % restent in-app.
    """
    profile = (
        db.query(models.Profile)
        .filter(models.Profile.user_id == user.id)
        .first()
    )
    if profile is None:
        return []
    taxonomy = load_taxonomy()
    jobs = (
        db.query(models.Job)
        .filter(models.Job.published_at >= since)
        .order_by(models.Job.published_at.desc())
        .limit(80)
        .all()
    )
    matches: list[tuple[models.Job, dict]] = []
    excluded = exclude_job_ids or set()
    for job in jobs:
        if job.id in excluded:
            continue
        match = compute_match(
            profile.skills or [], job.required_skills, taxonomy
        )
        if match["score"] >= min_score:
            matches.append((job, match))
    return matches


def _format_digest(user: models.User, matches: list[tuple]) -> str:
    if not matches:
        return ""
    first_name = (getattr(user, "full_name", "") or "").split(" ")[0]
    lines = [
        f"Bonjour {first_name},",
        f"{len(matches)} nouvelle(s) offre(s) correspondent à votre profil :",
    ]
    for job, match in matches[:DIGEST_LIMIT]:
        lines.append(
            f"· {job.title} · {job.company} ({job.location}) · "
            f"correspondance {match['score']}/100"
        )
    lines.append(
        "Connectez-vous à OrientSkill AI pour analyser le match et "
        "préparer votre candidature."
    )
    return "\n".join(lines)


def build_digest_for(db: Session, user: models.User, since) -> str:
    """Construit le texte du digest pour UN candidat (testable)."""
    return _format_digest(user, digest_matches_for(db, user, since))


def _already_digested_today(
    db: Session, user_id: int, now: datetime
) -> bool:
    """Plafond : un seul e-mail d'offres par jour et par candidat.

    La boîte in-app continue de recevoir toutes les correspondances ; ce
    plafond ne concerne que l'e-mail, pour éviter la surcharge.
    """
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(models.NotificationLog.id)
        .filter(
            models.NotificationLog.user_id == user_id,
            models.NotificationLog.event == "new_match",
            models.NotificationLog.sent_at >= start,
        )
        .first()
        is not None
    )


def _digested_job_ids(db: Session, user_id: int) -> set[int]:
    """Offres déjà envoyées à ce candidat : jamais deux fois le même job."""
    rows = (
        db.query(models.NotificationLog.job_id)
        .filter(
            models.NotificationLog.user_id == user_id,
            models.NotificationLog.event == "new_match",
        )
        .all()
    )
    return {row[0] for row in rows if row[0] is not None}


def run_digest_for_user(
    db: Session,
    user: models.User,
    now: Optional[datetime] = None,
    digest_hour: int = 8,
) -> dict:
    """Une passe pour un candidat : immédiate (fenêtre 1 h) ou quotidienne.

    Un seul e-mail d'alerte emploi par utilisateur et par jour (partagé
    avec les échéances et l'agent) ; le reste reste visible in-app.
    """
    now = now or datetime.utcnow()
    if not agent_prefs.frequency_allows_auto(user, now):
        return {"notified": 0, "skipped": 1, "errors": 0}
    prefs = normalize_prefs(
        getattr(user, "notification_prefs", None) or {},
        getattr(user, "role", "candidate"),
    )
    if not any([
        prefs["email_enabled"],
        prefs["telegram_enabled"],
        prefs["whatsapp_enabled"],
    ]):
        return {"notified": 0, "skipped": 1, "errors": 0}
    if not agent_prefs.action_enabled(user, "watch_jobs"):
        return {"notified": 0, "skipped": 1, "errors": 0}
    if job_alert_sent_today(db, user.id):
        return {"notified": 0, "skipped": 1, "errors": 0}
    frequency = prefs.get("email_frequency", "daily")
    if frequency == "daily" and now.hour < int(digest_hour):
        return {"notified": 0, "skipped": 1, "errors": 0}
    if _already_digested_today(db, user.id, now):
        return {"notified": 0, "skipped": 1, "errors": 0}
    window = WINDOW_IMMEDIATE if frequency == "immediate" else WINDOW_DAILY
    min_score = int(prefs.get("email_min_match") or EMAIL_THRESHOLD)
    matches = digest_matches_for(
        db,
        user,
        now - window,
        _digested_job_ids(db, user.id),
        min_score=min_score,
    )
    if not matches:
        return {"notified": 0, "skipped": 1, "errors": 0}
    try:
        results = dispatch(
            db, user,
            "OrientSkill AI : nouvelles offres pour vous",
            _format_digest(user, matches),
            event="new_match",
        )
        if results and any(r["ok"] for r in results):
            for job, _match in matches[:DIGEST_LIMIT]:
                db.add(models.NotificationLog(
                    user_id=user.id, event="new_match", job_id=job.id,
                ))
            db.commit()
            return {"notified": 1, "skipped": 0, "errors": 0}
        return {"notified": 0, "skipped": 0, "errors": 1}
    except Exception as exc:
        logger.warning("Digest utilisateur %s : %s", user.id, exc)
        return {"notified": 0, "skipped": 0, "errors": 1}


def run_digest_once(db: Session) -> dict:
    """Une passe de digest : retourne {notified, skipped, errors}."""
    now = datetime.utcnow()
    conf = settings_store.get_settings(db)
    digest_hour = int(conf.get("notifications", {}).get("digest_hour", 8) or 8)
    notified = skipped = errors = 0
    users = db.query(models.User).filter(models.User.role == "candidate").all()
    for user in users:
        result = run_digest_for_user(db, user, now, digest_hour)
        notified += result["notified"]
        skipped += result["skipped"]
        errors += result["errors"]
    return {"notified": notified, "skipped": skipped, "errors": errors}


def digest_enabled(db: Session) -> bool:
    conf = settings_store.get_settings(db)
    return bool(conf.get("notifications", {}).get("digest_enabled"))


def _digest_loop(stop_event: threading.Event, interval_hours: float) -> None:
    from app.services.alerts import run_alerts_once

    while not stop_event.is_set():
        db = SessionLocal()
        try:
            if digest_enabled(db):
                result = run_digest_once(db)
                logger.info("Digest exécuté : %s", result)
            # Alertes d'échéances et de l'agent : indépendantes du digest,
            # elles respectent les préférences par événement de chacun.
            alerts = run_alerts_once(db)
            if alerts["notified"] or alerts["errors"]:
                logger.info("Alertes exécutées : %s", alerts)
        except Exception as exc:
            logger.warning("Boucle digest : %s", exc)
        finally:
            db.close()
        stop_event.wait(interval_hours * 3600)


class DigestService:
    """Cycle de vie du planificateur de digest."""

    def __init__(self, interval_hours: float = 1):
        self.interval_hours = interval_hours
        self.stop_event: Optional[threading.Event] = None
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event = threading.Event()
        self.thread = threading.Thread(
            target=_digest_loop,
            args=(self.stop_event, self.interval_hours),
            daemon=True,
        )
        self.thread.start()
        logger.info("Planificateur de digest démarré (toutes les %s h).", self.interval_hours)

    def stop(self) -> None:
        if self.stop_event:
            self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
            self.thread = None


digest_service = DigestService()
