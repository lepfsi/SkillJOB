"""Bot Telegram (§25bis) : canal conversationnel d'accès à la plateforme.

Consultation d'opportunités en langage simple, via les mécanismes
officiels (Bot API, long polling). Le bot est ACTIVÉ par
l'administrateur (Paramètres · agrégateurs) ; sans token, rien ne tourne.
"""
import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal
from app.services import settings_store

logger = logging.getLogger("orientskill.telegram")

HELP_TEXT = (
    "OrientSkill AI · Assistant Telegram\n\n"
    "/start · démarrer (affiche votre chat ID)\n"
    "/offres [métier] · offres récentes (ex. /offres comptable)\n"
    "/help · cette aide\n\n"
    "Pour recevoir les notifications : copiez le chat ID affiché par "
    "/start dans vos paramètres OrientSkill (Notifications)."
)

# Chats récemment vus par le bot (permet à l'utilisateur de retrouver
# son chat ID depuis la plateforme). Mémoire du process uniquement.
SEEN_CHATS: dict[int, dict] = {}


def _record_chat(message: dict) -> None:
    """Mémorise un chat vu via getUpdates (chat_id, nom, @pseudo)."""
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    SEEN_CHATS[chat_id] = {
        "chat_id": chat_id,
        "name": " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")])) or chat.get("title") or "",
        "username": chat.get("username") or "",
    }


def _api(token: str, method: str, params: Optional[dict] = None, timeout: int = 12):
    base = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        base += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(base, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _answer_offers(db: Session, query: str) -> str:
    """Liste les 5 offres les plus récentes (filtrées par mots-clés)."""
    jobs = db.query(models.Job).order_by(models.Job.published_at.desc()).limit(60)
    items = jobs.all()
    needle = re.sub(r"^/offres?\s*", "", query or "").strip().lower()
    if needle:
        items = [
            j for j in items
            if needle in j.title.lower() or needle in j.description.lower()
            or needle in j.sector.lower()
        ]
    if not items:
        return "Aucune offre récente ne correspond à cette recherche."
    lines = ["Offres récentes :"]
    for j in items[:5]:
        lines.append(
            f"· {j.title} · {j.company} ({j.location}, {j.contract_type})"
        )
    lines.append("Détails et candidature sur la plateforme OrientSkill AI.")
    return "\n".join(lines)


def handle_command(text: str, chat_id) -> str:
    """Répond à une commande (testable sans réseau)."""
    cmd = (text or "").strip().lower()
    db = SessionLocal()
    try:
        if cmd.startswith("/start"):
            return (
                f"Bienvenue sur OrientSkill AI !\n\n"
                f"Votre chat ID est : {chat_id}\n"
                "Copiez ce numéro dans votre compte OrientSkill, section "
                "« Notifications », champ Telegram, pour recevoir les "
                "alertes ici.\n\n"
                "Envoyez /offres pour voir les opportunités récentes, ou "
                "/offres comptable pour filtrer par métier."
            )
        if cmd.startswith("/help"):
            return HELP_TEXT
        if cmd.startswith("/offres"):
            return _answer_offers(db, text)
        return (
            "Commande inconnue. Essayez /offres [métier] ou /help."
        )
    finally:
        db.close()


def _poll_loop(stop_event: threading.Event, token: str) -> None:
    """Long polling officiel de la Bot API (getUpdates)."""
    offset = None
    while not stop_event.is_set():
        try:
            params = {"timeout": 25}
            if offset:
                params["offset"] = offset
            data = _api(token, "getUpdates", params, timeout=30)
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message") or {}
                chat_id = message.get("chat", {}).get("id")
                text = message.get("text") or ""
                if not chat_id or not text:
                    continue
                _record_chat(message)
                reply = handle_command(text, chat_id)
                _api(token, "sendMessage", {
                    "chat_id": chat_id,
                    "text": reply[:1500],
                })
        except Exception as exc:  # réseau, token invalide… : on retente
            logger.warning("Polling Telegram : %s", exc)
            stop_event.wait(5)


class TelegramBotService:
    """Gestion du cycle de vie du bot (démarré par le lifespan FastAPI)."""

    def __init__(self):
        self.stop_event: Optional[threading.Event] = None
        self.thread: Optional[threading.Thread] = None

    def start_if_configured(self) -> bool:
        db = SessionLocal()
        try:
            conf = settings_store.get_raw_group(db, "aggregators").get("telegram", {})
            token = conf.get("bot_token")
            if not (conf.get("enabled") and token):
                return False
        finally:
            db.close()
        if self.thread and self.thread.is_alive():
            return True
        self.stop_event = threading.Event()
        self.thread = threading.Thread(
            target=_poll_loop, args=(self.stop_event, token), daemon=True
        )
        self.thread.start()
        logger.info("Bot Telegram démarré (polling).")
        return True

    def stop(self) -> None:
        if self.stop_event:
            self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=3)
            self.thread = None


bot_service = TelegramBotService()
