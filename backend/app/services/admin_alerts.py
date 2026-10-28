"""Alertes de l'équipe d'administration.

Une équipe de destinataires est configurée par catégorie : vérification de
profil, recours, signalement d'offre, échec de collecte et défaillance
critique. Chaque alerte est journalisée, même quand le service e-mail est
désactivé. Les alertes critiques ont un repli sur les comptes admin pour
ne jamais rester silencieuses.
"""
import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.services import notifications, settings_store

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ADMIN_CATEGORIES: dict[str, dict[str, str]] = {
    "verification": {
        "label": "Demandes de vérification",
        "description": "Un candidat dépose une pièce d'identité à examiner.",
    },
    "appeal": {
        "label": "Recours après suspension",
        "description": "Un compte suspendu conteste une décision.",
    },
    "report": {
        "label": "Signalements d'offres",
        "description": "Une offre est signalée comme frauduleuse, expirée ou discriminante.",
    },
    "ingestion": {
        "label": "Échec de collecte",
        "description": "Une source d'offres ne répond plus ou renvoie un flux invalide.",
    },
    "critical": {
        "label": "Défaillance critique",
        "description": "Le modèle IA ou un service essentiel est indisponible.",
    },
}


def categories_catalog() -> list[dict[str, str]]:
    return [
        {"key": key, **value}
        for key, value in ADMIN_CATEGORIES.items()
    ]


def _default_config() -> dict[str, Any]:
    return json.loads(json.dumps(settings_store.DEFAULTS["admin_alerts"]))


def _normalize_recipients(
    raw_recipients: Any, strict: bool = False
) -> list[dict[str, Any]]:
    recipients: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_recipients or []:
        if not isinstance(raw, dict):
            if strict:
                raise ValueError("Destinataire invalide.")
            continue
        email = str(raw.get("email") or "").strip().lower()
        if not _EMAIL_RE.match(email):
            if strict:
                raise ValueError(f"Adresse e-mail invalide : {email or '(vide)'}.")
            continue
        if email in seen:
            if strict:
                raise ValueError(f"Adresse e-mail en double : {email}.")
            continue
        seen.add(email)
        categories = [
            str(key)
            for key in (raw.get("categories") or [])
            if str(key) in ADMIN_CATEGORIES
        ]
        recipients.append({
            "name": str(raw.get("name") or "").strip()[:120],
            "email": email,
            "categories": categories,
        })
    return recipients


def get_config(db: Session) -> dict[str, Any]:
    config = _default_config()
    row = db.get(models.Setting, "admin_alerts")
    if row is not None and isinstance(row.value, dict):
        config["enabled"] = bool(row.value.get("enabled", config["enabled"]))
        categories = row.value.get("categories") or {}
        config["categories"] = {
            key: bool(categories.get(key, config["categories"].get(key, True)))
            for key in ADMIN_CATEGORIES
        }
        config["recipients"] = _normalize_recipients(
            row.value.get("recipients") or []
        )
    return config


def save_config(db: Session, data: dict[str, Any]) -> dict[str, Any]:
    current = get_config(db)
    enabled = bool(data.get("enabled", current["enabled"]))
    incoming_categories = data.get("categories") or {}
    categories = {
        key: bool(incoming_categories.get(
            key, current["categories"].get(key, True)
        ))
        for key in ADMIN_CATEGORIES
    }
    recipients = _normalize_recipients(
        data.get("recipients", current["recipients"]), strict=True
    )
    if enabled and categories.get("critical"):
        has_critical = any(
            not recipient["categories"]
            or "critical" in recipient["categories"]
            for recipient in recipients
        )
        if not has_critical:
            raise ValueError(
                "Ajoutez au moins un destinataire pour les alertes critiques, "
                "ou désactivez cette catégorie."
            )
    settings_store.update_group(db, "admin_alerts", {
        "enabled": enabled,
        "categories": categories,
        "recipients": recipients,
    })
    _sync_new_recipient_prefs(db, current, get_config(db))
    return get_config(db)


def _recipient_categories(recipient: dict[str, Any]) -> set[str]:
    """Catégories reçues ; liste vide = toutes."""
    selected = set(recipient.get("categories") or [])
    return selected or set(ADMIN_CATEGORIES)


def _sync_new_recipient_prefs(
    db: Session, previous: dict[str, Any], current: dict[str, Any]
) -> None:
    """Active les événements personnels des destinataires nouvellement
    ajoutés (ou nouvellement affectés à une catégorie).

    On n'éteint jamais un événement existant : un administrateur peut
    avoir choisi de recevoir une catégorie à titre personnel même s'il
    n'est plus dans le routage d'équipe.
    """
    old: dict[str, set[str]] = {
        str(r.get("email") or "").lower(): _recipient_categories(r)
        for r in previous.get("recipients", [])
    }
    admins = {
        (user.email or "").lower(): user
        for user in db.query(models.User)
        .filter(models.User.role == "admin")
        .all()
        if user.email
    }
    changed = False
    for recipient in current.get("recipients", []):
        email = str(recipient.get("email") or "").lower()
        user = admins.get(email)
        if user is None:
            continue
        newly_assigned = _recipient_categories(recipient) - old.get(email, set())
        if not newly_assigned:
            continue
        prefs = notifications.normalize_prefs(
            getattr(user, "notification_prefs", None) or {}, "admin"
        )
        for category in newly_assigned:
            if not current.get("categories", {}).get(category, True):
                continue
            event = notifications.ADMIN_CATEGORY_EVENTS.get(category)
            if event:
                prefs["events"][event] = True
        prefs["role_events_migrated"] = True
        user.notification_prefs = prefs
        changed = True
    if changed:
        db.commit()


