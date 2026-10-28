"""Point 15 : machine à états unique des candidatures.

Le candidat prépare, envoie, accepte, décline ou retire. Le recruteur
instruit (attente, entretien, offre, refus). L'admin arbitre avec un
motif obligatoire. Chaque transition est contrôlée par l'API et tracée
avec son auteur et, le cas échéant, son motif.
"""
from app import schemas
from app.services import applications


def _candidate(client, email: str) -> dict:
    res = client.post("/api/auth/register", json={
        "email": email,
        "password": "pass1234",
        "full_name": "Candidat Workflow",
    })
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def _recruiter(client, email: str, company: str) -> dict:
    res = client.post("/api/auth/register/recruiter", json={
        "email": email,
        "password": "pass1234",
        "recruiter_type": "company",
        "company_name": company,
        "company_sector": "IT",
        "company_description": "Test workflow.",
        "company_location": "Douala",
    })
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def _job(client, headers: dict, title: str) -> dict:
    res = client.post("/api/recruiter/jobs", json={
        "title": title,
        "company": "Workflow SARL",
        "location": "Douala",
        "sector": "IT",
        "contract_type": "CDI",
        "required_skills": [],
    }, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _application(client, headers: dict, job_id: int) -> dict:
    res = client.post(
        "/api/applications", json={"job_id": job_id}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()


def _patch(client, url: str, headers: dict, **payload):
    return client.patch(url, json=payload, headers=headers)


def test_status_sets_are_aligned():
    """Les statuts du service et du schéma restent une source unique."""
    assert set(applications.STATUS_LABELS) == schemas.APPLICATION_STATUSES
    assert applications.CLOSED_STATUSES <= set(applications.STATUS_LABELS)


def test_candidate_cannot_self_assign_recruiter_statuses(client):
    ch = _candidate(client, "workflow.candidat1@orientskill.cm")
    rh = _recruiter(client, "workflow.rh1@tgc.cm", "Workflow RH 1")
    job = _job(client, rh, "Développeur workflow")
    app = _application(client, ch, job["id"])

    refused = _patch(
        client, f"/api/applications/{app['id']}", ch, status="entretien"
    )
    assert refused.status_code == 403
    assert "candidat" in refused.json()["detail"]

    sent = _patch(
        client, f"/api/applications/{app['id']}", ch, status="envoyee"
    )
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["status"] == "envoyee"
    last = body["timeline"][-1]
    assert last["by"] == "candidat"


def test_candidate_accepts_or_declines_offer(client):
    ch = _candidate(client, "workflow.candidat2@orientskill.cm")
    rh = _recruiter(client, "workflow.rh2@tgc.cm", "Workflow RH 2")
    job = _job(client, rh, "Analyste workflow")
    app = _application(client, ch, job["id"])

    assert _patch(
        client, f"/api/applications/{app['id']}", ch, status="envoyee"
    ).status_code == 200
    assert _patch(
        client, f"/api/recruiter/applications/{app['id']}", rh,
        status="entretien",
    ).status_code == 200
    assert _patch(
        client, f"/api/recruiter/applications/{app['id']}", rh,
        status="offre",
    ).status_code == 200

    # Le recruteur ne peut pas accepter à la place du candidat.
    refused = _patch(
        client, f"/api/recruiter/applications/{app['id']}", rh,
        status="acceptee",
    )
    assert refused.status_code == 403

    accepted = _patch(
        client, f"/api/applications/{app['id']}", ch, status="acceptee"
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "acceptee"
    assert accepted.json()["timeline"][-1]["event"].startswith(
        "Offre acceptée"
    )

    # Statut terminal : plus aucune transition, même pour le recruteur.
    blocked = _patch(
        client, f"/api/recruiter/applications/{app['id']}", rh,
        status="refusee",
    )
    assert blocked.status_code == 403


def test_candidate_declines_offer_and_reason_is_traced(client):
    ch = _candidate(client, "workflow.candidat3@orientskill.cm")
    rh = _recruiter(client, "workflow.rh3@tgc.cm", "Workflow RH 3")
    job = _job(client, rh, "Chargé de workflow")
    app = _application(client, ch, job["id"])
    _patch(client, f"/api/applications/{app['id']}", ch, status="envoyee")
    _patch(
        client, f"/api/recruiter/applications/{app['id']}", rh,
        status="entretien",
    )
    _patch(
        client, f"/api/recruiter/applications/{app['id']}", rh,
        status="offre",
    )

    declined = _patch(
        client, f"/api/applications/{app['id']}", ch,
        status="declinee", reason="Proposition salariale trop basse",
    )
    assert declined.status_code == 200, declined.text
    body = declined.json()
    assert body["status"] == "declinee"
    last = body["timeline"][-1]
    assert last["by"] == "candidat"
    assert last["reason"] == "Proposition salariale trop basse"


def test_recruiter_cannot_skip_candidate_submission(client):
    ch = _candidate(client, "workflow.candidat4@orientskill.cm")
    rh = _recruiter(client, "workflow.rh4@tgc.cm", "Workflow RH 4")
    job = _job(client, rh, "Test sans envoi")
    app = _application(client, ch, job["id"])

    refused = _patch(
        client, f"/api/recruiter/applications/{app['id']}", rh,
        status="entretien",
    )
    assert refused.status_code == 403
    assert "recruteur" in refused.json()["detail"]


def test_admin_arbitration_requires_reason_and_is_traced(
    client, admin_headers
):
    ch = _candidate(client, "workflow.candidat5@orientskill.cm")
    rh = _recruiter(client, "workflow.rh5@tgc.cm", "Workflow RH 5")
    job = _job(client, rh, "Arbitrage workflow")
    app = _application(client, ch, job["id"])
    _patch(client, f"/api/applications/{app['id']}", ch, status="envoyee")

    # Motif absent ou trop court : refus.
    missing = client.patch(
        f"/api/admin/applications/{app['id']}",
        json={"status": "entretien"},
        headers=admin_headers,
    )
    assert missing.status_code == 422
    too_short = _patch(
        client, f"/api/admin/applications/{app['id']}", admin_headers,
        status="entretien", reason="ok",
    )
    assert too_short.status_code == 422

    # L'admin peut rouvrir un statut terminal, avec motif.
    _patch(
        client, f"/api/recruiter/applications/{app['id']}", rh,
        status="refusee", reason="Profil incomplet",
    )
    reopened = _patch(
        client, f"/api/admin/applications/{app['id']}", admin_headers,
        status="entretien",
        reason="Dossier complété après relance du candidat",
    )
    assert reopened.status_code == 200, reopened.text
    body = reopened.json()
    assert body["previous"] == "refusee"
    assert body["status"] == "entretien"

    mine = client.get("/api/applications", headers=ch).json()
    target = next(a for a in mine if a["id"] == app["id"])
    last = target["timeline"][-1]
    assert last["event"].startswith("Arbitrage administrateur")
    assert last["reason"] == "Dossier complété après relance du candidat"
    assert last["by"]

    # Même statut : refusé pour éviter les faux événements.
    same = _patch(
        client, f"/api/admin/applications/{app['id']}", admin_headers,
        status="entretien", reason="Toujours en entretien",
    )
    assert same.status_code == 422


def test_admin_application_route_is_admin_only(client):
    ch = _candidate(client, "workflow.candidat6@orientskill.cm")
    rh = _recruiter(client, "workflow.rh6@tgc.cm", "Workflow RH 6")
    job = _job(client, rh, "Accès admin workflow")
    app = _application(client, ch, job["id"])

    refused = _patch(
        client, f"/api/admin/applications/{app['id']}", ch,
        status="entretien", reason="Tentative candidat",
    )
    assert refused.status_code == 403
