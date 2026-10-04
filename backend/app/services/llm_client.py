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
    except (URLError, KeyError, ValueError, TimeoutError, OSError):
        return None


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
