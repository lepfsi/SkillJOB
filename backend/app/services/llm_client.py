"""Client LLM partagé : configuration via l'admin (table settings) avec
repli sur les variables d'environnement. Utilisé par l'assistant et les
tests de connexion administrateur.
"""
import json
import urllib.request
from typing import Any, Optional
from urllib.error import URLError

from sqlalchemy.orm import Session

from app import config
from app.services import settings_store


def get_llm_config(db: Session) -> dict[str, Any]:
    """Configuration active : settings admin prioritaires, sinon env."""
    raw = settings_store.get_raw_group(db, "llm")
    api_key = raw.get("api_key") or config.LLM_API_KEY
    provider = raw.get("provider") if raw.get("api_key") else (
        raw.get("provider") if raw.get("provider") != "rules" else config.LLM_PROVIDER
    )
    if raw.get("enabled") and api_key:
        provider = "openai"
    return {
        "enabled": bool(api_key) and provider == "openai",
        "provider": provider,
        "model": raw.get("model") or config.LLM_MODEL,
        "base_url": raw.get("base_url") or config.LLM_BASE_URL,
        "api_key": api_key,
    }


def chat_completion(
    db: Session,
    messages: list[dict[str, str]],
    max_tokens: int = 400,
    timeout: int = 20,
) -> Optional[str]:
    """Appel OpenAI-compatible ; None si désactivé ou en échec (fallback règles)."""
    conf = get_llm_config(db)
    if not conf["enabled"]:
        return None
    payload = json.dumps({
        "model": conf["model"],
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    request = urllib.request.Request(
        conf["base_url"].rstrip("/") + "/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {conf['api_key']}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except (URLError, KeyError, ValueError, TimeoutError, OSError) as exc:
        _notify_admin_failure(db, conf, str(exc)[:120])
        return None


# Anti-spam : au plus une notification admin par heure de défaillance.
_last_failure_notified: "float | None" = None


def _notify_admin_failure(db, conf: dict, error: str) -> None:
    """Défaillance du modèle IA → notification des administrateurs
    (leurs canaux configurés). La clé API n'apparaît JAMAIS dans le
    message. Best effort : aucune exception ne remonte à l'appelant."""
    global _last_failure_notified
    import time as _time

    now = _time.time()
    if _last_failure_notified is not None and now - _last_failure_notified < 3600:
        return
    _last_failure_notified = now
    try:
        from app import models as _models
        from app.services.notifications import dispatch

        admins = db.query(_models.User).filter(_models.User.role == "admin").all()
        for admin in admins:
            dispatch(
                db, admin,
                "OrientSkill AI : défaillance du modèle IA",
                f"L'appel au modèle ({conf.get('model') or 'non précisé'}, "
                f"{conf.get('base_url')}) a échoué : {error}. L'assistant "
                "passe en mode local. Vérifiez la clé API dans "
                "Paramètres > LLM. (La clé n'apparaît jamais dans ce message.)",
            )
    except Exception:
        pass  # notifier ne doit jamais casser l'assistant


def test_connection(db: Session) -> tuple[bool, str]:
    """Test administrateur : ping minimal du LLM configuré."""
    conf = get_llm_config(db)
    if not conf["enabled"]:
        return False, "LLM désactivé ou clé absente (mode règles locales actif)."
    reply = chat_completion(
        db,
        [{"role": "user", "content": "Réponds uniquement : OK"}],
        max_tokens=5,
        timeout=10,
    )
    if reply:
        return True, f"Connexion réussie (modèle : {conf['model']})."
    return False, "Échec de l'appel : vérifiez la clé, l'URL de base et le modèle."
