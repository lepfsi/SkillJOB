"""Réception des candidatures par e-mail (boîte interne).

Deux entrées complémentaires, réglées par l'administrateur :

- relève IMAP de la boîte interne (aucun service externe requis) ;
- webhook HTTP signé, pour les fournisseurs qui poussent les messages.

Dans les deux cas, le message est routé vers UNE offre : référence
OS-XXXX dans l'objet, mots-clés déclarés sur l'offre, puis titre ou
entreprise. La candidature est transmise au publieur avec les pièces
jointes d'origine. Si l'expéditeur n'a pas de compte, un compte candidat
est créé et ses accès lui sont envoyés. Aucune donnée de profil n'est
inventée : le CV reste une pièce jointe, le profil se complète ensuite.
"""
import base64
import hashlib
import hmac
import html as html_module
import imaplib
import logging
import re
import secrets
import threading
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import config, models, security
from app.services import email_routing, notifications, settings_store, uploads

logger = logging.getLogger("orientskill.inbound")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TEMP_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_ATTACHMENTS = 8
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024


@dataclass
class Attachment:
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


@dataclass
class InboundMessage:
    sender_email: str
    sender_name: str = ""
    subject: str = ""
    body: str = ""
    message_id: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    source: str = "webhook"


def temp_password() -> str:
    return "Ori-" + "".join(secrets.choice(TEMP_ALPHABET) for _ in range(6))


def _safe_filename(value: str) -> str:
    base = Path(value or "piece-jointe").name
    base = re.sub(r"[^A-Za-z0-9._() -]+", "_", base).strip(" .")
    if not base:
        base = "piece-jointe"
    if len(base) > 120:
        stem, suffix = Path(base).stem[:100], Path(base).suffix[:15]
        base = f"{stem}{suffix}"
    return base


def _clean_email(value: str) -> str:
    email = parseaddr(value or "")[1].strip().lower()
    return email if EMAIL_RE.match(email) else ""


def _display_name(value: str) -> str:
    name = parseaddr(value or "")[0].strip()
    return name[:255]


def _strip_html(value: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value or "")
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html_module.unescape(text)
    return re.sub(r"[ \t]+", " ", text).strip()


def _mime_parts(content_type: str) -> tuple[str, str]:
    maintype, _, subtype = (content_type or "application/octet-stream").partition("/")
    return (maintype or "application", subtype or "octet-stream")


def from_webhook(data: dict[str, Any]) -> InboundMessage:
    """Normalise le JSON d'un fournisseur (Mailgun, SendGrid, etc.)."""
    sender_raw = str(data.get("sender") or data.get("from") or "")
    sender = _clean_email(sender_raw)
    sender_name = str(data.get("sender_name") or _display_name(sender_raw))
    text = str(data.get("text") or "")
    if not text and data.get("html"):
        text = _strip_html(str(data.get("html")))
    attachments: list[Attachment] = []
    for item in (data.get("attachments") or [])[:MAX_ATTACHMENTS]:
        if not isinstance(item, dict):
            continue
        raw = item.get("content_base64") or item.get("content") or ""
        try:
            content = base64.b64decode(str(raw), validate=True)
        except Exception:
            continue
        if not content or len(content) > MAX_ATTACHMENT_BYTES:
            continue
        attachments.append(Attachment(
            filename=_safe_filename(str(item.get("filename") or "piece-jointe")),
            content=content,
            content_type=str(item.get("content_type") or "application/octet-stream"),
        ))
    return InboundMessage(
        sender_email=sender,
        sender_name=sender_name,
        subject=str(data.get("subject") or "")[:500],
        body=text[:50_000],
        message_id=str(data.get("message_id") or "")[:255],
        attachments=attachments,
        source="webhook",
    )


