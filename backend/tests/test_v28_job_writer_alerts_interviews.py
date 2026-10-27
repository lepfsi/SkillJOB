"""Rédaction assistée, demandes de créneau et alertes administratives.

Trois parcours complétés ensemble :
- un recruteur obtient une proposition d'offre exploitable, avec ou sans
  modèle IA, sans qu'aucune donnée ne soit enregistrée sans validation ;
- un candidat peut demander un autre créneau avec des disponibilités
  explicites, puis le recruteur propose, accepte ou refuse depuis une file
  dédiée ;
- l'équipe d'administration reçoit des alertes par catégorie, avec un
  journal complet et un test de routage sans envoi réel.
"""
import json
from datetime import datetime, timedelta


def _candidate(client, email):
    reg = client.post("/api/auth/register", json={
        "email": email,
        "password": "pass1234",
        "full_name": "Candidat Demandes",
    })
    assert reg.status_code == 201, reg.text
    body = reg.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


def _recruiter(client, email):
    reg = client.post("/api/auth/register/recruiter", json={
        "email": email,
        "password": "pass1234",
        "full_name": "Recruteur Demandes",
        "recruiter_type": "company",
        "company_name": "Entreprise Demandes SARL",
        "company_sector": "Informatique / IT",
        "company_description": "Entreprise de test.",
        "company_location": "Douala",
    })
    assert reg.status_code == 201, reg.text
    body = reg.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


