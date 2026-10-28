"""Préférences de l'agent carrière (§13) : périmètre, fréquence, validation.

Le mode de travail reste stocké dans ``User.agent_mode`` pour ne pas casser
les parcours existants. Les autres réglages vivent dans ``User.agent_prefs``
(JSON) : ils sont distincts du mode, persistés et réellement appliqués par
les services (veille, alertes, génération de documents).
"""
from datetime import datetime
from typing import Any, Optional

# Catalogue des modes, partagé avec l'API historique /agent/mode.
AGENT_MODES = [
    {
        "id": "accompagnement",
        "label": "Mode accompagnement",
        "description": "Je priorise le conseil et les compétences à renforcer, puis les offres.",
    },
    {
        "id": "preparation",
        "label": "Mode préparation",
        "description": "Je priorise la préparation des CV et lettres ciblés ; vous validez chaque envoi.",
    },
    {
        "id": "veille",
        "label": "Mode veille",
        "description": "Je priorise les nouvelles offres à examiner et je vous informe.",
    },
    {
        "id": "autonome",
        "label": "Mode autonome",
        "description": "Je prépare automatiquement les documents pour vos meilleures correspondances ; vous validez l'envoi.",
    },
]

SCOPES = [
    {
        "id": "tous",
        "label": "Tous les secteurs",
        "description": "L'agent surveille toutes les offres compatibles avec votre profil.",
    },
    {
        "id": "secteur",
        "label": "Mon secteur principal",
        "description": "L'agent privilégie le premier secteur de vos préférences.",
    },
    {
        "id": "region",
        "label": "Ma zone géographique",
        "description": "L'agent privilégie les offres proches de votre localisation.",
    },
]

FREQUENCIES = [
    {
        "id": "quotidienne",
        "label": "Chaque jour",
        "description": "Une passe de veille et d'alertes par jour.",
    },
    {
        "id": "hebdomadaire",
        "label": "Chaque semaine",
        "description": "Une passe automatique le lundi ; le reste reste consultable.",
    },
    {
        "id": "manuelle",
        "label": "Manuelle",
        "description": "Aucune passe automatique : vous consultez l'agent quand vous le souhaitez.",
    },
]

VALIDATIONS = [
    {
        "id": "documents",
        "label": "Validation par document",
        "description": "L'agent peut préparer plusieurs documents ; vous validez chaque envoi.",
    },
    {
        "id": "toujours",
        "label": "Validation à chaque étape",
        "description": "L'agent propose une action à la fois ; vous validez chaque étape.",
    },
]

CANDIDATE_ACTIONS = [
    {
        "id": "prepare_cv",
        "label": "Préparer des CV ciblés",
        "description": "Générer un CV adapté à une offre, depuis le profil validé.",
    },
    {
        "id": "prepare_letter",
        "label": "Préparer des lettres de motivation",
        "description": "Générer une lettre ciblée, depuis le profil validé.",
    },
    {
        "id": "prepare_interview",
        "label": "Préparer les entretiens",
        "description": "Proposer des questions et des conseils pour un entretien.",
    },
    {
        "id": "watch_jobs",
        "label": "Surveiller les offres",
        "description": "Faire apparaître les nouvelles offres et correspondances fortes.",
    },
    {
        "id": "alert_deadlines",
        "label": "Alerter sur les échéances",
        "description": "Signaler les offres compatibles dont la date limite approche.",
    },
]

DEFAULT_PREFS: dict[str, Any] = {
    "scope": "tous",
    "frequency": "quotidienne",
    "validation": "documents",
    "actions": {item["id"]: True for item in CANDIDATE_ACTIONS},
}

_SCOPE_IDS = {item["id"] for item in SCOPES}
_FREQUENCY_IDS = {item["id"] for item in FREQUENCIES}
_VALIDATION_IDS = {item["id"] for item in VALIDATIONS}
_ACTION_IDS = {item["id"] for item in CANDIDATE_ACTIONS}


def normalize_agent_prefs(raw: Optional[dict]) -> dict[str, Any]:
    """Retourne des préférences complètes et valides, sans jamais lever."""
    source = raw if isinstance(raw, dict) else {}
    scope = source.get("scope") if source.get("scope") in _SCOPE_IDS else "tous"
    frequency = (
        source.get("frequency")
        if source.get("frequency") in _FREQUENCY_IDS
        else "quotidienne"
    )
    validation = (
        source.get("validation")
        if source.get("validation") in _VALIDATION_IDS
        else "documents"
    )
    raw_actions = source.get("actions")
    raw_actions = raw_actions if isinstance(raw_actions, dict) else {}
    actions = {
        action_id: bool(raw_actions.get(action_id, True))
        for action_id in _ACTION_IDS
    }
    return {
        "scope": scope,
        "frequency": frequency,
        "validation": validation,
        "actions": actions,
    }


def update_agent_prefs(
    current: Optional[dict], payload: dict[str, Any]
) -> dict[str, Any]:
    """Fusionne un payload partiel ; lève ValueError sur une valeur inconnue."""
    prefs = normalize_agent_prefs(current)
    if "scope" in payload:
        if payload["scope"] not in _SCOPE_IDS:
            raise ValueError("Périmètre d'action invalide.")
        prefs["scope"] = payload["scope"]
    if "frequency" in payload:
        if payload["frequency"] not in _FREQUENCY_IDS:
            raise ValueError("Fréquence de veille invalide.")
        prefs["frequency"] = payload["frequency"]
    if "validation" in payload:
        if payload["validation"] not in _VALIDATION_IDS:
            raise ValueError("Niveau de validation invalide.")
        prefs["validation"] = payload["validation"]
    if "actions" in payload:
        actions = payload["actions"]
        if not isinstance(actions, dict):
            raise ValueError("Format des actions invalide.")
        for key, value in actions.items():
            if key not in _ACTION_IDS:
                raise ValueError(f"Action inconnue : {key}.")
            prefs["actions"][key] = bool(value)
    return prefs


def action_enabled(user: Any, action: str) -> bool:
    """Vrai si l'action est autorisée par les réglages de l'agent."""
    prefs = normalize_agent_prefs(getattr(user, "agent_prefs", None))
    return bool(prefs["actions"].get(action, True))


def frequency_allows_auto(user: Any, now: Optional[datetime] = None) -> bool:
    """Les passes automatiques respectent la fréquence choisie."""
    frequency = normalize_agent_prefs(
        getattr(user, "agent_prefs", None)
    )["frequency"]
    if frequency == "manuelle":
        return False
    if frequency == "hebdomadaire":
        current = now or datetime.utcnow()
        return current.weekday() == 0
    return True


def mode_allowed(user: Any, mode: str) -> bool:
    """Le mode autonome exige une validation par document.

    La validation humaine de l'envoi reste obligatoire dans tous les cas.
    """
    if mode != "autonome":
        return True
    prefs = normalize_agent_prefs(getattr(user, "agent_prefs", None))
    return prefs["validation"] == "documents"


def catalog() -> dict[str, Any]:
    return {
        "scopes": SCOPES,
        "frequencies": FREQUENCIES,
        "validations": VALIDATIONS,
        "actions": CANDIDATE_ACTIONS,
    }
