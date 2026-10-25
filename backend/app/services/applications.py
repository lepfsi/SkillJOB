"""Suivi des candidatures (§6) : étapes et libellés partagés.

Ces libellés sont PERSISTÉS dans l'historique de chaque candidature :
ils constituent donc une source de vérité unique, utilisée par l'API
(écriture de l'historique) et par l'assistant (lecture).
"""
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
}

# États qui ne sont plus « en cours ».
CLOSED_STATUSES = {"acceptee", "refusee"}


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
