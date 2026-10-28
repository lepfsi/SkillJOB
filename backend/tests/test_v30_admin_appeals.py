"""Page admin des recours (point 16) : filtres, historique, décisions.

Le recours reste un objet de modération : l'administration peut accepter,
refuser ou demander un complément avec un motif obligatoire. Chaque étape
est horodatée dans l'historique et tracée dans le journal admin.
"""
from datetime import date

import pytest

from app.services import notifications


class FakeSMTP:
    """SMTP capturé : aucune connexion réelle."""

    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        pass

    def login(self, username, password):
        pass

    def send_message(self, msg):
        self.messages.append(msg)


def _candidate(client, email):
    reg = client.post("/api/auth/register", json={
        "email": email, "password": "pass1234", "full_name": "Rania Recours",
    })
    assert reg.status_code == 201, reg.text
    body = reg.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


def _smtp(client, admin_headers, enabled):
    res = client.put("/api/admin/settings/smtp", json={
        "data": {
            "provider": "smtp", "enabled": enabled,
            "host": "smtp.exemple.cm", "port": 587,
            "username": "no@orientskill.cm", "password": "secret",
            "from_email": "no@orientskill.cm", "use_tls": True,
        },
    }, headers=admin_headers)
    assert res.status_code == 200, res.text


@pytest.fixture
def captured_smtp(client, admin_headers, monkeypatch):
    _smtp(client, admin_headers, True)
    FakeSMTP.instances = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    yield FakeSMTP
    _smtp(client, admin_headers, False)


def _emails_to(captured, address):
    found = []
    for instance in captured.instances:
        for message in instance.messages:
            if address in (message.get("To") or ""):
                found.append(message)
    return found


def _ban(client, admin_headers, user_id, reason="Signalement à vérifier"):
    res = client.put(f"/api/admin/users/{user_id}/ban", json={
        "reason": reason,
    }, headers=admin_headers)
    assert res.status_code == 200, res.text


def _appeal(client, email, message):
    res = client.post("/api/auth/appeal", json={
        "email": email, "password": "pass1234", "message": message,
    })
    assert res.status_code == 201, res.text
    return res.json()