def _future(days, hour=10):
    return (datetime.now() + timedelta(days=days)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


# ------------------------------------------------- Rédaction assistée (6)

def test_job_writer_rules_mode_is_useful_and_persists_nothing(
    client, demo_headers, admin_headers
):
    description = (
        "Nous recrutons un technicien support informatique chez "
        "Numérik Services à Douala. CDI. Compétences : Windows Server, TCP/IP."
    )
    before = client.get("/api/admin/stats", headers=admin_headers).json()["jobs"]

    forbidden = client.post("/api/jobs/write", json={
        "description": description,
    }, headers=demo_headers)
    assert forbidden.status_code == 403

    response = client.post("/api/jobs/write", json={
        "description": description,
    }, headers=admin_headers)
    assert response.status_code == 200, response.text
    draft = response.json()

    assert draft["mode"] == "rules"
    assert "technicien support" in draft["title"].lower()
    assert draft["location"] == "Douala"
    assert draft["contract_type"] == "CDI"
    assert draft["description"].strip()
    assert draft["requirements"].strip()
    names = [skill["name"] for skill in draft["required_skills"]]
    assert "Windows Server" in names
    assert draft["warning"]
    assert "id" not in draft

    after = client.get("/api/admin/stats", headers=admin_headers).json()["jobs"]
    assert after == before

    short = client.post("/api/jobs/write", json={
        "description": "Trop",
    }, headers=admin_headers)
    assert short.status_code == 422


def test_job_writer_uses_llm_when_available(client, admin_headers, monkeypatch):
    from app.services import job_writer

    reply = json.dumps({
        "title": "Technicien support informatique",
        "description": (
            "Nous recherchons un technicien support informatique pour "
            "Numérik Services à Douala. Vous assurez le support de premier "
            "niveau et le suivi des incidents."
        ),
        "requirements": (
            "Profil recherché :\n"
            "- Maîtrise de Windows Server.\n"
            "- Connaissance de TCP/IP."
        ),
    })

    def fake_completion(db, messages, *args, **kwargs):
        return reply

    monkeypatch.setattr(
        job_writer.llm_client, "chat_completion", fake_completion
    )
    response = client.post("/api/jobs/write", json={
        "description": (
            "Technicien support informatique chez Numérik Services à "
            "Douala. CDI. Windows Server, TCP/IP."
        ),
    }, headers=admin_headers)
    assert response.status_code == 200, response.text
    draft = response.json()
    assert draft["mode"] == "llm"
    assert "support de premier niveau" in draft["description"]
    assert "Windows Server" in draft["requirements"]
    assert "id" not in draft


# ------------------------------- Demandes de créneau et refus réel (7 et 8)

def test_interview_reschedule_queue_and_recruiter_decisions(client):
    rh, _recruiter_id = _recruiter(client, "recruteur.demandes@tgc.cm")
    ch, candidate_id = _candidate(client, "candidat.demandes@orientskill.cm")

    job = client.post("/api/recruiter/jobs", json={
        "title": "Technicien support",
        "company": "Entreprise Demandes SARL",
        "location": "Douala",
        "sector": "Informatique / IT",
        "contract_type": "CDI",
        "description": "Support de premier niveau.",
        "required_skills": [{"name": "Windows Server", "importance": "core"}],
    }, headers=rh)
    assert job.status_code == 201, job.text
    job_id = job.json()["id"]

    shortlist = client.post("/api/recruiter/shortlists", json={
        "name": "File support",
    }, headers=rh)
    assert shortlist.status_code == 201, shortlist.text
    added = client.post(
        f"/api/recruiter/shortlists/{shortlist.json()['id']}/items",
        json={"candidate_id": candidate_id},
        headers=rh,
    )
    assert added.status_code == 200, added.text

    invite = client.post("/api/recruiter/interviews", json={
        "candidate_id": candidate_id,
        "job_id": job_id,
        "slot_at": _future(3).isoformat(),
        "duration_min": 45,
        "subject": "Entretien technicien support",
        "message": "Merci de confirmer le créneau proposé.",
    }, headers=rh)
    assert invite.status_code == 201, invite.text
    token = invite.json()["token"]

    # Une demande d'autre créneau sans disponibilité est refusée.
    missing = client.post(f"/api/interviews/{token}/respond", json={
        "decision": "declined",
        "note": "Je ne suis pas disponible.",
    }, headers=ch)
    assert missing.status_code == 422

    requested = [_future(5, hour=10).isoformat(), _future(6, hour=15).isoformat()]
    declined = client.post(f"/api/interviews/{token}/respond", json={
        "decision": "declined",
        "note": "Voici mes disponibilités.",
        "requested_slots": requested,
    }, headers=ch)
    assert declined.status_code == 200, declined.text
    row = declined.json()
    assert row["status"] == "declined"
    assert len(row["requested_slots"]) == 2
    assert row["awaiting_recruiter"] is True
    assert any(event["action"] == "declined" for event in row["history"])

    # La demande apparaît dans la file dédiée du recruteur.
    queue = client.get("/api/recruiter/interviews/requests", headers=rh).json()
    assert any(item["token"] == token for item in queue)

    # Le recruteur propose un nouveau créneau.
    proposal = client.post(f"/api/recruiter/interviews/{row['id']}/respond", json={
        "action": "propose",
        "slot_at": _future(7, hour=11).isoformat(),
        "note": "Ce créneau vous convient-il ?",
    }, headers=rh)
    assert proposal.status_code == 200, proposal.text
    proposed = proposal.json()
    assert proposed["status"] == "pending"
    assert proposed["requested_slots"] == []
    assert any(event["action"] == "slot_proposed" for event in proposed["history"])

    queue_after = client.get("/api/recruiter/interviews/requests", headers=rh).json()
    assert not any(item["token"] == token for item in queue_after)

    notifications = client.get("/api/notifications", headers=ch).json()
    assert any("nouveau créneau" in event["message"] for event in notifications)

    # Le candidat refuse explicitement ce nouveau créneau.
    refused = client.post(f"/api/interviews/{token}/respond", json={
        "decision": "refused",
        "note": "Je ne pourrai pas être disponible.",
    }, headers=ch)
    assert refused.status_code == 200, refused.text
    assert refused.json()["status"] == "refused"
    assert any(event["action"] == "refused" for event in refused.json()["history"])

    calendar = client.get(refused.json()["calendar_url"])
    assert calendar.status_code == 200
    assert "STATUS:CANCELLED" in calendar.text

    # Le refus réel n'apparaît plus dans la file du recruteur.
    queue_refused = client.get("/api/recruiter/interviews/requests", headers=rh).json()
    assert not any(item["token"] == token for item in queue_refused)


def test_recruiter_accepts_candidate_requested_slot(client):
    rh, _recruiter_id = _recruiter(client, "recruteur.accepte@tgc.cm")
    ch, candidate_id = _candidate(client, "candidat.accepte@orientskill.cm")

    job = client.post("/api/recruiter/jobs", json={
        "title": "Assistant support",
        "company": "Entreprise Demandes SARL",
        "location": "Douala",
        "sector": "Informatique / IT",
        "contract_type": "CDD",
        "description": "Support utilisateur.",
        "required_skills": [],
    }, headers=rh)
    assert job.status_code == 201, job.text
    job_id = job.json()["id"]

    shortlist = client.post("/api/recruiter/shortlists", json={
        "name": "File assistant",
    }, headers=rh)
    client.post(
        f"/api/recruiter/shortlists/{shortlist.json()['id']}/items",
        json={"candidate_id": candidate_id},
        headers=rh,
    )

    invite = client.post("/api/recruiter/interviews", json={
        "candidate_id": candidate_id,
        "job_id": job_id,
        "slot_at": _future(4).isoformat(),
        "duration_min": 30,
        "subject": "Entretien assistant support",
        "message": "Merci de confirmer le créneau proposé.",
    }, headers=rh)
    assert invite.status_code == 201, invite.text
    token = invite.json()["token"]
    invite_id = invite.json()["id"]

    requested = [_future(8, hour=14).isoformat()]
    declined = client.post(f"/api/interviews/{token}/respond", json={
        "decision": "declined",
        "note": "Je propose ce créneau.",
        "requested_slots": requested,
    }, headers=ch)
    assert declined.status_code == 200, declined.text

    # Le recruteur ne peut pas accepter un créneau hors proposition.
    outside = client.post(f"/api/recruiter/interviews/{invite_id}/respond", json={
        "action": "accept_requested",
        "slot_at": _future(9, hour=9).isoformat(),
    }, headers=rh)
    assert outside.status_code == 422

    accepted = client.post(f"/api/recruiter/interviews/{invite_id}/respond", json={
        "action": "accept_requested",
        "slot_at": requested[0],
        "note": "C'est noté, à bientôt.",
    }, headers=rh)
    assert accepted.status_code == 200, accepted.text
    row = accepted.json()
    assert row["status"] == "accepted"
    assert row["recruiter_responded_at"] is not None
    assert any(event["action"] == "request_accepted" for event in row["history"])

    notifications = client.get("/api/notifications", headers=ch).json()
    assert any("accepté votre créneau" in event["message"] for event in notifications)

    calendar = client.get(row["calendar_url"])
    assert "STATUS:CONFIRMED" in calendar.text


# ------------------------------------- Équipe et alertes admin (point 10)

def test_admin_alert_team_journal_and_routing(client, admin_headers, monkeypatch):
    from app.services import admin_alerts

    settings = client.get("/api/admin/alert-settings", headers=admin_headers)
    assert settings.status_code == 200, settings.text
    body = settings.json()
    assert {c["key"] for c in body["categories"]} >= {
        "verification", "appeal", "report", "ingestion", "critical",
    }
    assert isinstance(body["journal"], list)

    # Un destinataire est obligatoire pour les alertes critiques.
    invalid = client.put("/api/admin/alert-settings", json={
        "enabled": True,
        "categories": {key: True for key in (
            "verification", "appeal", "report", "ingestion", "critical"
        )},
        "recipients": [],
    }, headers=admin_headers)
    assert invalid.status_code == 422

    saved = client.put("/api/admin/alert-settings", json={
        "enabled": True,
        "categories": {key: True for key in (
            "verification", "appeal", "report", "ingestion", "critical"
        )},
        "recipients": [{
            "name": "Cellule modération",
            "email": "moderation@orientskill.cm",
            "categories": ["report", "critical"],
        }],
    }, headers=admin_headers)
    assert saved.status_code == 200, saved.text
    config = saved.json()["config"]
    assert len(config["recipients"]) == 1
    assert config["recipients"][0]["categories"] == ["report", "critical"]

    # Test de routage : aucun e-mail n'est envoyé.
    routing = client.post("/api/admin/alert-settings/test", json={
        "category": "report",
    }, headers=admin_headers)
    assert routing.status_code == 200, routing.text
    assert routing.json()["ok"] is True
    assert "moderation@orientskill.cm" in routing.json()["recipients"]

    # Déclenche une alerte réelle sans réseau : l'envoi est simulé.
    calls = []

    def fake_send_email(db, to_email, subject, body, *args, **kwargs):
        calls.append((to_email, subject))
        return True, "E-mail simulé."

    monkeypatch.setattr(admin_alerts.notifications, "send_email", fake_send_email)

    job = client.post("/api/admin/jobs", json={
        "title": "Offre signalée test alertes",
        "company": "Entreprise Test Alertes",
        "location": "Douala",
        "sector": "Informatique / IT",
        "contract_type": "CDI",
        "description": "Offre utilisée pour tester le journal des alertes.",
        "requirements": "Aucune.",
        "required_skills": [],
    }, headers=admin_headers)
    assert job.status_code in (200, 201), job.text
    job_id = job.json()["id"]

    candidate_headers, _candidate_id = _candidate(
        client, "candidat.alertes@orientskill.cm"
    )
    report = client.post(f"/api/jobs/{job_id}/reports", json={
        "reason": "arnaque",
        "details": "Cette offre demande de l'argent pour postuler.",
    }, headers=candidate_headers)
    assert report.status_code == 201, report.text

    assert any(
        email == "moderation@orientskill.cm" and "Signalement" in subject
        for email, subject in calls
    )

    journal = client.get("/api/admin/alert-journal", headers=admin_headers).json()
    entry = next(
        row for row in journal if row["category"] == "report"
        and "Offre signalée test alertes" in row["subject"]
    )
    assert entry["sent_count"] == 1
    assert entry["failed_count"] == 0
    assert entry["recipients"] == ["moderation@orientskill.cm"]
