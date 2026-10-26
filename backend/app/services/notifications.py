"""Notifications multi-canaux (§25) : e-mail (SMTP), Telegram, WhatsApp.

Les préférences appartiennent à l'utilisateur (canaux + coordonnées).
Les identifiants des services sont ceux configurés par l'administrateur
(settings SMTP / agrégateurs). Envois au mieux (best effort) : un échec
d'envoi ne casse jamais la requête métier ; il est journalisé côté
réponse pour le test manuel uniquement.
"""
import json
import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Optional
from urllib.parse import quote

import urllib.request

from app.services import settings_store

logger = logging.getLogger("orientskill.notifications")

# ------------------------------------------------- Événements (§25, §52)
# Types d'événements notifiables. Le candidat choisit, POUR CHAQUE
# événement, s'il veut aussi l'e-mail ; sinon la notification reste
# dans l'application (inbox / messagerie / briefing).

EVENT_TYPES: dict[str, str] = {
    "new_match": "Nouvelle offre correspondant au profil",
    "expiring": "Offre correspondante dont la date limite approche",
    "agent": "Conseil ou alerte importante de l'agent",
    "message": "Message d'un recruteur",
    "application": "Mise à jour d'une candidature",
    "verification_decision": "Décision sur la vérification de votre profil",
}

DEFAULT_PREFS: dict[str, Any] = {
    "email_enabled": False,
    "email": "",
    "whatsapp_enabled": False,
    "whatsapp_number": "",
    "telegram_enabled": False,
    "telegram_username": "",
    # Choix par événement : e-mail souhaité (false = in-app uniquement).
    "events": {event: False for event in EVENT_TYPES},
}


def normalize_prefs(raw: Optional[dict]) -> dict[str, Any]:
    prefs = {**DEFAULT_PREFS, **(raw or {})}
    for key in ("email_enabled", "whatsapp_enabled", "telegram_enabled"):
        prefs[key] = bool(prefs.get(key))
    for key in ("email", "whatsapp_number", "telegram_username"):
        prefs[key] = str(prefs.get(key) or "").strip()
    events = prefs.get("events") or {}
    prefs["events"] = {
        event: bool(events.get(event, False)) for event in EVENT_TYPES
    }
    return prefs


def email_wanted(prefs: dict, event: Optional[str]) -> bool:
    """E-mail souhaité pour cet événement ? (True si pas d'événement :
    envoi manuel / test des canaux.)"""
    if not event:
        return True
    return bool((prefs.get("events") or {}).get(event, False))


# ------------------------------------------------------------- canaux

def _add_attachments(msg: EmailMessage, attachments: Optional[list[Any]]) -> None:
    """Ajoute des pièces jointes en conservant leur type MIME.

    Deux formes acceptées : dictionnaire (filename, content, maintype,
    subtype) pour les flux entrants, ou couple (filename, bytes) pour les
    PDF historiques. Un type inconnu retombe sur application/octet-stream.
    """
    for item in attachments or []:
        if isinstance(item, dict):
            filename = str(item.get("filename") or "piece-jointe")
            content = item.get("content") or b""
            maintype = str(item.get("maintype") or "application")
            subtype = str(item.get("subtype") or "octet-stream")
        else:
            filename, content = item[0], item[1]
            maintype, subtype = "application", "pdf"
        msg.add_attachment(
            content,
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )


def send_email(
    db,
    to_email: str,
    subject: str,
    body: str,
    attachments: Optional[list[Any]] = None,
    reply_to: str = "",
) -> tuple[bool, str]:
    """Envoie un e-mail texte, avec pièces jointes optionnelles.

    ``attachments`` accepte des dictionnaires (voir ``_add_attachments``)
    pour les calendriers .ics et les CV/lettres reçus par e-mail.
    """
    conf = settings_store.get_raw_group(db, "smtp")
    if not (conf.get("enabled") and conf.get("host") and to_email):
        return False, "Service e-mail non configuré (voir administrateur)."
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = conf.get("from_email") or conf.get("username") or "no-reply@orientskill.cm"
        msg["To"] = to_email
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.set_content(body, charset="utf-8")
        _add_attachments(msg, attachments)
        with smtplib.SMTP(conf["host"], int(conf.get("port") or 587), timeout=8) as server:
            if conf.get("use_tls", True):
                server.starttls()
            if conf.get("username") and conf.get("password"):
                server.login(conf["username"], conf["password"])
            server.send_message(msg)
        return True, "E-mail envoyé."
    except Exception as exc:
        logger.warning("Envoi e-mail échoué : %s", exc)
        return False, f"Échec e-mail : {exc}"


def send_application_email(
    db,
    to_email: str,
    subject: str,
    body: str,
    reply_to: str = "",
    attachments: Optional[list[tuple[str, bytes]]] = None,
) -> tuple[bool, str]:
    """Candidature transférée au publieur : corps texte + PDF joints.

    ``reply_to`` : adresse du candidat ; la réponse du recruteur part
    directement chez lui (notre adresse reste en expéditeur pour la
    traçabilité SMTP). ``attachments`` : liste (nom_fichier, bytes PDF).
    """
    conf = settings_store.get_raw_group(db, "smtp")
    if not (conf.get("enabled") and conf.get("host") and to_email):
        return False, "Service e-mail non configuré (voir administrateur)."
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = conf.get("from_email") or conf.get("username") or "candidatures@orientskill.cm"
        msg["To"] = to_email
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.set_content(body, charset="utf-8")
        _add_attachments(msg, attachments)
        with smtplib.SMTP(conf["host"], int(conf.get("port") or 587), timeout=15) as server:
            if conf.get("use_tls", True):
                server.starttls()
            if conf.get("username") and conf.get("password"):
                server.login(conf["username"], conf["password"])
            server.send_message(msg)
        return True, "Candidature transmise par e-mail."
    except Exception as exc:
        logger.warning("Envoi candidature e-mail échoué : %s", exc)
        return False, f"Échec e-mail : {exc}"


