"""Notifications intelligentes (§52) : digest quotidien.

Chaque jour, chaque candidat ayant activé au moins un canal reçoit les
NOUVELLES offres correspondant à son profil (score >= 45, publiées dans
les dernières 24 h). Filtrage par pertinence pour éviter la surcharge
informationnelle. Planificateur léger (thread daemon) démarré avec
l'application ; activable/désactivable par l'administrateur.
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal
from app.services import settings_store
from app.services.matching import compute_match
from app.services.notifications import dispatch, normalize_prefs
from app.services.skills_taxonomy import load_taxonomy

logger = logging.getLogger("orientskill.digest")

MATCH_THRESHOLD = 45  # correspondance moyenne minimum


def build_digest_for(db: Session, user: models.User, since) -> str:
    """Construit le texte du digest pour UN candidat (testable)."""
    profile = db.query(models.Profile).filter(models.Profile.user_id == user.id).first()
    if profile is None:
        return ""
    taxonomy = load_taxonomy()
    cutoff = since
    jobs = (
        db.query(models.Job)
        .filter(models.Job.published_at >= cutoff)
        .order_by(models.Job.published_at.desc())
        .limit(80)
        .all()
    )
    matches = []
    for job in jobs:
        match = compute_match(profile.skills or [], job.required_skills, taxonomy)
        if match["score"] >= MATCH_THRESHOLD:
            matches.append((job, match))
    if not matches:
        return ""
    lines = [f"Bonjour {user.full_name.split(' ')[0]},",
             f"{len(matches)} nouvelle(s) offre(s) correspondent à votre profil :"]
    for job, match in matches[:5]:
        lines.append(
            f"· {job.title} · {job.company} ({job.location}) · "
            f"correspondance {match['score']}/100"
        )
    lines.append("Connectez-vous à OrientSkill AI pour analyser le match et préparer votre candidature.")
    return "\n".join(lines)


def run_digest_once(db: Session) -> dict:
    """Une passe de digest : retoure {notified, skipped, errors}."""
    since = datetime.utcnow() - timedelta(hours=24)
    notified = skipped = errors = 0
    users = db.query(models.User).filter(models.User.role == "candidate").all()
    for user in users:
        prefs = normalize_prefs(getattr(user, "notification_prefs", None) or {})
        if not any([prefs["email_enabled"], prefs["telegram_enabled"], prefs["whatsapp_enabled"]]):
            skipped += 1
            continue
        try:
            body = build_digest_for(db, user, since)
            if not body:
                skipped += 1
                continue
            results = dispatch(
                db, user,
                "OrientSkill AI : nouvelles offres pour vous",
                body,
            )
            if results and any(r["ok"] for r in results):
                notified += 1
            else:
                errors += 1
        except Exception as exc:
            logger.warning("Digest utilisateur %s : %s", user.id, exc)
            errors += 1
    return {"notified": notified, "skipped": skipped, "errors": errors}


def digest_enabled(db: Session) -> bool:
    conf = settings_store.get_settings(db)
    return bool(conf.get("notifications", {}).get("digest_enabled"))


def _digest_loop(stop_event: threading.Event, interval_hours: float) -> None:
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            if digest_enabled(db):
                result = run_digest_once(db)
                logger.info("Digest exécuté : %s", result)
        except Exception as exc:
            logger.warning("Boucle digest : %s", exc)
        finally:
            db.close()
        stop_event.wait(interval_hours * 3600)


class DigestService:
    """Cycle de vie du planificateur de digest."""

    def __init__(self, interval_hours: float = 24):
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