def from_raw_email(raw: bytes, source: str = "imap") -> Optional[InboundMessage]:
    """Convertit un message RFC 822 complet en message normalisé."""
    message = message_from_bytes(raw, policy=policy.default)
    if str(message.get("Auto-Submitted") or "no").lower() != "no":
        return None
    if str(message.get("Precedence") or "").lower() in ("bulk", "junk", "list"):
        return None
    sender = _clean_email(str(message.get("From") or ""))
    if not sender:
        return None
    body = ""
    part = message.get_body(preferencelist=("plain", "html"))
    if part is not None:
        try:
            body = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            body = payload.decode("utf-8", errors="replace")
        if part.get_content_type() == "text/html":
            body = _strip_html(body)
    attachments: list[Attachment] = []
    for item in list(message.iter_attachments())[:MAX_ATTACHMENTS]:
        try:
            content = item.get_content()
        except Exception:
            content = item.get_payload(decode=True) or b""
        if isinstance(content, str):
            content = content.encode("utf-8")
        if not content or len(content) > MAX_ATTACHMENT_BYTES:
            continue
        name = item.get_filename() or "piece-jointe"
        attachments.append(Attachment(
            filename=_safe_filename(str(name)),
            content=content,
            content_type=item.get_content_type() or "application/octet-stream",
        ))
    return InboundMessage(
        sender_email=sender,
        sender_name=_display_name(str(message.get("From") or "")),
        subject=str(message.get("Subject") or "")[:500],
        body=(body or "")[:50_000],
        message_id=str(message.get("Message-ID") or "")[:255],
        attachments=attachments,
        source=source,
    )


def _save_attachments(
    message: InboundMessage,
    job_id: Optional[int],
) -> list[dict[str, Any]]:
    if not message.attachments:
        return []
    folder = (
        config.UPLOAD_DIR / "inbound"
        / (str(job_id) if job_id else "non-routees")
        / secrets.token_hex(6)
    )
    folder.mkdir(parents=True, exist_ok=True)
    saved: list[dict[str, Any]] = []
    for index, attachment in enumerate(message.attachments):
        name = _safe_filename(attachment.filename)
        target = folder / name
        if target.exists():
            target = folder / f"{Path(name).stem}-{index}{Path(name).suffix}"
        target.write_bytes(attachment.content)
        saved.append({
            "filename": target.name,
            "content_type": attachment.content_type,
            "path": uploads.store(target),
            "size": len(attachment.content),
        })
    return saved


def _find_or_create_user(
    db: Session, message: InboundMessage
) -> tuple[models.User, bool, str]:
    user = (
        db.query(models.User)
        .filter(models.User.email == message.sender_email)
        .first()
    )
    if user is not None:
        return user, False, ""
    name = (message.sender_name or "").strip()
    if len(name) < 2:
        local = message.sender_email.split("@")[0]
        name = local.replace(".", " ").replace("_", " ").strip().title()
    if len(name) < 2:
        name = "Candidat"
    password = temp_password()
    user = models.User(
        email=message.sender_email,
        full_name=name[:255],
        password_hash=security.hash_password(password),
        role="candidate",
    )
    db.add(user)
    db.flush()
    return user, True, password


def _application_for(
    db: Session,
    user: models.User,
    job: models.Job,
    message: InboundMessage,
    reference: str,
) -> tuple[models.Application, bool]:
    application = (
        db.query(models.Application)
        .filter(
            models.Application.user_id == user.id,
            models.Application.job_id == job.id,
        )
        .order_by(models.Application.created_at.desc())
        .first()
    )
    now = models.utcnow()
    event = {
        "at": now.isoformat(timespec="seconds"),
        "event": (
            f"Candidature reçue par e-mail (référence {reference}) ; "
            "pièces jointes transmises à l'entreprise"
        ),
    }
    cover_note = (message.body or "").strip()[:5000]
    if application is None:
        application = models.Application(
            user_id=user.id,
            job_id=job.id,
            status="envoyee",
            apply_channel="email",
            submitted_at=now,
            cover_note=cover_note,
            timeline=[event],
        )
        db.add(application)
        db.flush()
        return application, True
    if not application.submitted_at:
        application.status = "envoyee"
        application.submitted_at = now
    if not application.apply_channel:
        application.apply_channel = "email"
    if cover_note and not application.cover_note:
        application.cover_note = cover_note
    application.timeline = list(application.timeline or []) + [event]
    db.add(application)
    db.flush()
    return application, False


def _forward_destination(
    db: Session, job: Optional[models.Job], conf: dict[str, Any]
) -> str:
    if job is None:
        return ""
    candidates = [job.apply_email or ""]
    if job.company_id:
        company = db.get(models.Company, job.company_id)
        if company is not None:
            owner = db.get(models.User, company.owner_user_id)
            if owner is not None:
                candidates.append(owner.email or "")
    candidates.append(str(conf.get("fallback_email") or ""))
    internal = str(conf.get("address") or "").strip().lower()
    for value in candidates:
        email = _clean_email(value)
        if email and email != internal:
            return email
    return ""


