"""Réception des candidatures par e-mail et visuel public (V29).

Le webhook normalisé est signé, routé par référence puis par mots-clés,
transmet les pièces jointes à l'entreprise et crée le compte candidat avec
des accès utilisables. Le visuel LinkedIn reste un SVG autonome généré
depuis la seule fiche de l'offre.
"""
import base64
import re
from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from app.services import calendar as calendar_service
from app.services import email_routing, inbound_email, poster


def _set_inbound(client, admin_headers, **values):
    payload = {
        "enabled": False,
        "address": "candidatures@orientskill.test",
        "protocol": "webhook",
        "webhook_secret": "secret-test-v29",
        "fallback_email": "",
    }
    payload.update(values)
    res = client.put(
        "/api/admin/settings/inbound",
        json={"data": payload},
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text


def _create_job(client, admin_headers, **extra):
    suffix = uuid4().hex[:8]
    payload = {
        "title": f"Chargé de clientèle {suffix}",
        "company": f"Entreprise Inbound {suffix}",
        "location": "Douala",
        "sector": "Services",
        "contract_type": "CDI",
        "description": "Accueillir et conseiller les clients.",
        "requirements": "Sens du service.",
        "source_name": "Test V29",
        "source_url": f"https://exemple.cm/offre/{suffix}",
        "apply_channel": "external",
        "apply_email": f"rh-{suffix}@exemple.cm",
        "apply_keywords": [f"motcle{suffix}"],
        "required_skills": [{"name": "Relation client", "importance": "core"}],
    }
    payload.update(extra)
    res = client.post("/api/admin/jobs", json=payload, headers=admin_headers)
    assert res.status_code == 201, res.text
    return res.json()


class _FakeSend:
    def __init__(self):
        self.calls = []

    def __call__(self, db, to_email, subject, body, attachments=None,
                 reply_to="", **kwargs):
        self.calls.append({
            "to": to_email,
            "subject": subject,
            "body": body,
            "attachments": attachments or [],
            "reply_to": reply_to,
        })
        return True, "E-mail simulé."

    def password_for(self, email):
        call = next(
            c for c in reversed(self.calls)
            if c["to"] == email and c["subject"] == "Vos accès OrientSkill AI"
        )
        match = re.search(r"Mot de passe provisoire : (\S+)", call["body"])
        assert match, call["body"]
        return match.group(1)


def _login(client, email, password):
    return client.post("/api/auth/login", json={
        "email": email, "password": password,
    })


def test_poster_requires_configured_address(client, admin_headers):
    job = _create_job(client, admin_headers)
    _set_inbound(client, admin_headers, address="")
    res = client.get(f"/api/public/jobs/{job['id']}/poster.svg")
    assert res.status_code == 503
    assert "adresse" in res.json()["detail"].lower()


def test_poster_is_escaped_and_uses_the_offer(client, admin_headers):
    job = _create_job(client, admin_headers)
    _set_inbound(client, admin_headers)
    res = client.get(f"/api/public/jobs/{job['id']}/poster.svg")
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("image/svg+xml")
    svg = res.text
    assert "width=\"1200\"" in svg and "height=\"1500\"" in svg
    assert "candidatures@orientskill.test" in svg
    assert f"OS-{job['id']:04d}" in svg
    assert "<script" not in svg.lower()

    card = client.get(f"/api/public/jobs/{job['id']}").json()
    assert card["email_apply_address"] == "candidatures@orientskill.test"
    assert card["email_reference"] == f"OS-{job['id']:04d}"
    assert card["poster_url"] == f"/api/public/jobs/{job['id']}/poster.svg"

    # Le texte de l'offre est échappé, jamais interprété comme balisage.
    fake = SimpleNamespace(
        id=9999,
        title="<script>alert(1)</script>",
        company="A & B",
        location="Douala",
        contract_type="CDI",
        sector="<b>Test</b>",
    )
    escaped = poster.build_svg(fake, "rh@exemple.cm", "OS-9999", "https://x.cm")
    assert "<script" not in escaped.lower()
    assert "&lt;script&gt;" in escaped


def test_webhook_rejects_wrong_secret(client, admin_headers):
    job = _create_job(client, admin_headers)
    _set_inbound(client, admin_headers)
    res = client.post(
        "/api/public/inbound-email",
        json={
            "sender": "Intrus <intrus@exemple.cm>",
            "subject": f"CANDIDATURE OS-{job['id']:04d}",
            "message_id": f"<intrus-{uuid4().hex}@exemple.cm>",
        },
        headers={"X-OrientSkill-Secret": "mauvais-secret"},
    )
    assert res.status_code == 401


def test_inbound_webhook_creates_account_and_forwards(
    client, admin_headers, monkeypatch
):
    job = _create_job(client, admin_headers)
    _set_inbound(client, admin_headers)
    fake = _FakeSend()
    monkeypatch.setattr(inbound_email.notifications, "send_email", fake)

    suffix = uuid4().hex[:8]
    candidate_email = f"candidat-{suffix}@exemple.cm"
    attachment = base64.b64encode(b"CV de test V29").decode()
    payload = {
        "sender": f"Candidat Test <{candidate_email}>",
        "sender_name": "Candidat Test",
        "subject": f"CANDIDATURE OS-{job['id']:04d} - {job['title']}",
        "text": "Bonjour, je souhaite postuler à cette offre.",
        "message_id": f"<{suffix}@exemple.cm>",
        "attachments": [{
            "filename": "cv.txt",
            "content_type": "text/plain",
            "content_base64": attachment,
        }],
    }
    res = client.post(
        "/api/public/inbound-email",
        json=payload,
        headers={"X-OrientSkill-Secret": "secret-test-v29"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True and body["duplicate"] is False
    assert body["job_id"] == job["id"]
    assert body["routing"] == "reference"
    assert body["account_created"] is True
    assert body["access_email_sent"] is True
    assert body["forward_email_sent"] is True

    # Un mail de transmission à l'entreprise, avec la pièce jointe d'origine.
    forward = next(
        call for call in fake.calls
        if call["to"] == job["apply_email"]
    )
    assert forward["reply_to"] == candidate_email
    assert forward["attachments"][0]["filename"] == "cv.txt"
    assert forward["attachments"][0]["content"] == b"CV de test V29"

    # Le compte candidat est réellement utilisable avec le mot de passe reçu.
    password = fake.password_for(candidate_email)
    login = _login(client, candidate_email, password)
    assert login.status_code == 200, login.text

    # La candidature est tracée avec le canal e-mail.
    apps = client.get("/api/admin/applications?channel=email",
                      headers=admin_headers).json()
    application = next(a for a in apps if a["id"] == body["application_id"])
    assert application["apply_channel"] == "email"
    assert application["job_id"] == job["id"]

    # Rejouer le même Message-ID ne crée ni compte, ni candidature, ni envoi.
    calls_before = len(fake.calls)
    duplicate = client.post(
        "/api/public/inbound-email",
        json=payload,
        headers={"X-OrientSkill-Secret": "secret-test-v29"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["duplicate"] is True
    assert len(fake.calls) == calls_before

    # Le journal admin expose le routage, la transmission et les pièces.
    journal = client.get("/api/admin/inbound-emails", headers=admin_headers).json()
    row = next(r for r in journal if r["id"] == body["inbound_id"])
    assert row["status"] == "transmise"
    assert row["account_created"] is True
    assert row["forwarded_to"] == job["apply_email"]
    assert row["attachments_count"] == 1
    assert row["attachment_names"] == ["cv.txt"]

    # Routage par mots-clés, sans référence dans l'objet.
    keyword_email = f"motcle-{suffix}@exemple.cm"
    keyword_payload = {
        "sender": f"Candidat Mots-clés <{keyword_email}>",
        "sender_name": "Candidat Mots-clés",
        "subject": f"Candidature {job['apply_keywords'][0]}",
        "text": "Bonjour, je découvre votre offre.",
        "message_id": f"<motcle-{suffix}@exemple.cm>",
    }
    keyword = client.post(
        "/api/public/inbound-email",
        json=keyword_payload,
        headers={"X-OrientSkill-Secret": "secret-test-v29"},
    )
    assert keyword.status_code == 200, keyword.text
    assert keyword.json()["job_id"] == job["id"]
    assert keyword.json()["routing"] == "keywords"

    # Message non routé : conservé pour revue, jamais envoyé au hasard.
    orphan_payload = {
        "sender": f"Inconnu <inconnu-{suffix}@exemple.cm>",
        "sender_name": "Inconnu",
        "subject": "Demande d'information",
        "text": "Zzzt qqqq wwww.",
        "message_id": f"<inconnu-{suffix}@exemple.cm>",
    }
    orphan = client.post(
        "/api/public/inbound-email",
        json=orphan_payload,
        headers={"X-OrientSkill-Secret": "secret-test-v29"},
    )
    assert orphan.status_code == 200, orphan.text
    assert orphan.json()["job_id"] is None
    assert orphan.json()["status"] == "non_routee"


def test_resend_access_rotates_password(client, admin_headers, monkeypatch):
    job = _create_job(client, admin_headers)
    _set_inbound(client, admin_headers)
    fake = _FakeSend()
    monkeypatch.setattr(inbound_email.notifications, "send_email", fake)

    # Le renvoi d'accès exige un SMTP configuré ; l'envoi reste simulé.
    client.put("/api/admin/settings/smtp", json={"data": {
        "enabled": True,
        "host": "smtp.exemple.test",
        "port": 587,
        "from_email": "candidatures@orientskill.test",
        "use_tls": False,
    }}, headers=admin_headers)

    suffix = uuid4().hex[:8]
    email = f"acces-{suffix}@exemple.cm"
    created = client.post(
        "/api/public/inbound-email",
        json={
            "sender": f"Candidat Accès <{email}>",
            "sender_name": "Candidat Accès",
            "subject": f"CANDIDATURE OS-{job['id']:04d}",
            "text": "Bonjour.",
            "message_id": f"<acces-{suffix}@exemple.cm>",
        },
        headers={"X-OrientSkill-Secret": "secret-test-v29"},
    )
    assert created.status_code == 200, created.text
    old_password = fake.password_for(email)
    assert _login(client, email, old_password).status_code == 200

    resend = client.post(
        f"/api/admin/inbound-emails/{created.json()['inbound_id']}/resend-access",
        headers=admin_headers,
    )
    assert resend.status_code == 200, resend.text
    assert resend.json()["ok"] is True
    new_password = fake.password_for(email)
    assert new_password != old_password
    assert _login(client, email, old_password).status_code == 401
    assert _login(client, email, new_password).status_code == 200


class _FakeImap:
    instances = []

    def __init__(self, host, port, timeout=12):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.login_args = None
        self.selected = None
        _FakeImap.instances.append(self)

    def login(self, username, password):
        self.login_args = (username, password)
        return "OK", [b""]

    def select(self, mailbox, readonly=False):
        self.selected = (mailbox, readonly)
        return "OK", [b""]

    def logout(self):
        return "BYE", [b""]


def test_imap_test_uses_form_values_before_save(
    client, admin_headers, monkeypatch
):
    monkeypatch.setattr(inbound_email.imaplib, "IMAP4_SSL", _FakeImap)
    res = client.post(
        "/api/admin/test-imap",
        json={"data": {
            "imap_host": "ssl0.example.test",
            "imap_port": 993,
            "imap_username": "contact@example.test",
            "imap_password": "mot-de-passe-formulaire",
            "imap_use_ssl": True,
            "imap_mailbox": "INBOX",
        }},
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True
    client_imap = _FakeImap.instances[-1]
    assert client_imap.host == "ssl0.example.test"
    assert client_imap.port == 993
    assert client_imap.login_args == (
        "contact@example.test", "mot-de-passe-formulaire"
    )
    assert client_imap.selected == ("INBOX", True)


def test_imap_test_reuses_stored_password(
    client, admin_headers, monkeypatch
):
    _set_inbound(
        client,
        admin_headers,
        imap_host="stored.example.test",
        imap_port=993,
        imap_username="contact@example.test",
        imap_password="mot-de-passe-stocke",
        imap_use_ssl=True,
        imap_mailbox="INBOX",
    )
    monkeypatch.setattr(inbound_email.imaplib, "IMAP4_SSL", _FakeImap)
    res = client.post(
        "/api/admin/test-imap",
        json={"data": {
            "imap_host": "form.example.test",
            "imap_port": 993,
            "imap_username": "contact@example.test",
            "imap_password": "",
            "imap_use_ssl": True,
            "imap_mailbox": "INBOX",
        }},
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True
    client_imap = _FakeImap.instances[-1]
    assert client_imap.host == "form.example.test"
    assert client_imap.login_args[1] == "mot-de-passe-stocke"


def test_imap_test_reports_missing_host(client, admin_headers):
    res = client.post(
        "/api/admin/test-imap",
        json={"data": {"imap_host": ""}},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json() == {"ok": False, "detail": "Hôte IMAP manquant."}


def test_imap_test_reports_invalid_port(client, admin_headers):
    res = client.post(
        "/api/admin/test-imap",
        json={"data": {
            "imap_host": "ssl0.example.test",
            "imap_port": "port-invalide",
        }},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json() == {"ok": False, "detail": "Port IMAP invalide."}


def test_calendar_ics_is_utc_and_follows_status():
    invite = SimpleNamespace(
        token="jeton-test",
        job_id=12,
        slot_at=datetime(2026, 11, 10, 10, 0),
        duration_min=45,
        status="pending",
        message="Merci de confirmer.",
        candidate_note="",
    )
    job = SimpleNamespace(
        title="Développeur web", company="Entreprise Test",
        location="Douala", id=12,
    )
    candidate = SimpleNamespace(full_name="Awa Test", email="awa@test.cm")
    recruiter = SimpleNamespace(full_name="Paul Recruteur", email="paul@test.cm")

    pending = calendar_service.build(invite, job, candidate, recruiter).decode("utf-8")
    assert "DTSTART:20261110T090000Z" in pending
    assert "DTEND:20261110T094500Z" in pending
    assert "STATUS:TENTATIVE" in pending
    assert "METHOD:REQUEST" in pending
    assert "OS-" not in pending

    invite.status = "accepted"
    accepted = calendar_service.build(invite, job, candidate, recruiter).decode("utf-8")
    assert "STATUS:CONFIRMED" in accepted
    assert "SEQUENCE:1" in accepted

    invite.status = "declined"
    cancelled = calendar_service.build(invite, job, candidate, recruiter).decode("utf-8")
    assert "STATUS:CANCELLED" in cancelled
    assert "METHOD:CANCEL" in cancelled
    assert calendar_service.filename(invite, job).endswith("-20261110.ics")


def test_reference_and_normalization():
    assert email_routing.reference_for(SimpleNamespace(id=7)) == "OS-0007"
    assert email_routing.reference_for(SimpleNamespace(id=None)) == ""
    assert email_routing.normalize("Développeur à Douala") == "developpeur a douala"
