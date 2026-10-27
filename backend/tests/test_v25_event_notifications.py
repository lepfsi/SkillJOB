"""Notifications par événement (V25) : opt-in e-mail par type.

Pour chaque événement (nouveau match, échéance proche, alerte agent,
message recruteur, mise à jour de candidature), le candidat choisit :
e-mail aussi, ou uniquement in-app. Sans opt-in, aucun e-mail part.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from app import models
from app.database import SessionLocal
from app.services import notifications
from app.services.alerts import build_agent_body, run_alerts_once
from app.services.eventlog import build_inbox

EVENT_KEYS = {
    "new_match", "expiring", "agent", "message", "application",
    "verification_decision", "interview",
}


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
        "email": email, "password": "pass1234", "full_name": "Nadia Notif",
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def _recruiter(client, email):
    reg = client.post("/api/auth/register/recruiter", json={
        "email": email, "password": "pass1234",
        "recruiter_type": "company",
        "company_name": "Notif RH",
        "company_sector": "IT",
        "company_description": "Test.",
        "company_location": "Douala",
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def _smtp(client, admin_headers, enabled):
    res = client.put("/api/admin/settings/smtp", json={
        "data": {"enabled": enabled, "host": "smtp.exemple.cm", "port": 587,
                 "username": "no@orientskill.cm", "password": "secret",
                 "from_email": "no@orientskill.cm", "use_tls": True},
    }, headers=admin_headers)
    assert res.status_code == 200, res.text


def _enable_email(client, headers, events):
    """Active le canal e-mail et les opt-in par événement."""
    body = {"email_enabled": True, "email": "nadia@exemple.cm", "events": events}
    res = client.put("/api/profile/notifications", json=body, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _matching_profile(client, headers):
    client.put("/api/profile", json={
        "title": "Technicienne support",
        "summary": "Profil de test notifications.",
        "skills": [{"skill": "Support informatique", "proficiency": "avance"}],
    }, headers=headers)


def _deadline_job(client, admin_headers, title, days):
    job = client.post("/api/admin/jobs", json={
        "title": title,
        "company": "Echeance SARL",
        "location": "Douala", "sector": "IT", "contract_type": "CDD",
        "description": "Support.", "requirements": "Rigueur.",
        "deadline": (datetime.utcnow() + timedelta(days=days)).isoformat(),
        "required_skills": [
            {"name": "Support informatique", "importance": "core"},
        ],
    }, headers=admin_headers)
    assert job.status_code == 201, job.text
    return job.json()


def test_prefs_expose_event_catalog_and_defaults(client, demo_headers):
    """GET renvoie le catalogue et les opt-in par défaut (in-app)."""
    prefs = client.get("/api/profile/notifications", headers=demo_headers).json()
    assert set(prefs["events"].keys()) == EVENT_KEYS
    assert all(value is False for value in prefs["events"].values())
    assert prefs["event_types"]["expiring"].startswith("Offre correspondante")

    # PUT : mise à jour partielle des événements, puis persistance.
    updated = client.put("/api/profile/notifications", json={
        "events": {"expiring": True, "message": True},
    }, headers=demo_headers)
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["events"]["expiring"] is True
    assert body["events"]["message"] is True
    assert body["events"]["agent"] is False
    again = client.get("/api/profile/notifications", headers=demo_headers).json()
    assert again["events"]["expiring"] is True

    # Nettoyage : le candidat démo reste in-app par défaut.
    client.put("/api/profile/notifications", json={
        "events": {"expiring": False, "message": False},
    }, headers=demo_headers)


def test_recruiter_message_email_only_when_opted_in(
    client, admin_headers, monkeypatch
):
    """Sans opt-in « message », le message reste in-app ; avec, un e-mail part."""
    _smtp(client, admin_headers, True)
    FakeSMTP.instances = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)

    rh = _recruiter(client, "recruteur.notif1@tgc.cm")
    headers = _candidate(client, "candidat.notif1@orientskill.cm")
    _enable_email(client, headers, {"message": False})
    user_id = client.get("/api/auth/me", headers=headers).json()["id"]

    try:
        sent = client.post("/api/messages", json={
            "recipient_id": user_id, "body": "Bonjour, votre profil nous intéresse.",
        }, headers=rh)
        assert sent.status_code == 201, sent.text
        assert len(FakeSMTP.instances) == 0, "aucun e-mail sans opt-in"

        _enable_email(client, headers, {"message": True})
        sent2 = client.post("/api/messages", json={
            "recipient_id": user_id, "body": "Pouvons-nous échanger ?",
        }, headers=rh)
        assert sent2.status_code == 201, sent2.text
        assert len(FakeSMTP.instances) == 1
        subjects = [m["Subject"] for m in FakeSMTP.instances[0].messages]
        assert any("nouveau message" in s for s in subjects)
    finally:
        _smtp(client, admin_headers, False)


def test_application_update_email_only_when_opted_in(
    client, admin_headers, monkeypatch
):
    """Mise à jour de candidature : e-mail seulement si le candidat l'a choisi."""
    _smtp(client, admin_headers, True)
    FakeSMTP.instances = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)

    rh = _recruiter(client, "recruteur.notif2@tgc.cm")
    headers = _candidate(client, "candidat.notif2@orientskill.cm")
    _enable_email(client, headers, {"application": False})

    job = client.post("/api/recruiter/jobs", json={
        "title": "Poste notif", "company": "Notif RH",
        "location": "Douala", "sector": "IT", "contract_type": "CDI",
        "required_skills": [],
    }, headers=rh).json()
    app = client.post("/api/applications", json={"job_id": job["id"]},
                      headers=headers).json()

    try:
        client.patch(f"/api/recruiter/applications/{app['id']}",
                     json={"status": "entretien"}, headers=rh)
        assert len(FakeSMTP.instances) == 0, "aucun e-mail sans opt-in"

        _enable_email(client, headers, {"application": True})
        client.patch(f"/api/recruiter/applications/{app['id']}",
                     json={"status": "offre"}, headers=rh)
        assert len(FakeSMTP.instances) == 1
        subject = FakeSMTP.instances[0].messages[0]["Subject"]
        assert "candidature a évolué" in subject
    finally:
        _smtp(client, admin_headers, False)