def test_appeal_filters_history_complement_and_email(
    client, admin_headers, captured_smtp
):
    email = "candidat.recours.page@orientskill.cm"
    headers, user_id = _candidate(client, email)
    # Le canal e-mail est actif avant la suspension : la décision part sur
    # l'adresse de notification, sans dépendre d'une catégorie.
    prefs = client.put("/api/profile/notifications", json={
        "email_enabled": True,
        "email": "recours.notif@exemple.cm",
    }, headers=headers)
    assert prefs.status_code == 200, prefs.text

    _ban(client, admin_headers, user_id)
    row = _appeal(
        client, email,
        "Je conteste cette suspension : mon compte est légitime et je "
        "n'ai jamais enfreint les règles de la plateforme.",
    )
    assert row["status"] == "pending"

    # Filtres de la page dédiée : statut ouvert, utilisateur, texte, date.
    opened = client.get(
        "/api/admin/appeals?status=open&user=recours.page",
        headers=admin_headers,
    )
    assert opened.status_code == 200, opened.text
    mine = next(a for a in opened.json() if a["user_id"] == user_id)
    assert mine["is_open"] is True
    assert mine["kind"] == "suspension"
    assert mine["user_role"] == "candidate"
    assert mine["age_hours"] >= 0
    assert len(mine["history"]) == 1
    assert mine["history"][0]["action"] == "depot"
    assert "Signalement" in mine["ban_reason"]

    today = date.today().isoformat()
    dated = client.get(
        f"/api/admin/appeals?date_from={today}&date_to={today}",
        headers=admin_headers,
    ).json()
    assert any(a["user_id"] == user_id for a in dated)

    searched = client.get(
        "/api/admin/appeals?q=jamais+enfreint",
        headers=admin_headers,
    ).json()
    assert any(a["user_id"] == user_id for a in searched)

    closed = client.get(
        "/api/admin/appeals?status=accepted&user=recours.page",
        headers=admin_headers,
    ).json()
    assert closed == []
    bad_kind = client.get(
        "/api/admin/appeals?kind=autre", headers=admin_headers
    )
    assert bad_kind.status_code == 422
    bad_status = client.get(
        "/api/admin/appeals?status=inconnu", headers=admin_headers
    )
    assert bad_status.status_code == 422

    # Motif obligatoire, même pour une demande de complément.
    short = client.put(f"/api/admin/appeals/{mine['id']}", json={
        "decision": "complement", "note": "court",
    }, headers=admin_headers)
    assert short.status_code == 422

    complement = client.put(f"/api/admin/appeals/{mine['id']}", json={
        "decision": "complement",
        "note": "Merci de préciser la date et le contenu du message signalé.",
    }, headers=admin_headers)
    assert complement.status_code == 200, complement.text
    body = complement.json()
    assert body["status"] == "complement"
    assert body["is_open"] is True
    assert body["admin_note"].startswith("Merci")
    assert len(body["history"]) == 2
    assert body["history"][-1]["actor"] == "admin"
    assert body["history"][-1]["action"] == "complement"

    # Le candidat ne peut pas se connecter, mais voit le motif attendu.
    login = client.post("/api/auth/login", json={
        "email": email, "password": "pass1234",
    })
    assert login.status_code == 403
    assert "complément" in login.json()["detail"].lower()
    assert "Merci de préciser" in login.json()["detail"]

    # Il répond : le recours repasse en examen, l'historique est conservé.
    updated = _appeal(
        client, email,
        "Voici le complément demandé : le message datait du 12 octobre "
        "et contenait une offre manifestement frauduleuse.",
    )
    assert updated["id"] == mine["id"]
    assert updated["status"] == "pending"
    assert updated["admin_note"] is None

    reopened = client.get(
        "/api/admin/appeals?status=open&user=recours.page",
        headers=admin_headers,
    ).json()
    current = next(a for a in reopened if a["user_id"] == user_id)
    assert len(current["history"]) == 3
    assert current["history"][-1]["action"] == "complement"

    # Décision finale : motif, notification in-app, e-mail et journal.
    decision = client.put(f"/api/admin/appeals/{mine['id']}", json={
        "decision": "accepted",
        "note": "Vérification faite : le signalement était erroné.",
    }, headers=admin_headers)
    assert decision.status_code == 200, decision.text
    decided = decision.json()
    assert decided["status"] == "accepted"
    assert decided["is_open"] is False
    assert decided["reviewed_by_name"]
    assert len(decided["history"]) == 4
    assert decided["history"][-1]["action"] == "accepted"

    # Le compte est intact : la connexion refonctionne.
    login2 = client.post("/api/auth/login", json={
        "email": email, "password": "pass1234",
    })
    assert login2.status_code == 200, login2.text
    inbox = client.get("/api/inbox", headers=headers).json()
    assert any(
        e["kind"] == "appeal" and "accepté" in e["message"] for e in inbox
    )

    mails = _emails_to(captured_smtp, "recours.notif@exemple.cm")
    assert len(mails) == 2, mails
    subjects = [mail["Subject"] for mail in mails]
    assert any("complément" in subject.lower() for subject in subjects)
    assert any("recours est accepté" in subject.lower() for subject in subjects)

    journal = client.get(
        "/api/admin/alert-settings", headers=admin_headers
    ).json()["journal"]
    assert any(
        entry["category"] == "appeal"
        and f"Recours #{mine['id']}" in entry["subject"]
        and entry["sent_count"] == 1
        for entry in journal
    )

    # Un recours clos ne se traite plus.
    twice = client.put(f"/api/admin/appeals/{mine['id']}", json={
        "decision": "rejected",
        "note": "Tentative de double décision.",
    }, headers=admin_headers)
    assert twice.status_code == 400