def _forward_body(
    message: InboundMessage,
    job: models.Job,
    user: models.User,
    reference: str,
) -> str:
    return (
        "Bonjour,\n\n"
        "Une candidature a été reçue sur la boîte interne OrientSkill AI.\n\n"
        f"Offre : {job.title} ({reference})\n"
        f"Entreprise : {job.company}\n"
        f"Candidat : {user.full_name}\n"
        f"E-mail : {message.sender_email}\n"
        f"Objet du message : {message.subject or 'Sans objet'}\n\n"
        "Message du candidat :\n"
        f"{message.body[:4000] or 'Aucun message texte.'}\n\n"
        "Les pièces jointes d'origine (CV, lettre) sont jointes à cet e-mail. "
        "Répondez directement à ce message pour joindre le candidat.\n\n"
        "OrientSkill AI\n"
    )


def _access_body(
    user: models.User,
    password: str,
    job: Optional[models.Job],
    reference: str,
) -> str:
    base = config.PUBLIC_BASE_URL.rstrip("/")
    subject_line = (
        f"Votre candidature pour « {job.title} » chez {job.company} a bien "
        "été reçue."
        if job else
        "Votre message a bien été reçu par OrientSkill AI."
    )
    reference_line = (
        f"Référence de l'offre : {reference}\n"
        if job else
        "Nous n'avons pas pu identifier l'offre : précisez la référence "
        "OS-XXXX dans l'objet de votre prochain message.\n"
    )
    return (
        f"Bonjour {user.full_name},\n\n"
        f"{subject_line}\n"
        f"{reference_line}\n"
        "Un compte OrientSkill AI a été créé pour vous :\n"
        f"E-mail : {user.email}\n"
        f"Mot de passe provisoire : {password}\n\n"
        f"Se connecter : {base}/login\n"
        f"Compléter votre profil : {base}/profil\n\n"
        "Votre profil est encore vide : ajoutez vos compétences et "
        "expériences pour améliorer vos chances. Vous pouvez changer votre "
        "mot de passe dans les paramètres du compte.\n\n"
        "OrientSkill AI\n"
    )