def _receives(recipient: dict[str, Any], category: str) -> bool:
    return not recipient.get("categories") or category in recipient["categories"]


def recipients_for(config: dict[str, Any], category: str) -> list[dict[str, Any]]:
    if not config.get("enabled"):
        return []
    if not (config.get("categories") or {}).get(category, True):
        return []
    return [
        recipient for recipient in config.get("recipients", [])
        if _receives(recipient, category)
    ]


def test_config(db: Session, category: str) -> dict[str, Any]:
    """Vérifie le routage sans envoyer le moindre e-mail."""
    category = category if category in ADMIN_CATEGORIES else "critical"
    config = get_config(db)
    recipients = recipients_for(config, category)
    if not config.get("enabled"):
        detail = "Les alertes administratives sont désactivées."
    elif not (config.get("categories") or {}).get(category, True):
        detail = "Cette catégorie est désactivée."
    elif not recipients:
        detail = "Aucun destinataire ne reçoit cette catégorie."
    else:
        detail = (
            f"{len(recipients)} destinataire(s) recevraient cette alerte. "
            "Aucun e-mail n'a été envoyé."
        )
    return {
        "ok": bool(recipients),
        "category": category,
        "category_label": ADMIN_CATEGORIES[category]["label"],
        "recipients": [recipient["email"] for recipient in recipients],
        "detail": detail,
    }


def notify_admins(
    db: Session,
    category: str,
    subject: str,
    body: str,
) -> dict[str, Any]:
    """Envoie une alerte aux destinataires de la catégorie et la journalise."""
    category = category if category in ADMIN_CATEGORIES else "critical"
    config = get_config(db)
    recipients = recipients_for(config, category)
    fallback = False
    if not recipients and category == "critical":
        admins = (
            db.query(models.User)
            .filter(models.User.role == "admin")
            .order_by(models.User.id)
            .all()
        )
        recipients = [
            {"name": admin.full_name, "email": admin.email, "categories": []}
            for admin in admins
            if admin.email
        ]
        fallback = bool(recipients)

    sent = 0
    failed = 0
    details: list[str] = []
    # Les destinataires qui possèdent un compte administrateur reçoivent
    # l'alerte via leurs préférences personnelles (catalogue admin). Les
    # adresses externes restent routées directement. Les alertes critiques
    # ignorent l'opt-in et partent sur l'adresse du compte.
    admin_users = {
        (user.email or "").lower(): user
        for user in db.query(models.User)
        .filter(models.User.role == "admin")
        .all()
        if user.email
    }
    if not config.get("enabled"):
        details.append("Alertes administratives désactivées.")
    elif not (config.get("categories") or {}).get(category, True):
        details.append("Catégorie désactivée.")
    elif not recipients:
        details.append("Aucun destinataire configuré pour cette catégorie.")
    else:
        event = notifications.ADMIN_CATEGORY_EVENTS.get(category)
        for recipient in recipients:
            admin_user = admin_users.get(
                str(recipient["email"] or "").lower()
            )
            if admin_user is not None:
                results = notifications.dispatch(
                    db,
                    admin_user,
                    subject,
                    body,
                    event=event,
                    critical=(category == "critical"),
                )
                ok = any(result["ok"] for result in results)
                if results:
                    detail = "; ".join(
                        f"{result['channel']}: {result['detail']}"
                        for result in results
                    )
                else:
                    detail = (
                        "aucun canal e-mail activé pour ce compte "
                        "administrateur"
                    )
            else:
                ok, detail = notifications.send_email(
                    db, recipient["email"], subject, body
                )
            if ok:
                sent += 1
            else:
                failed += 1
                details.append(f"{recipient['email']}: {detail}")
    if fallback:
        details.append("Repli sur les comptes administrateurs.")

    log = models.AdminNotificationLog(
        category=category,
        subject=subject[:255],
        body=body[:8000],
        recipients=[recipient["email"] for recipient in recipients],
        sent_count=sent,
        failed_count=failed,
        detail="\n".join(details)[:2000],
    )
    try:
        db.add(log)
        db.commit()
    except Exception:
        db.rollback()
    return {
        "category": category,
        "sent": sent,
        "failed": failed,
        "recipients": log.recipients,
        "detail": log.detail,
        "fallback": fallback,
    }


def journal(db: Session, limit: int = 50) -> list[dict[str, Any]]:
    rows = (
        db.query(models.AdminNotificationLog)
        .order_by(models.AdminNotificationLog.created_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )
    return [
        {
            "id": row.id,
            "category": row.category,
            "category_label": ADMIN_CATEGORIES.get(
                row.category, {}
            ).get("label", row.category),
            "subject": row.subject,
            "body": row.body,
            "recipients": row.recipients or [],
            "sent_count": row.sent_count,
            "failed_count": row.failed_count,
            "detail": row.detail,
            "created_at": row.created_at,
        }
        for row in rows
    ]
