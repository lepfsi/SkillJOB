"""Suivi des candidatures (§6) : étapes, libellés et transitions partagés.

Ces libellés sont PERSISTÉS dans l'historique de chaque candidature :
ils constituent donc une source de vérité unique, utilisée par l'API
(écriture de l'historique) et par l'assistant (lecture). Les transitions
autorisées par rôle sont appliquées côté API, jamais seulement dans l'UI.
"""
from datetime import datetime, timezone
from typing import Optional

# Étapes du pipeline, dans l'ordre. « refusee » est un état terminal
# hors pipeline : on ne le franchit pas, on s'y arrête.
PIPELINE = [
    "identifiee",
    "cv_prepare",
    "envoyee",
    "en_attente",
    "entretien",
    "offre",
    "acceptee",
]

STATUS_LABELS = {
    "identifiee": "Candidature identifiée",
    "cv_prepare": "CV ciblé préparé",
    "envoyee": "Candidature envoyée",
    "en_attente": "En attente de réponse",
    "entretien": "Entretien à préparer",
    "offre": "Offre reçue",
    "acceptee": "Candidature acceptée",
    "refusee": "Candidature refusée",
    "retiree": "Candidature retirée",
    "declinee": "Offre déclinée",
}

# États qui ne sont plus « en cours ».
CLOSED_STATUSES = {"acceptee", "refusee", "retiree", "declinee"}

# Tous les statuts connus. Doit rester aligné sur
# ``schemas.APPLICATION_STATUSES`` (test de cohérence dédié).
ALL_STATUSES = set(STATUS_LABELS)

# Transitions autorisées par rôle. Un candidat prépare et envoie sa
# candidature, puis accepte ou décline une offre. Le recruteur instruit
# la candidature. L'admin peut arbitrer n'importe quel statut avec motif.
CANDIDATE_TRANSITIONS: dict[str, set[str]] = {
    "identifiee": {"cv_prepare", "envoyee", "retiree"},
    "cv_prepare": {"envoyee", "retiree"},
    "envoyee": {"retiree"},
    "en_attente": {"retiree"},
    "entretien": {"retiree"},
    "offre": {"acceptee", "declinee", "retiree"},
}

RECRUITER_TRANSITIONS: dict[str, set[str]] = {
    "envoyee": {"en_attente", "entretien", "refusee"},
    "en_attente": {"entretien", "refusee"},
    "entretien": {"offre", "refusee"},
    "offre": {"refusee"},
}

ROLE_LABELS = {
    "candidate": "candidat",
    "recruiter": "recruteur",
    "admin": "administrateur",
}


def label_for(status: Optional[str]) -> str:
    """Libellé français d'un statut, sans jamais inventer : un statut
    inconnu est renvoyé tel quel."""
    if not status:
        return "Statut inconnu"
    return STATUS_LABELS.get(status, status)


def next_status(status: str) -> Optional[str]:
    """Étape suivante du pipeline (None si terminée ou refusée)."""
    if status not in PIPELINE:
        return None
    index = PIPELINE.index(status)
    return PIPELINE[index + 1] if index + 1 < len(PIPELINE) else None


def can_transition(role: str, current: str, target: str) -> bool:
    """Transition autorisée pour ce rôle et cet état courant ?"""
    if target not in ALL_STATUSES or target == current:
        return False
    if role == "admin":
        return True
    if current in CLOSED_STATUSES:
        return False
    if role == "candidate":
        return target in CANDIDATE_TRANSITIONS.get(current, set())
    if role == "recruiter":
        return target in RECRUITER_TRANSITIONS.get(current, set())
    return False


def transition_detail(role: str, current: str, target: str) -> str:
    """Message d'erreur actionnable pour une transition refusée."""
    role_label = ROLE_LABELS.get(role, role)
    return (
        f"Transition non autorisée pour le {role_label} : "
        f"{label_for(current)} → {label_for(target)}."
    )


def timeline_entry(
    event: str, by: str = "", reason: str = ""
) -> dict[str, str]:
    """Événement d'historique avec auteur et motif optionnels."""
    entry = {
        "at": datetime.now(timezone.utc)
        .replace(tzinfo=None)
        .isoformat(timespec="seconds"),
        "event": event,
    }
    if by:
        entry["by"] = by
    if reason:
        entry["reason"] = reason
    return entry