def test_inbox_lists_expiring_event(client, admin_headers):
    """L'inbox applicative signale les échéances proches, sans e-mail."""
    headers = _candidate(client, "candidat.echeance@orientskill.cm")
    _matching_profile(client, headers)
    job = _deadline_job(client, admin_headers, "Support échéance proche", 3)

    inbox = client.get("/api/inbox", headers=headers).json()
    expiring = [e for e in inbox if e["kind"] == "expiring"]
    assert any(e["job_id"] == job["id"] for e in expiring), inbox
    assert all("Date limite proche" in e["message"] for e in expiring)

    # Déjà postulée : l'alerte disparaît de l'inbox.
    client.post("/api/applications", json={"job_id": job["id"]}, headers=headers)
    inbox2 = client.get("/api/inbox", headers=headers).json()
    assert not [
        e for e in inbox2
        if e["kind"] == "expiring" and e["job_id"] == job["id"]
    ]


def test_inbox_ignores_jobs_published_before_account():
    """Un compte neuf ne voit pas les offres publiées avant sa création."""
    since = datetime.utcnow() - timedelta(hours=1)
    old_job = SimpleNamespace(
        id=1001,
        title="Offre antérieure",
        company="Ancienne SARL",
        location="Douala",
        published_at=since - timedelta(days=2),
        required_skills=[],
        deadline=None,
    )
    new_job = SimpleNamespace(
        id=1002,
        title="Offre du jour",
        company="Nouvelle SARL",
        location="Douala",
        published_at=since + timedelta(minutes=10),
        required_skills=[],
        deadline=None,
    )
    inbox = build_inbox(None, [old_job, new_job], [], since=since)
    assert any(event["job_id"] == new_job.id for event in inbox)
    assert not any(event["job_id"] == old_job.id for event in inbox)
    assert all(event["at"] >= since for event in inbox)


