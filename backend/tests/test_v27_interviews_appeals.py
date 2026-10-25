"""Recours après suspension et invitations à un entretien.

Deux parcours complets, sans données inventées :
- un compte suspendu prouve son identité et conteste ; l'admin tranche,
  la décision est tracée et visible dans les notifications ;
- un recruteur invite un candidat de sa shortlist à un créneau daté ; le
  candidat accepte depuis son espace, le recruteur voit la réponse.
"""
from datetime import datetime, timedelta
import re


def _candidate(client, email):
    reg = client.post("/api/auth/register", json={
        "email": email,
        "password": "pass1234",
        "full_name": "Candidat Test",
    })
    assert reg.status_code == 201, reg.text
    body = reg.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


def _recruiter(client, email):
    reg = client.post("/api/auth/register/recruiter", json={
        "email": email,
        "password": "pass1234",
        "full_name": "Recruteur Test",
        "recruiter_type": "company",
        "company_name": "Entreprise Entretien SARL",
        "company_sector": "Informatique / IT",
        "company_description": "Entreprise de test.",
        "company_location": "Douala",
    })
    assert reg.status_code == 201, reg.text
    body = reg.json()
    return {"Authorization": f"Bearer {body['token']}"}, body["user"]["id"]


def test_ban_appeal_is_treated_and_traced(client, admin_headers):
    email = "candidat.recours@orientskill.cm"
    headers, user_id = _candidate(client, email)
    ban = client.put(f"/api/admin/users/{user_id}/ban", json={
        "reason": "Signalement à vérifier",
    }, headers=admin_headers)
    assert ban.status_code == 200, ban.text

    login = client.post("/api/auth/login", json={
        "email": email, "password": "pass1234",
    })
    assert login.status_code == 403
    assert "contester" in login.json()["detail"].lower()

    # Identité prouvée par le mot de passe : mauvais mot de passe refusé.
    bad = client.post("/api/auth/appeal", json={
        "email": email,
        "password": "mauvais",
        "message": "Je conteste cette suspension, mon compte est légitime.",
    })
    assert bad.status_code == 401

    # Message trop court : refusé.
    short = client.post("/api/auth/appeal", json={
        "email": email, "password": "pass1234", "message": "Trop court",
    })
    assert short.status_code == 422

    appeal = client.post("/api/auth/appeal", json={
        "email": email,
        "password": "pass1234",
        "message": "Je conteste cette suspension : mon compte est légitime "
                   "et je n'ai jamais enfreint les règles de la plateforme.",
    })
    assert appeal.status_code == 201, appeal.text
    row = appeal.json()
    assert row["status"] == "pending"

    # Une nouvelle demande met à jour le recours ouvert (pas de doublon).
    again = client.post("/api/auth/appeal", json={
        "email": email,
        "password": "pass1234",
        "message": "Précision : je peux fournir toutes les pièces demandées.",
    })
    assert again.status_code == 201
    assert again.json()["id"] == row["id"]

    pending = client.get("/api/admin/appeals?status=pending",
                         headers=admin_headers).json()
    mine = next(a for a in pending if a["user_id"] == user_id)
    assert mine["user_email"] == email
    assert "Signalement" in mine["ban_reason"]

    decision = client.put(f"/api/admin/appeals/{mine['id']}", json={
        "decision": "accepted",
        "note": "Vérification faite, compte réactivé.",
    }, headers=admin_headers)
    assert decision.status_code == 200, decision.text
    assert decision.json()["status"] == "accepted"

    # Le compte est intact : la connexion refonctionne.
    login2 = client.post("/api/auth/login", json={
        "email": email, "password": "pass1234",
    })
    assert login2.status_code == 200, login2.text

    # La décision est visible dans les notifications.
    inbox = client.get("/api/inbox", headers=headers).json()
    assert any(e["kind"] == "appeal" and "accepté" in e["message"] for e in inbox)

    # Un recours déjà traité ne se traite pas deux fois.
    twice = client.put(f"/api/admin/appeals/{mine['id']}", json={
        "decision": "rejected",
    }, headers=admin_headers)
    assert twice.status_code == 400


