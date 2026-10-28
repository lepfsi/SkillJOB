"""Alertes planifiées : échéances proches et conseil de l'agent (§25, §52).

Passes exécutées par le planificateur quotidien (services/digest.py) :
- « expiring » : une offre CORRESPONDANT au profil dont la date limite
  arrive à échéance sous 7 jours ; le candidat n'a pas encore postulé ;
- « agent » : le conseil le plus important du moment (délai urgent,
  entretien à préparer, meilleure piste, compétence manquante).

Chaque envoi est journalisé (notification_log) : la même alerte n'est
jamais envoyée deux fois. Le tout respecte les préférences par
événement : sans opt-in e-mail, l'information reste dans l'application
(inbox, briefing de l'agent).
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models
from app.services import agent_prefs
from app.services.matching import LEVEL_STRONG, compute_match
from app.services.notifications import dispatch, normalize_prefs
from app.services.skills_taxonomy import load_taxonomy

logger = logging.getLogger("orientskill.alerts")

MATCH_THRESHOLD = 45   # correspondance moyenne minimum
DEADLINE_WINDOW_DAYS = 7


def _has_applied(applications: list[Any], job_id: int) -> bool:
    return any(a.job_id == job_id for a in applications)


def expiring_matches(
    skills: list,
    jobs: list[Any],
    applications: list[Any],
    taxonomy=None,
    now: Optional[datetime] = None,
) -> list[tuple[models.Job, dict]]:
    """Offres correspondantes dont l'échéance arrive sous 7 jours.

    ``skills`` : liste des compétences du profil (format du profil
    validé). Une offre déjà postulée n'alerte plus.
    """
    now = now or datetime.utcnow()
    results: list[tuple[models.Job, dict]] = []
    for job in jobs:
        if not job.deadline:
            continue
        remaining = (job.deadline - now).days
        if not (0 <= remaining <= DEADLINE_WINDOW_DAYS):
            continue
        if _has_applied(applications, job.id):
            continue
        match = compute_match(skills or [], job.required_skills, taxonomy)
        if match["score"] >= MATCH_THRESHOLD:
            results.append((job, match))
    results.sort(key=lambda pair: pair[0].deadline)
    return results


def build_expiring_body(user: models.User, job: models.Job, match: dict) -> str:
    days = (job.deadline - datetime.utcnow()).days
    delay = (
        "aujourd'hui" if days <= 0
        else f"dans {days} jour" + ("s" if days > 1 else "")
    )
    return "\n".join([
        f"Bonjour {user.full_name.split(' ')[0]},",
        "",
        f"La candidature pour « {job.title} » chez {job.company} "
        f"({job.location}) se termine {delay}.",
        f"Correspondance avec votre profil : {match['score']}/100.",
        "",
        "Connectez-vous à OrientSkill AI : votre CV ciblé et votre lettre "
        "sont prêts en quelques minutes, puis envoyez votre candidature.",
    ])


def build_agent_body(
    user: models.User,
    profile: Optional[models.Profile],
    jobs: list[models.Job],
    applications: list[Any],
    taxonomy=None,
    now: Optional[datetime] = None,
) -> str:
    """Conseil le plus important du moment ; vide si rien à signaler.

    Priorité : délai urgent, entretien à préparer, meilleure
    correspondance, compétence manquante. Jamais d'invention (§47) :
    chaque phrase vient des données réelles.
    """
    if profile is None:
        return ""
    now = now or datetime.utcnow()
    first = (user.full_name or "").split(" ")[0]
    skills = profile.skills or []
    taxonomy = taxonomy or load_taxonomy()
    strong: list[tuple[models.Job, dict]] = []
    best: Optional[tuple[models.Job, dict]] = None
    for job in jobs:
        match = compute_match(skills, job.required_skills, taxonomy)
        if match["score"] >= LEVEL_STRONG:
            strong.append((job, match))
        if best is None or match["score"] > best[1]["score"]:
            best = (job, match)

    # 1) Délai urgent sur une correspondance forte non postulée
    for job, match in strong:
        if job.deadline and 0 <= (job.deadline - now).days <= 3 \
                and not _has_applied(applications, job.id):
            return "\n".join([
                f"Bonjour {first},",
                "",
                f"J'ai repéré une urgence : la candidature pour "
                f"« {job.title} » chez {job.company} se termine bientôt "
                f"(correspondance {match['score']}/100 avec votre profil).",
                "",
                "Connectez-vous à OrientSkill AI : je prépare le CV ciblé "
                "et la lettre, vous n'aurez plus qu'à valider l'envoi.",
            ])

    # 2) Entretien à préparer
    interviews = [
        a for a in applications if a.status == "entretien"
    ]
    if interviews:
        title = interviews[0].job.title if interviews[0].job else "votre poste"
        return "\n".join([
            f"Bonjour {first},",
            "",
            f"Il vous reste un entretien à préparer pour « {title} ». "
            "Je peux générer les questions probables et simuler l'entretien "
            "avec vous.",
            "",
            "Retrouvez la préparation complète dans votre espace OrientSkill AI.",
        ])

    # 3) Meilleure correspondance
    if strong:
        job, match = max(strong, key=lambda pair: pair[1]["score"])
        return "\n".join([
            f"Bonjour {first},",
            "",
            f"Une piste se détache : « {job.title} » chez {job.company} "
            f"({match['score']}/100 de correspondance avec votre profil).",
            "",
            "Connectez-vous à OrientSkill AI pour analyser le match et "
            "préparer votre candidature.",
        ])

    # 4) Compétence manquante la plus fréquente
    if best:
        missing: list[str] = []
        for job in jobs[:10]:
            for name in compute_match(skills, job.required_skills, taxonomy)["missing"]:
                if name not in missing:
                    missing.append(name)
        if missing:
            return "\n".join([
                f"Bonjour {first},",
                "",
                f"Pour décrocher plus d'entretiens, la compétence "
                f"« {missing[0]} » revient le plus souvent dans les offres "
                "qui vous correspondent.",
                "",
                "La page Apprentissage d'OrientSkill AI propose des ressources "
                "pour monter en niveau rapidement.",
            ])
    return ""


def _agent_alerted_today(db: Session, user_id: int) -> bool:
    """Le conseil de l'agent a-t-il déjà été envoyé aujourd'hui ?"""
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(models.NotificationLog)
        .filter(
            models.NotificationLog.user_id == user_id,
            models.NotificationLog.event == "agent",
            models.NotificationLog.sent_at >= start,
        )
        .first()
        is not None
    )


def _already_alerted(db: Session, user_id: int, event: str, job_id: int) -> bool:
    return (
        db.query(models.NotificationLog)
        .filter(
            models.NotificationLog.user_id == user_id,
            models.NotificationLog.event == event,
            models.NotificationLog.job_id == job_id,
        )
        .first()
        is not None
    )


def _wants_email(user: models.User, event: str) -> bool:
    prefs = normalize_prefs(getattr(user, "notification_prefs", None) or {})
    return bool(prefs["email_enabled"] and prefs["email"]
                and prefs["events"].get(event))


def run_alerts_once(db: Session) -> dict:
    """Une passe d'alertes : retoune {notified, skipped, errors}."""
    notified = skipped = errors = 0
    taxonomy = load_taxonomy()
    candidates = db.query(models.User).filter(models.User.role == "candidate").all()
    for user in candidates:
        # Fréquence de veille : manuelle = aucune passe automatique,
        # hebdomadaire = uniquement le lundi.
        if not agent_prefs.frequency_allows_auto(user):
            skipped += 1
            continue
        profile = (
            db.query(models.Profile)
            .filter(models.Profile.user_id == user.id)
            .first()
        )
        if profile is None:
            continue
        applications = (
            db.query(models.Application)
            .filter(models.Application.user_id == user.id)
            .all()
        )
        jobs = db.query(models.Job).all()

        # ---- Événement « expiring » : par offre, une seule fois.
        # Sans opt-in e-mail, l'offre reste visible dans l'application
        # (inbox) : on ne journalise PAS, un opt-in tardif doit pouvoir
        # déclencher l'envoi pendant la fenêtre de 7 jours.
        if agent_prefs.action_enabled(user, "alert_deadlines"):
            for job, match in expiring_matches(
                profile.skills or [], jobs, applications, taxonomy
            ):
                if _already_alerted(db, user.id, "expiring", job.id):
                    continue
                if not _wants_email(user, "expiring"):
                    skipped += 1
                    continue
                try:
                    results = dispatch(
                        db, user,
                        "OrientSkill AI : une offre qui vous correspond expire bientôt",
                        build_expiring_body(user, job, match),
                        event="expiring",
                    )
                    db.add(models.NotificationLog(
                        user_id=user.id, event="expiring", job_id=job.id,
                    ))
                    if results and any(r["ok"] for r in results):
                        notified += 1
                    else:
                        errors += 1
                except Exception as exc:
                    logger.warning("Alerte expiring user %s : %s", user.id, exc)
                    errors += 1

        # ---- Événement « agent » : un conseil par jour au maximum.
        if not agent_prefs.action_enabled(user, "watch_jobs"):
            continue
        if _agent_alerted_today(db, user.id):
            continue
        body = build_agent_body(user, profile, jobs, applications, taxonomy)
        if not body:
            continue
        if not _wants_email(user, "agent"):
            skipped += 1
            continue
        try:
            results = dispatch(
                db, user,
                "OrientSkill AI : votre agent a repéré quelque chose",
                body,
                event="agent",
            )
            db.add(models.NotificationLog(
                user_id=user.id, event="agent",
            ))
            if results and any(r["ok"] for r in results):
                notified += 1
            else:
                errors += 1
        except Exception as exc:
            logger.warning("Alerte agent user %s : %s", user.id, exc)
            errors += 1
    db.commit()
    return {"notified": notified, "skipped": skipped, "errors": errors}
