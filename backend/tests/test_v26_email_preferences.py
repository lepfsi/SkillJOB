"""Préférences e-mail par rôle (points 18 et 19).

Le candidat choisit ses catégories et la fréquence des alertes emploi ;
le recruteur et l'administrateur ne voient que leurs propres événements.
Les e-mails critiques restent envoyés, et le désabonnement emploi est
signé et utilisable sans connexion.
"""
from datetime import datetime, timedelta

import pytest

from app import models
from app.database import SessionLocal
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


def _candidate(client, email, name="Nadia Prefs"):
    reg = client.post("/api/auth/register", json={
        "email": email, "password": "pass1234", "full_name": name,
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def _recruiter(client, email, company="Prefs RH"):
    reg = client.post("/api/auth/register/recruiter", json={
        "email": email, "password": "pass1234",
        "recruiter_type": "company",
        "company_name": company,
        "company_sector": "Informatique / IT",
        "company_description": "Test préférences e-mail.",
        "company_location": "Douala",
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['token']}"}


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


def _enable_email(client, headers, email, events, frequency=None):
    body = {
        "email_enabled": True,
        "email": email,
        "events": events,
    }
    if frequency:
        body["email_frequency"] = frequency
    res = client.put("/api/profile/notifications", json=body, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _profile(client, headers):
    res = client.put("/api/profile", json={
        "title": "Technicienne support",
        "summary": "Profil de test préférences e-mail.",
        "skills": [
            {"skill": "Support informatique", "proficiency": "avance"},
            {"skill": "Gestion des incidents", "proficiency": "intermediaire"},
        ],
    }, headers=headers)
    assert res.status_code == 200, res.text


def _job(client, recruiter_headers, title="Technicien support préfs",
         deadline=None):
    payload = {
        "title": title,
        "company": "Prefs RH",
        "location": "Douala",
        "sector": "Informatique / IT",
        "contract_type": "CDI",
        "description": "Support informatique et gestion des incidents.",
        "requirements": "Rigueur et sens du service.",
        "required_skills": [
            {"name": "Support informatique", "importance": "core"},
            {"name": "Gestion des incidents", "importance": "preferred"},
        ],
    }
    if deadline:
        payload["deadline"] = deadline.isoformat()
    res = client.post("/api/recruiter/jobs", json=payload, headers=recruiter_headers)
    assert res.status_code == 201, res.text
    return res.json()


def _cv(client, headers, job_id):
    res = client.post(
        f"/api/jobs/{job_id}/cv", json={"template": "classique"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()


def _emails_to(captured, address):
    found = []
    for instance in captured.instances:
        for message in instance.messages:
            if address in (message.get("To") or ""):
                found.append(message)
    return found


def test_candidate_catalog_and_frequency(client):
    headers = _candidate(client, "candidat.prefs.catalogue@orientskill.cm")
    prefs = client.get("/api/profile/notifications", headers=headers).json()
    assert prefs["role"] == "candidate"
    assert prefs["email_frequency"] == "daily"
    keys = {item["key"] for item in prefs["event_catalog"]}
    assert keys == {
        "new_match", "expiring", "message", "application", "interview",
        "verification_decision", "agent",
    }
    assert "new_application" not in keys

    updated = _enable_email(
        client, headers, "candidat.prefs@exemple.cm",
        {"new_match": True}, frequency="immediate",
    )
    assert updated["email_frequency"] == "immediate"
    assert updated["events"]["new_match"] is True
    assert updated["events"]["application"] is False

    bad = client.put("/api/profile/notifications", json={
        "email_frequency": "hebdomadaire",
    }, headers=headers)
    assert bad.status_code == 422

    # Une clé d'un autre rôle est ignorée, jamais ajoutée au candidat.
    other = client.put("/api/profile/notifications", json={
        "events": {"new_application": True},
    }, headers=headers)
    assert other.status_code == 200, other.text
    assert "new_application" not in other.json()["events"]


def test_recruiter_catalog_is_role_specific(client):
    headers = _recruiter(
        client, "recruteur.prefs.catalogue@orientskill.cm"
    )
    prefs = client.get("/api/profile/notifications", headers=headers).json()
    assert prefs["role"] == "recruiter"
    keys = {item["key"] for item in prefs["event_catalog"]}
    assert keys == {
        "new_application", "candidate_message", "interview_response",
        "job_published", "job_expiring", "company_verification",
    }
    assert "new_match" not in keys

    updated = _enable_email(
        client, headers, "rh.prefs@exemple.cm",
        {"new_application": True, "new_match": True},
    )
    assert updated["events"]["new_application"] is True
    assert "new_match" not in updated["events"]


def test_admin_catalog_is_role_specific(client, admin_headers):
    prefs = client.get(
        "/api/profile/notifications", headers=admin_headers
    ).json()
    assert prefs["role"] == "admin"
    keys = {item["key"] for item in prefs["event_catalog"]}
    assert keys == {
        "verification_request", "appeal", "report",
        "ingestion_failure", "critical_alert",
    }
    assert "new_match" not in keys

    updated = client.put("/api/profile/notifications", json={
        "events": {"report": True},
    }, headers=admin_headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["events"]["report"] is True
    # Nettoyage pour les autres tests d'alertes admin.
    client.put("/api/profile/notifications", json={
        "events": {"report": False},
    }, headers=admin_headers)


def test_recruiter_new_application_email_only_when_opted_in(
    client, captured_smtp
):
    recruiter = _recruiter(
        client, "recruteur.newapp@orientskill.cm", company="NewApp SARL"
    )
    candidate = _candidate(
        client, "candidat.newapp@orientskill.cm", name="Paul NewApp"
    )
    _profile(client, candidate)
    job1 = _job(client, recruiter, title="Support newapp 1")
    cv1 = _cv(client, candidate, job1["id"])

    # Sans opt-in : le recruteur reçoit la messagerie interne, pas d'e-mail.
    first = client.post(
        f"/api/applications/jobs/{job1['id']}/submit",
        json={"cv_document_id": cv1["id"]},
        headers=candidate,
    )
    assert first.status_code == 200, first.text
    assert _emails_to(captured_smtp, "recruteur.newapp@orientskill.cm") == []

    # Avec opt-in : l'e-mail part à l'adresse de notification.
    _enable_email(
        client, recruiter, "rh.newapp@exemple.cm",
        {"new_application": True},
    )
    job2 = _job(client, recruiter, title="Support newapp 2")
    cv2 = _cv(client, candidate, job2["id"])
    second = client.post(
        f"/api/applications/jobs/{job2['id']}/submit",
        json={"cv_document_id": cv2["id"]},
        headers=candidate,
    )
    assert second.status_code == 200, second.text
    emails = _emails_to(captured_smtp, "rh.newapp@exemple.cm")
    assert len(emails) == 1, emails
    assert "nouvelle candidature" in emails[0]["Subject"].lower()


def test_critical_email_bypasses_opt_in(client, captured_smtp):
    candidate = _candidate(
        client, "candidat.critique@orientskill.cm", name="Crise Test"
    )
    db = SessionLocal()
    try:
        user = db.query(models.User).filter_by(
            email="candidat.critique@orientskill.cm"
        ).first()
        # Canal e-mail explicitement désactivé.
        user.notification_prefs = {
            "email_enabled": False, "email": "",
            "events": {"message": False},
        }
        db.commit()
        db.refresh(user)

        normal = notifications.dispatch(
            db, user, "Message normal", "Corps", event="message",
        )
        assert normal == []
        assert _emails_to(captured_smtp, user.email) == []

        critical = notifications.dispatch(
            db, user, "Alerte de sécurité", "Corps critique",
            event="critical_alert",
        )
        assert critical and critical[0]["ok"] is True
        emails = _emails_to(captured_smtp, user.email)
        assert len(emails) == 1
        assert "désabonner" not in emails[0].get_content().lower()
    finally:
        db.close()


def test_unsubscribe_token_disables_job_alerts(client):
    headers = _candidate(
        client, "candidat.desabonnement@orientskill.cm", name="Désabo Test"
    )
    _enable_email(
        client, headers, "desabo@exemple.cm",
        {"new_match": True, "expiring": True, "agent": True,
         "message": True},
    )
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]
    token = notifications.unsubscribe_token(user_id)

    res = client.get(f"/api/profile/notifications/unsubscribe?token={token}")
    assert res.status_code == 200, res.text
    assert "Désabonnement confirmé" in res.text

    prefs = client.get("/api/profile/notifications", headers=headers).json()
    assert prefs["events"]["new_match"] is False
    assert prefs["events"]["expiring"] is False
    assert prefs["events"]["agent"] is False
    assert prefs["events"]["message"] is True

    bad = client.get(
        "/api/profile/notifications/unsubscribe?token=invalide"
    )
    assert bad.status_code == 400
    assert notifications.parse_unsubscribe_token("1.job_alerts.faux") is None


def test_recruiter_job_expiring_email(client, captured_smtp):
    from app.services.alerts import run_alerts_once

    recruiter = _recruiter(
        client, "recruteur.expiration@orientskill.cm",
        company="Expiration SARL",
    )
    _job(
        client, recruiter, title="Offre qui expire",
        deadline=datetime.utcnow() + timedelta(days=3),
    )
    _enable_email(
        client, recruiter, "rh.expiration@exemple.cm",
        {"job_expiring": True},
    )

    db = SessionLocal()
    try:
        run_alerts_once(db)
        first = _emails_to(captured_smtp, "rh.expiration@exemple.cm")
        assert len(first) == 1, first
        assert "expire bientôt" in first[0]["Subject"]
        # Une deuxième passe ne renvoie pas la même offre.
        run_alerts_once(db)
        assert len(_emails_to(captured_smtp, "rh.expiration@exemple.cm")) == 1
    finally:
        db.close()


def test_digest_frequency_immediate_and_daily_cap(
    client, captured_smtp, admin_headers
):
    from app.services.digest import run_digest_for_user

    recruiter = _recruiter(
        client, "recruteur.digest.prefs@orientskill.cm",
        company="Digest SARL",
    )
    candidate = _candidate(
        client, "candidat.digest.prefs@orientskill.cm", name="Dina Digest"
    )
    _profile(client, candidate)
    _job(client, recruiter, title="Support digest immédiat")
    _enable_email(
        client, candidate, "digest@exemple.cm",
        {"new_match": True}, frequency="immediate",
    )

    db = SessionLocal()
    try:
        user = db.query(models.User).filter_by(
            email="candidat.digest.prefs@orientskill.cm"
        ).first()
        now = datetime.utcnow()
        first = run_digest_for_user(db, user, now=now, digest_hour=8)
        assert first["notified"] == 1, first
        assert len(_emails_to(captured_smtp, "digest@exemple.cm")) == 1
        second = run_digest_for_user(db, user, now=now, digest_hour=8)
        assert second["notified"] == 0
        assert len(_emails_to(captured_smtp, "digest@exemple.cm")) == 1

        # Fréquence quotidienne : rien avant l'heure configurée, puis un
        # seul envoi pour la journée.
        daily = _candidate(
            client, "candidat.digest.daily@orientskill.cm",
            name="Dora Quotidien",
        )
        _profile(client, daily)
        _job(client, recruiter, title="Support digest quotidien")
        _enable_email(
            client, daily, "digest.daily@exemple.cm",
            {"new_match": True}, frequency="daily",
        )
        daily_user = db.query(models.User).filter_by(
            email="candidat.digest.daily@orientskill.cm"
        ).first()
        early = now.replace(hour=6, minute=0, second=0, microsecond=0)
        before = run_digest_for_user(
            db, daily_user, now=early, digest_hour=8
        )
        assert before["notified"] == 0
        assert _emails_to(captured_smtp, "digest.daily@exemple.cm") == []
        late = now.replace(hour=9, minute=0, second=0, microsecond=0)
        after = run_digest_for_user(
            db, daily_user, now=late, digest_hour=8
        )
        assert after["notified"] == 1, after
        assert len(_emails_to(captured_smtp, "digest.daily@exemple.cm")) == 1
    finally:
        db.close()