def test_interview_invitation_and_candidate_response(client):
    rh, _recruiter_id = _recruiter(client, "recruteur.entretien@tgc.cm")
    ch, candidate_id = _candidate(client, "candidat.entretien@orientskill.cm")

    job = client.post("/api/recruiter/jobs", json={
        "title": "Développeur web",
        "company": "Entreprise Entretien SARL",
        "location": "Douala",
        "sector": "Informatique / IT",
        "contract_type": "CDI",
        "description": "Poste de test.",
        "required_skills": [{"name": "JavaScript", "importance": "core"}],
    }, headers=rh)
    assert job.status_code == 201, job.text
    job_id = job.json()["id"]

    slot = (datetime.now() + timedelta(days=3)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    base = {
        "candidate_id": candidate_id,
        "job_id": job_id,
        "slot_at": slot.isoformat(),
        "duration_min": 45,
        "subject": "Entretien pour le poste de développeur web",
        "message": "Bonjour, votre profil nous intéresse pour ce poste. "
                   "Merci de confirmer le créneau proposé.",
    }

    # Le candidat doit d'abord être dans une shortlist du recruteur.
    not_shortlisted = client.post("/api/recruiter/interviews", json=base,
                                   headers=rh)
    assert not_shortlisted.status_code == 400

    shortlist = client.post("/api/recruiter/shortlists", json={
        "name": "Finalistes développeur",
    }, headers=rh)
    assert shortlist.status_code == 201, shortlist.text
    sl_id = shortlist.json()["id"]
    added = client.post(f"/api/recruiter/shortlists/{sl_id}/items", json={
        "candidate_id": candidate_id,
    }, headers=rh)
    assert added.status_code == 200, added.text

    # Un créneau passé est refusé.
    past = dict(base)
    past["slot_at"] = (datetime.now() - timedelta(days=1)).isoformat()
    refused = client.post("/api/recruiter/interviews", json=past, headers=rh)
    assert refused.status_code == 400

    created = client.post("/api/recruiter/interviews", json=base, headers=rh)
    assert created.status_code == 201, created.text
    invite = created.json()
    token = invite["token"]
    assert invite["job_title"] == "Développeur web"
    assert invite["company"] == "Entreprise Entretien SARL"
    assert invite["status"] == "pending"
    # SMTP n'est pas configuré dans les tests : l'invitation reste visible
    # dans l'espace du candidat, le drapeau le dit honnêtement.
    assert invite["email_sent"] is False
    assert invite["calendar_url"].endswith(f"/interviews/{token}/calendar.ics")

    # Le fichier calendrier est public (le jeton fait office de secret) et
    # convertit le créneau camerounais en UTC.
    calendar = client.get(invite["calendar_url"])
    assert calendar.status_code == 200, calendar.text
    assert calendar.headers["content-type"].startswith("text/calendar")
    ics = calendar.text
    assert "BEGIN:VCALENDAR" in ics
    assert re.search(r"DTSTART:\d{8}T\d{6}Z", ics)
    assert re.search(r"DTEND:\d{8}T\d{6}Z", ics)
    assert "STATUS:TENTATIVE" in ics
    assert "SUMMARY:" in ics and "Entretien" in ics

    # La vue publique du lien e-mail fonctionne sans connexion.
    public = client.get(f"/api/interviews/{token}")
    assert public.status_code == 200
    assert public.json()["job_title"] == "Développeur web"

    # Le candidat voit l'invitation, et elle apparaît dans ses notifications,
    # rubrique distincte de la messagerie. Le badge tombe après consultation.
    mine = client.get("/api/interviews", headers=ch).json()
    assert any(row["token"] == token for row in mine)
    notifications = client.get("/api/notifications", headers=ch).json()
    assert any(e["kind"] == "interview" and "Développeur web" in e["message"]
               for e in notifications)
    assert client.get("/api/notifications/unread-count", headers=ch).json()["count"] >= 1
    seen = client.post("/api/notifications/seen", headers=ch)
    assert seen.status_code == 200, seen.text
    assert client.get("/api/notifications/unread-count",
                      headers=ch).json()["count"] == 0
    # L'ancien chemin reste un alias masqué, sans casser les clients.
    inbox = client.get("/api/inbox", headers=ch).json()
    assert any(e["kind"] == "interview" for e in inbox)

    # Un autre candidat ne peut pas répondre.
    other_h, _ = _candidate(client, "candidat.autre-entretien@orientskill.cm")
    forbidden = client.post(f"/api/interviews/{token}/respond", json={
        "decision": "accepted",
    }, headers=other_h)
    assert forbidden.status_code == 403

    answered = client.post(f"/api/interviews/{token}/respond", json={
        "decision": "accepted",
        "note": "Créneau confirmé, merci.",
    }, headers=ch)
    assert answered.status_code == 200, answered.text
    assert answered.json()["status"] == "accepted"
    assert answered.json()["candidate_note"] == "Créneau confirmé, merci."

    # Le même fichier reflète désormais la confirmation.
    confirmed = client.get(answered.json()["calendar_url"])
    assert confirmed.status_code == 200
    assert "STATUS:CONFIRMED" in confirmed.text
    assert "SEQUENCE:1" in confirmed.text

    twice = client.post(f"/api/interviews/{token}/respond", json={
        "decision": "declined",
    }, headers=ch)
    assert twice.status_code == 400

    # Le recruteur voit la réponse dans sa liste.
    sent = client.get("/api/recruiter/interviews", headers=rh).json()
    row = next(r for r in sent if r["token"] == token)
    assert row["status"] == "accepted"
    assert row["candidate_note"] == "Créneau confirmé, merci."

    # Le recruteur ne peut pas inviter pour l'offre d'un autre.
    rh2, _ = _recruiter(client, "recruteur.autre-entretien@tgc.cm")
    shortlist2 = client.post("/api/recruiter/shortlists", json={
        "name": "Liste autre",
    }, headers=rh2).json()
    client.post(f"/api/recruiter/shortlists/{shortlist2['id']}/items", json={
        "candidate_id": candidate_id,
    }, headers=rh2)
    not_my_job = client.post("/api/recruiter/interviews", json=base, headers=rh2)
    assert not_my_job.status_code == 403