def process_inbound(db: Session, message: InboundMessage) -> dict[str, Any]:
    """Traite UN message : routage, compte, candidature, transmission.

    Le message est idempotent grâce à son ``Message-ID`` : un webhook qui
    réessaie ou une relève IMAP qui repasse ne crée pas de doublon.
    """
    if not message.sender_email:
        raise ValueError("Expéditeur sans adresse e-mail valide")
    if not message.message_id:
        digest = hashlib.sha256(
            f"{message.sender_email}|{message.subject}|{message.body}".encode("utf-8")
        ).hexdigest()[:24]
        message_id = f"<{digest}@orientskill.local>"
    else:
        message_id = message.message_id
    existing = (
        db.query(models.InboundEmail)
        .filter(models.InboundEmail.message_id == message_id)
        .first()
    )
    if existing is not None:
        return {
            "ok": True,
            "duplicate": True,
            "status": existing.status,
            "inbound_id": existing.id,
            "application_id": existing.application_id,
            "job_id": existing.job_id,
        }

    conf = settings_store.get_raw_group(db, "inbound")
    job, routing = email_routing.match_job(db, message.subject, message.body)
    reference = email_routing.reference_for(job) if job else ""
    user, created, password = _find_or_create_user(db, message)
    application = None
    if job is not None:
        application, _new = _application_for(db, user, job, message, reference)
    attachments = _save_attachments(message, job.id if job else None)

    row = models.InboundEmail(
        message_id=message_id,
        source=message.source,
        sender_email=message.sender_email,
        sender_name=message.sender_name,
        subject=message.subject,
        body_text=message.body,
        job_id=job.id if job else None,
        user_id=user.id,
        application_id=application.id if application else None,
        attachments=attachments,
        routing=routing,
        status="recue",
        detail="",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    # 1. Transmission à l'entreprise, avec les pièces jointes d'origine.
    destination = _forward_destination(db, job, conf)
    forward_ok = False
    forward_detail = ""
    if job is not None and destination:
        row.forwarded_to = destination
        mail_attachments = []
        for attachment in message.attachments:
            maintype, subtype = _mime_parts(attachment.content_type)
            mail_attachments.append({
                "filename": _safe_filename(attachment.filename),
                "content": attachment.content,
                "maintype": maintype,
                "subtype": subtype,
            })
        forward_ok, forward_detail = notifications.send_email(
            db,
            destination,
            f"Candidature - {job.title} - {user.full_name}",
            _forward_body(message, job, user, reference),
            attachments=mail_attachments,
            reply_to=message.sender_email,
        )
    elif job is not None:
        forward_detail = (
            "Aucune adresse de transmission : renseignez l'e-mail de "
            "candidature de l'offre ou l'adresse de secours."
        )
    else:
        forward_detail = "Offre non identifiée : candidature conservée pour revue."

    # 2. Accès au compte (nouveau compte) ou confirmation (compte existant).
    access_ok = False
    if created:
        access_ok, access_detail = notifications.send_email(
            db,
            user.email,
            "Vos accès OrientSkill AI",
            _access_body(user, password, job, reference),
        )
        if not access_ok:
            forward_detail = (forward_detail + " " + access_detail).strip()
    elif job is not None:
        notifications.send_email(
            db,
            user.email,
            f"Candidature reçue : {job.title}",
            (
                f"Bonjour {user.full_name},\n\n"
                f"Votre candidature pour « {job.title} » chez {job.company} "
                f"a bien été reçue et transmise à l'entreprise.\n"
                f"Référence : {reference}\n\n"
                "Suivez vos candidatures depuis votre espace OrientSkill AI.\n\n"
                "OrientSkill AI\n"
            ),
        )

    if job is None:
        row.status = "non_routee"
    elif forward_ok:
        row.status = "transmise"
    else:
        row.status = "recue"
    row.access_email_sent = access_ok
    row.forward_email_sent = forward_ok
    row.account_created = created
    row.detail = forward_detail[:2000]
    row.processed_at = models.utcnow()
    db.commit()
    db.refresh(row)
    return {
        "ok": True,
        "duplicate": False,
        "status": row.status,
        "inbound_id": row.id,
        "job_id": row.job_id,
        "application_id": row.application_id,
        "user_id": row.user_id,
        "account_created": created,
        "access_email_sent": access_ok,
        "forward_email_sent": forward_ok,
        "routing": routing,
        "detail": row.detail,
    }


def verify_webhook_secret(db: Session, provided: str) -> bool:
    conf = settings_store.get_raw_group(db, "inbound")
    expected = str(conf.get("webhook_secret") or "")
    if not expected:
        return False
    return hmac.compare_digest(expected, provided or "")


def test_imap(
    db: Session,
    overrides: Optional[dict[str, Any]] = None,
) -> tuple[bool, str]:
    """Teste la connexion IMAP sans modifier la boîte (pas de SELECT/STORE).

    ``overrides`` permet de tester les valeurs du formulaire courant avant
    enregistrement. Un mot de passe vide conserve celui déjà stocké.
    """
    conf = settings_store.get_raw_group(db, "inbound")
    if overrides:
        for key, value in overrides.items():
            if key in ("imap_password", "webhook_secret") and not value:
                continue
            conf[key] = value
    host = str(conf.get("imap_host") or "").strip()
    if not host:
        return False, "Hôte IMAP manquant."
    try:
        port = int(conf.get("imap_port") or 993)
    except (TypeError, ValueError):
        return False, "Port IMAP invalide."
    if not 1 <= port <= 65535:
        return False, "Port IMAP invalide."
    client: Optional[imaplib.IMAP4] = None
    try:
        if conf.get("imap_use_ssl", True):
            client = imaplib.IMAP4_SSL(host, port, timeout=12)
        else:
            client = imaplib.IMAP4(host, port, timeout=12)
            try:
                client.starttls()
            except Exception:
                pass
        client.login(
            str(conf.get("imap_username") or ""),
            str(conf.get("imap_password") or ""),
        )
        client.select(str(conf.get("imap_mailbox") or "INBOX"), readonly=True)
        return True, "Connexion IMAP réussie, boîte accessible en lecture."
    except Exception as exc:
        return False, f"Échec IMAP : {exc}"
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass


def resend_access(db: Session, row: models.InboundEmail) -> tuple[bool, str]:
    """Renvoie des accès à un candidat créé par e-mail, avec un nouveau mot
    de passe provisoire. Le mot de passe n'est remplacé qu'après un envoi
    réussi, pour ne jamais laisser le compte sans accès connu."""
    user = db.get(models.User, row.user_id) if row.user_id else None
    if user is None:
        return False, "Aucun compte associé à ce message."
    smtp = settings_store.get_raw_group(db, "smtp")
    if not (smtp.get("enabled") and smtp.get("host")):
        return False, "SMTP non configuré : impossible d'envoyer les accès."
    job = db.get(models.Job, row.job_id) if row.job_id else None
    reference = email_routing.reference_for(job) if job else ""
    password = temp_password()
    ok, detail = notifications.send_email(
        db,
        user.email,
        "Vos accès OrientSkill AI",
        _access_body(user, password, job, reference),
    )
    if not ok:
        return False, detail
    user.password_hash = security.hash_password(password)
    row.access_email_sent = True
    row.detail = (row.detail + " Accès renvoyés par l'administrateur.").strip()[:2000]
    db.commit()
    return True, "Accès renvoyés."


def fetch_imap_once(db: Session) -> list[dict[str, Any]]:
    """Relève les messages non lus de la boîte IMAP configurée."""
    conf = settings_store.get_raw_group(db, "inbound")
    if not (conf.get("enabled") and conf.get("imap_host")):
        return []
    host = str(conf.get("imap_host"))
    port = int(conf.get("imap_port") or 993)
    use_ssl = bool(conf.get("imap_use_ssl", True))
    mailbox = str(conf.get("imap_mailbox") or "INBOX")
    results: list[dict[str, Any]] = []
    client: Optional[imaplib.IMAP4] = None
    try:
        if use_ssl:
            client = imaplib.IMAP4_SSL(host, port, timeout=20)
        else:
            client = imaplib.IMAP4(host, port, timeout=20)
            try:
                client.starttls()
            except Exception:
                pass
        client.login(
            str(conf.get("imap_username") or ""),
            str(conf.get("imap_password") or ""),
        )
        client.select(mailbox)
        _typ, data = client.search(None, "UNSEEN")
        numbers = (data[0] or b"").split() if data else []
        for number in numbers[:50]:
            _typ, payload = client.fetch(number, "(RFC822)")
            raw = b""
            for part in payload or []:
                if isinstance(part, tuple) and len(part) >= 2:
                    raw = part[1]
                    break
            if not raw:
                continue
            message = from_raw_email(raw, source="imap")
            if message is not None:
                try:
                    results.append(process_inbound(db, message))
                except Exception as exc:
                    logger.warning("Candidature IMAP non traitée : %s", exc)
                    db.rollback()
            client.store(number, "+FLAGS", "\\Seen")
    except Exception as exc:
        logger.warning("Relève IMAP impossible : %s", exc)
        db.rollback()
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:
                pass
    return results


class InboundEmailService:
    """Relève IMAP en arrière-plan, sans bloquer les requêtes HTTP."""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def _configured(self) -> tuple[bool, int]:
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            conf = settings_store.get_raw_group(db, "inbound")
            enabled = bool(
                conf.get("enabled")
                and conf.get("protocol") == "imap"
                and conf.get("imap_host")
            )
            poll = max(30, int(conf.get("poll_seconds") or 120))
            return enabled, poll
        finally:
            db.close()

    def start_if_configured(self) -> None:
        enabled, _poll = self._configured()
        if not enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="orientskill-inbound", daemon=True
        )
        self._thread.start()

    def _loop(self) -> None:
        from app.database import SessionLocal
        while not self._stop.is_set():
            db = SessionLocal()
            try:
                fetch_imap_once(db)
            except Exception as exc:  # pragma: no cover - défense
                logger.warning("Boucle IMAP interrompue : %s", exc)
            finally:
                db.close()
            _enabled, poll = self._configured()
            self._stop.wait(poll)

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None

    def restart_if_configured(self) -> None:
        self.stop()
        self.start_if_configured()


inbound_service = InboundEmailService()
