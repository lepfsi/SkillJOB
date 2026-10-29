"""Boîte administrative commune, distincte du journal d'envoi."""
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.services.admin_alerts import ADMIN_CATEGORIES

RETENTION_DAYS = 90
ACTION_PATHS = {
    "verification": "/admin/verifications",
    "appeal": "/admin/recours",
    "report": "/admin/signalements",
    "ingestion": "/admin/sources",
    "critical": "/admin/equipe-alertes",
}


def filtered_query(db: Session, *, category=None, status="all", since=None,
                   until=None, delivery="all"):
    """Même périmètre pour la liste, les compteurs et la pagination."""
    log = models.AdminNotificationLog
    query = db.query(log).filter(
        log.created_at >= models.utcnow() - timedelta(days=RETENTION_DAYS)
    )
    if category:
        query = query.filter(log.category == category)
    if status == "archived":
        query = query.filter(log.archived_at.is_not(None))
    else:
        query = query.filter(log.archived_at.is_(None))
        if status == "unread":
            query = query.filter(log.marked_read_at.is_(None))
        elif status == "read":
            query = query.filter(log.marked_read_at.is_not(None))
    if since:
        query = query.filter(log.created_at >= datetime.combine(since, time.min))
    if until:
        query = query.filter(log.created_at < datetime.combine(until, time.max))
    if delivery == "sent":
        query = query.filter(log.sent_count > 0, log.failed_count == 0)
    elif delivery == "partial":
        query = query.filter(log.sent_count > 0, log.failed_count > 0)
    elif delivery == "failed":
        query = query.filter(log.sent_count == 0, log.failed_count > 0)
    elif delivery == "recorded":
        query = query.filter(log.sent_count == 0, log.failed_count == 0)
    return query


def counters(query) -> dict:
    log = models.AdminNotificationLog
    counts = query.with_entities(
        log.category, func.count(log.id),
    ).group_by(log.category).all()
    unread = query.filter(log.marked_read_at.is_(None), log.archived_at.is_(None))
    unread_counts = dict(unread.with_entities(
        log.category, func.count(log.id),
    ).group_by(log.category).all())
    return {
        "total": sum(count for _, count in counts),
        "unread": sum(unread_counts.values()),
        "per_category": {
            category: {"total": count, "unread": unread_counts.get(category, 0)}
            for category, count in counts
        },
    }


def notification_dict(log) -> dict:
    status = "recorded"
    if log.sent_count:
        status = "partial" if log.failed_count else "sent"
    elif log.failed_count:
        status = "failed"
    return {
        "id": log.id, "category": log.category,
        "category_label": ADMIN_CATEGORIES.get(log.category, {}).get("label", log.category),
        "subject": log.subject, "body": log.body, "detail": log.detail,
        "recipients": log.recipients, "status": status,
        "sent_count": log.sent_count, "failed_count": log.failed_count,
        "is_unread": log.marked_read_at is None and log.archived_at is None,
        "marked_read_at": log.marked_read_at, "archived_at": log.archived_at,
        "created_at": log.created_at,
        "href": ACTION_PATHS.get(log.category, "/admin/equipe-alertes"),
    }