def _telegram_error_detail(exc: Exception) -> str:
    """Traduit les erreurs de l'API Telegram en message actionnable."""
    import json as _json
    from urllib.error import HTTPError

    if isinstance(exc, HTTPError):
        try:
            body = _json.loads(exc.read().decode("utf-8", errors="ignore"))
            description = body.get("description", "")
        except Exception:
            description = str(exc)
        desc = description.lower()
        if "chat not found" in desc:
            return (
                "Chat introuvable : ouvrez une conversation avec le bot dans "
                "Telegram, envoyez /start, puis copiez le chat ID (nombre) "
                "affiché par le bot dans vos paramètres."
            )
        if "unauthorized" in desc or exc.code == 401:
            return "Token du bot invalide : vérifiez le token @BotFather côté administrateur."
        if "bot was blocked" in desc:
            return "Le bot a été bloqué par ce destinataire dans Telegram."
        if "not found" in desc and "token" in desc:
            return "Token du bot introuvable : vérifiez la configuration administrateur."
        return f"Telegram : {description or exc}"
    return f"Échec Telegram : {exc}"


def send_telegram(db, chat_id: str, text: str) -> tuple[bool, str]:
    conf = settings_store.get_raw_group(db, "aggregators").get("telegram", {})
    token = conf.get("bot_token")
    if not (conf.get("enabled") and token and chat_id):
        return False, "Canal Telegram non configuré (voir administrateur)."
    from urllib.error import HTTPError, URLError

    url = (
        f"https://api.telegram.org/bot{token}/sendMessage"
        f"?chat_id={quote(str(chat_id).strip())}&text={quote(text[:1500])}"
    )
    try:
        with urllib.request.urlopen(url, timeout=10):
            pass
        return True, "Message Telegram envoyé."
    except HTTPError as exc:
        logger.warning("Envoi Telegram échoué : %s", exc)
        return False, _telegram_error_detail(exc)
    except (URLError, TimeoutError, OSError) as exc:
        logger.warning("Envoi Telegram échoué : %s", exc)
        return False, f"Réseau indisponible : {exc}"


def validate_telegram_token(db) -> tuple[bool, str, str]:
    """Validation ADMIN : getMe vérifie le token SANS envoyer de message.
    Retourne (ok, message, bot_username)."""
    conf = settings_store.get_raw_group(db, "aggregators").get("telegram", {})
    token = conf.get("bot_token")
    if not (conf.get("enabled") and token):
        return False, "Canal Telegram désactivé ou token absent.", ""
    from urllib.error import HTTPError, URLError

    try:
        with urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/getMe", timeout=10
        ) as response:
            body = json.loads(response.read().decode("utf-8", errors="ignore"))
        if body.get("ok"):
            result = body.get("result", {})
            username = result.get("username", "")
            return True, f"Bot connecté : @{username}", username
        return False, "Réponse inattendue de Telegram.", ""
    except HTTPError as exc:
        return False, _telegram_error_detail(exc), ""
    except (URLError, TimeoutError, OSError) as exc:
        return False, f"Réseau indisponible : {exc}", ""


def send_whatsapp(db, number: str, text: str) -> tuple[bool, str]:
    conf = settings_store.get_raw_group(db, "aggregators").get("whatsapp", {})
    if not (conf.get("enabled") and conf.get("api_key") and number):
        return False, "Canal WhatsApp Business non configuré (voir administrateur)."
    # Agrégateur générique : l'URL précise dépend du fournisseur choisi
    # (Twilio, 360dialog…) ; l'admin la configure dans l'URL de base.
    return False, (
        "WhatsApp Business exige un agrégateur officiel et un gabarit "
        "approuvé : configuration à finaliser par l'administrateur "
        "(roadmap V2, §67)."
    )


# ----------------------------------------------------------- dispatch

def dispatch(
    db, user, subject: str, body: str, event: Optional[str] = None
) -> list[dict[str, Any]]:
    """Envoie une notification sur les canaux ACTIVÉS du destinataire.

    ``event`` : type d'événement (voir EVENT_TYPES). Quand il est
    renseigné et que le destinataire n'a PAS demandé l'e-mail pour cet
    événement, la notification reste in-app (inbox / messagerie) : aucun
    e-mail n'est envoyé. Best effort : jamais d'exception remontée à
    l'appelant métier.
    """
    prefs = normalize_prefs(getattr(user, "notification_prefs", None) or {})
    results: list[dict[str, Any]] = []
    if (
        prefs["email_enabled"]
        and prefs["email"]
        and email_wanted(prefs, event)
    ):
        ok, detail = send_email(db, prefs["email"], subject, body)
        results.append({"channel": "email", "ok": ok, "detail": detail})
    if prefs["telegram_enabled"] and prefs["telegram_username"]:
        # chat_id = identifiant Telegram fourni par l'utilisateur
        ok, detail = send_telegram(db, prefs["telegram_username"], f"{subject}\n\n{body}")
        results.append({"channel": "telegram", "ok": ok, "detail": detail})
    if prefs["whatsapp_enabled"] and prefs["whatsapp_number"]:
        ok, detail = send_whatsapp(db, prefs["whatsapp_number"], f"{subject}\n\n{body}")
        results.append({"channel": "whatsapp", "ok": ok, "detail": detail})
    return results
