"""Paramètres SMTP : le test utilise le formulaire, pas seulement la base.

Le bouton « Tester la connexion » doit fonctionner avant l'enregistrement,
comme le test IMAP. Un mot de passe vide réutilise le secret stocké. En cas
de timeout, le message rappelle le blocage des ports SMTP sur Render.
"""
import base64
import json

import pytest


@pytest.fixture
def clean_smtp(client, admin_headers):
    """Rétablit un service désactivé après un test qui enregistre des secrets."""
    yield
    client.put(
        "/api/admin/settings/smtp",
        json={
            "data": {
                "provider": "smtp",
                "enabled": False,
                "host": "",
            }
        },
        headers=admin_headers,
    )


class _FakeSmtp:
    def __init__(self, host, port, timeout=8):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.tls = False
        self.login_args = None
        _FakeSmtp.last = self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        self.tls = True

    def login(self, username, password):
        self.login_args = (username, password)


class _FakeResponse:
    def __init__(self, status=200, body=b"{}"):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


def _fake_urlopen(monkeypatch, status=200):
    """Remplace urlopen et enregistre les requêtes HTTP sortantes."""
    calls = []

    def fake(request, timeout=8):
        calls.append(
            {
                "url": request.full_url,
                "method": request.get_method(),
                "headers": {
                    key.lower(): value
                    for key, value in request.header_items()
                },
                "data": request.data,
            }
        )
        return _FakeResponse(status)

    monkeypatch.setattr(
        "app.services.notifications.urllib.request.urlopen", fake
    )
    return calls


def _save_smtp(client, headers, **values):
    payload = {
        "host": "smtp.exemple.test",
        "port": 587,
        "username": "compte",
        "password": "secret-stocke",
        "from_email": "no-reply@exemple.test",
        "use_tls": True,
        "enabled": True,
    }
    payload.update(values)
    res = client.put(
        "/api/admin/settings/smtp",
        json={"data": payload},
        headers=headers,
    )
    assert res.status_code == 200, res.text


def test_smtp_test_uses_unsaved_form_values(client, admin_headers, monkeypatch):
    monkeypatch.setattr("app.services.notifications.smtplib.SMTP", _FakeSmtp)
    res = client.post(
        "/api/admin/test-smtp",
        json={
            "data": {
                "host": "smtp.nouveau.test",
                "port": 2525,
                "username": "nouveau",
                "password": "mot-de-passe",
                "from_email": "no-reply@nouveau.test",
                "use_tls": True,
                "enabled": True,
            }
        },
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True
    assert _FakeSmtp.last.host == "smtp.nouveau.test"
    assert _FakeSmtp.last.port == 2525
    assert _FakeSmtp.last.tls is True
    assert _FakeSmtp.last.login_args == ("nouveau", "mot-de-passe")


def test_smtp_test_keeps_stored_password_when_field_is_empty(
    client, admin_headers, monkeypatch, clean_smtp
):
    _save_smtp(client, admin_headers)
    monkeypatch.setattr("app.services.notifications.smtplib.SMTP", _FakeSmtp)
    res = client.post(
        "/api/admin/test-smtp",
        json={
            "data": {
                "host": "smtp.exemple.test",
                "port": 2525,
                "username": "compte",
                "password": "",
                "from_email": "no-reply@exemple.test",
                "use_tls": True,
                "enabled": True,
            }
        },
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True
    assert _FakeSmtp.last.port == 2525
    assert _FakeSmtp.last.login_args == ("compte", "secret-stocke")


def test_smtp_timeout_explains_render_port_block(
    client, admin_headers, monkeypatch
):
    class _TimeoutSmtp:
        def __init__(self, host, port, timeout=8):
            raise TimeoutError("timed out")

    monkeypatch.setattr("app.services.notifications.smtplib.SMTP", _TimeoutSmtp)
    res = client.post(
        "/api/admin/test-smtp",
        json={
            "data": {
                "host": "smtp.exemple.test",
                "port": 587,
                "username": "compte",
                "password": "secret",
                "from_email": "no-reply@exemple.test",
                "use_tls": True,
                "enabled": True,
            }
        },
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is False
    assert "2525" in body["detail"]
    assert "Render" in body["detail"]


@pytest.fixture
def db():
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_brevo_test_uses_api_key(client, admin_headers, monkeypatch):
    calls = _fake_urlopen(monkeypatch)
    res = client.post(
        "/api/admin/test-smtp",
        json={
            "data": {
                "provider": "brevo",
                "api_key": "cle-brevo",
                "from_email": "no-reply@exemple.test",
                "enabled": True,
            }
        },
        headers=admin_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["ok"] is True
    assert calls[0]["url"] == "https://api.brevo.com/v3/account"
    assert calls[0]["method"] == "GET"
    assert calls[0]["headers"]["api-key"] == "cle-brevo"


def test_brevo_send_email_posts_payload(
    client, admin_headers, monkeypatch, clean_smtp, db
):
    _save_smtp(
        client,
        admin_headers,
        provider="brevo",
        api_key="cle-brevo",
        from_email="no-reply@exemple.test",
    )
    calls = _fake_urlopen(monkeypatch)
    from app.services import notifications

    ok, detail = notifications.send_email(
        db,
        "candidat@exemple.test",
        "Sujet",
        "Corps",
        attachments=[("cv.pdf", b"pdf")],
    )
    assert ok is True
    assert detail == "E-mail envoyé via Brevo."
    call = calls[0]
    assert call["url"] == "https://api.brevo.com/v3/smtp/email"
    payload = json.loads(call["data"].decode("utf-8"))
    assert payload["sender"]["email"] == "no-reply@exemple.test"
    assert payload["to"] == [{"email": "candidat@exemple.test"}]
    assert payload["subject"] == "Sujet"
    assert payload["textContent"].startswith("Corps")
    assert "OrientSkill AI" in payload["textContent"]
    assert "OrientSkill AI" in payload["htmlContent"]
    assert "#0a6b4c" in payload["htmlContent"]
    assert payload["attachment"][0]["name"] == "cv.pdf"
    assert payload["attachment"][0]["content"] == base64.b64encode(
        b"pdf"
    ).decode("ascii")


def test_resend_send_email_posts_payload(
    client, admin_headers, monkeypatch, clean_smtp, db
):
    _save_smtp(
        client,
        admin_headers,
        provider="resend",
        api_key="cle-resend",
        from_email="no-reply@exemple.test",
    )
    calls = _fake_urlopen(monkeypatch)
    from app.services import notifications

    ok, detail = notifications.send_email(
        db, "candidat@exemple.test", "Sujet", "Corps"
    )
    assert ok is True
    assert detail == "E-mail envoyé via Resend."
    call = calls[0]
    assert call["url"] == "https://api.resend.com/emails"
    assert call["headers"]["authorization"] == "Bearer cle-resend"
    payload = json.loads(call["data"].decode("utf-8"))
    assert payload["from"] == "OrientSkill AI <no-reply@exemple.test>"
    assert payload["to"] == ["candidat@exemple.test"]
    assert payload["text"].startswith("Corps")
    assert "OrientSkill AI" in payload["text"]
    assert "OrientSkill AI" in payload["html"]
