"""Recours après suspension : libellés et fil d'historique partagés.

Le recours reste un objet de modération : chaque dépôt, message du
candidat, demande de complément et décision d'administration est ajouté
au fil ``history``. Les anciens recours, créés avant cette colonne, sont
reconstitués à la lecture pour ne jamais perdre le contexte.
"""
from app import models

STATUS_LABELS = {
    "pending": "En attente",
    "complement": "Complément attendu",
    "accepted": "Accepté",
    "rejected": "Refusé",
}

ACTION_LABELS = {
    "depot": "Dépôt du recours",
    "message": "Message du candidat",
    "complement": "Demande de complément",
    "accepted": "Recours accepté",
    "rejected": "Recours refusé",
}

OPEN_STATUSES = ("pending", "complement")


def append_history(
    row: models.BanAppeal,
    actor: str,
    action: str,
    note: str = "",
    status: str | None = None,
    actor_id: int | None = None,
    actor_name: str | None = None,
) -> dict:
    """Ajoute une étape horodatée au fil du recours."""
    history = list(row.history or [])
    entry = {
        "at": models.utcnow().isoformat(timespec="seconds"),
        "actor": actor,
        "action": action,
        "status": status or row.status,
        "note": (note or "")[:2000],
    }
    if actor_id is not None:
        entry["actor_id"] = actor_id
    if actor_name:
        entry["actor_name"] = actor_name
    history.append(entry)
    row.history = history
    return entry


def history_for(row: models.BanAppeal) -> list[dict]:
    """Fil complet ; reconstitue les anciens recours sans historique."""
    history = list(row.history or [])
    if history:
        return history
    history = [{
        "at": (
            row.created_at.isoformat(timespec="seconds")
            if row.created_at else ""
        ),
        "actor": "candidate",
        "action": "depot",
        "status": "pending",
        "note": row.message or "",
    }]
    if row.reviewed_at:
        history.append({
            "at": row.reviewed_at.isoformat(timespec="seconds"),
            "actor": "admin",
            "action": row.status,
            "status": row.status,
            "note": row.admin_note or "",
        })
    return history