def test_new_account_inbox_starts_at_account_creation(client):
    """L'API applique le même filtre pour un compte fraîchement créé."""
    reg = client.post("/api/auth/register", json={
        "email": "compte.neuf.notifs@orientskill.cm",
        "password": "pass1234",
        "full_name": "Compte Neuf",
    })
    assert reg.status_code == 201, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    me = client.get("/api/auth/me", headers=headers).json()
    created_at = datetime.fromisoformat(me["created_at"].replace("Z", ""))
    inbox = client.get("/api/inbox", headers=headers).json()
    assert all(
        datetime.fromisoformat(event["at"].replace("Z", "")) >= created_at
        for event in inbox
    )


def test_inbox_drops_events_older_than_30_days():
    """Rétention in-app : un événement de plus de 30 jours disparaît."""
    old_job = SimpleNamespace(
        id=999,
        title="Vieux poste",
        company="Entreprise ancienne",
        location="Douala",
        published_at=datetime.utcnow() - timedelta(days=45),
        required_skills=[],
        deadline=None,
    )
    recent_job = SimpleNamespace(
        id=998,
        title="Poste récent",
        company="Entreprise récente",
        location="Douala",
        published_at=datetime.utcnow() - timedelta(days=2),
        required_skills=[],
        deadline=None,
    )
    inbox = build_inbox(None, [old_job, recent_job], [])
    assert any(e["job_id"] == recent_job.id for e in inbox)
    assert not any(e["job_id"] == old_job.id for e in inbox)


def test_alerts_once_sends_and_dedupes(client, admin_headers, monkeypatch):
    """La passe planifiée envoie l'échéance une seule fois (journal)."""
    _smtp(client, admin_headers, True)
    FakeSMTP.instances = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)

    headers = _candidate(client, "candidat.alerte@orientskill.cm")
    _matching_profile(client, headers)
    _enable_email(client, headers, {"expiring": True, "agent": True})
    _deadline_job(client, admin_headers, "Support alerte échéance", 2)

    db = SessionLocal()
    try:
        first = run_alerts_once(db)
        assert first["notified"] >= 1, first
        subjects = [
            m["Subject"]
            for inst in FakeSMTP.instances
            for m in inst.messages
        ]
        assert any("expire bientôt" in s for s in subjects)
        # Un conseil de l'agent part au plus une fois par jour.
        assert any("votre agent a repéré" in s for s in subjects)

        FakeSMTP.instances = []
        second = run_alerts_once(db)
        assert second["notified"] == 0, "déduplication par le journal"
        assert len(FakeSMTP.instances) == 0
    finally:
        db.close()
        _smtp(client, admin_headers, False)


def test_agent_body_prioritizes_urgent_deadline(client, admin_headers):
    """Le conseil de l'agent met l'urgence en tête (jamais d'invention)."""
    headers = _candidate(client, "candidat.conseil@orientskill.cm")
    _matching_profile(client, headers)
    job = _deadline_job(client, admin_headers, "Support conseil urgent", 1)

    db = SessionLocal()
    try:
        user = (
            db.query(models.User)
            .filter_by(email="candidat.conseil@orientskill.cm")
            .first()
        )
        profile = (
            db.query(models.Profile)
            .filter_by(user_id=user.id)
            .first()
        )
        jobs = db.query(models.Job).filter(models.Job.id == job["id"]).all()
        body = build_agent_body(user, profile, jobs, [])
        assert "urgence" in body
        assert job["title"] in body
    finally:
        db.close()
