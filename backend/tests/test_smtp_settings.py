"""Paramètres SMTP : le test utilise le formulaire, pas seulement la base.

Le bouton « Tester la connexion » doit fonctionner avant l'enregistrement,
comme le test IMAP. Un mot de passe vide réutilise le secret stocké. En cas
de timeout, le message rappelle le blocage des ports SMTP sur Render.
"""
import pytest


@pytest.fixture
def clean_smtp(client, admin_headers):
    """Rétablit un service désactivé après un test qui enregistre des secrets."""
    yield
    client.put(
        "/api/admin/settings/smtp",
        json={"data": {"enabled": False, "host": ""}},
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
    monkeypatch.setattr("app.api.admin.smtplib.SMTP", _FakeSmtp)
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
    monkeypatch.setattr("app.api.admin.smtplib.SMTP", _FakeSmtp)
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

    monkeypatch.setattr("app.api.admin.smtplib.SMTP", _TimeoutSmtp)
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
