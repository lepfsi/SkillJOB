"""Store de paramètres d'administration (table ``settings``).

Groupes : ``smtp`` (notifications e-mail), ``llm`` (assistant IA),
``aggregators`` (Telegram, WhatsApp). Les secrets ne sont jamais
renvoyés en clair : seule la présence (`*_set`) est exposée, et une
valeur vide soumise conserve le secret existant.
"""
import json
from typing import Any

from sqlalchemy.orm import Session

from app import models

# Clés sensibles : masquées en lecture, non écrasées si soumises vides.
SECRET_KEYS = {"password", "api_key", "bot_token"}

DEFAULTS: dict[str, dict[str, Any]] = {
    "smtp": {
        "host": "",
        "port": 587,
        "username": "",
        "password": "",
        "from_email": "",
        "use_tls": True,
        "enabled": False,
    },
    "llm": {
        "provider": "rules",          # "rules" | "openai"
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "enabled": False,
    },
    "aggregators": {
        "telegram": {"bot_token": "", "chat_id": "", "enabled": False},
        "whatsapp": {"provider": "", "api_key": "", "phone_number_id": "", "enabled": False},
    },
    "notifications": {
        # Notifications intelligentes (§52) : digest quotidien des offres
        "digest_enabled": False,
        "digest_hour": 8,
    },
}


def _mask(group: str, value: dict[str, Any]) -> dict[str, Any]:
    """Retourne la configuration lisible : secrets remplacés par `<set>`."""
    out = json.loads(json.dumps(value))  # copie profonde (petites configs)
    if group == "llm":
        out["api_key_set"] = bool(value.get("api_key"))
        out["api_key"] = "<set>" if value.get("api_key") else ""
    elif group == "smtp":
        out["password_set"] = bool(value.get("password"))
        out["password"] = "<set>" if value.get("password") else ""
    elif group == "aggregators":
        for chan in ("telegram", "whatsapp"):
            if chan in out:
                out[chan]["api_key_set"] = bool(value.get(chan, {}).get("api_key"))
                out[chan]["api_key"] = "<set>" if value.get(chan, {}).get("api_key") else ""
                out[chan]["bot_token_set"] = bool(value.get(chan, {}).get("bot_token"))
                out[chan]["bot_token"] = "<set>" if value.get(chan, {}).get("bot_token") else ""
    return out


def _load_group(db: Session, group: str) -> dict[str, Any]:
    row = db.get(models.Setting, group)
    base = json.loads(json.dumps(DEFAULTS.get(group, {})))
    if row is not None and isinstance(row.value, dict):
        base.update(row.value)
    return base


def get_settings(db: Session) -> dict[str, Any]:
    """Tous les groupes, secrets masqués."""
    return {group: _mask(group, _load_group(db, group)) for group in DEFAULTS}


def get_raw_group(db: Session, group: str) -> dict[str, Any]:
    """Configuration brute (secrets inclus) : usage interne uniquement."""
    return _load_group(db, group)


def update_group(db: Session, group: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Fusionne puis enregistre un groupe ; retourne la version masquée."""
    if group not in DEFAULTS:
        raise KeyError(group)
    current = _load_group(db, group)
    merged = _merge(current, payload)
    row = db.get(models.Setting, group)
    if row is None:
        row = models.Setting(key=group, value=merged)
        db.add(row)
    else:
        row.value = merged
    db.commit()
    return _mask(group, merged)


def _merge(current: dict, payload: dict) -> dict:
    out = json.loads(json.dumps(current))
    for key, value in payload.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        elif key in SECRET_KEYS and (value is None or value == "" or value == "<set>"):
            continue  # secret existant conservé
        else:
            out[key] = value
    return out
