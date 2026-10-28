"""Page recruteur des candidatures reçues (point 20).

Les candidatures sont groupées par offre, avec total, nouvelles
candidatures, score de correspondance, filtres et pagination. Les actions
de statut restent celles autorisées au recruteur.
"""
from datetime import date


def _recruiter(client, email, company):
    res = client.post("/api/auth/register/recruiter", json={
        "email": email, "password": "pass1234",
        "recruiter_type": "company",
        "company_name": company,
        "company_sector": "Informatique / IT",
        "company_description": "Test candidatures reçues.",
        "company_location": "Douala",
    })
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def _candidate(client, email, name):
    res = client.post("/api/auth/register", json={
        "email": email, "password": "pass1234", "full_name": name,
    })
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def _profile(client, headers):
    res = client.put("/api/profile", json={
        "title": "Technicien support",
        "summary": "Profil de test candidatures reçues.",
        "skills": [
            {"skill": "Support informatique", "proficiency": "avance"},
            {"skill": "Gestion des incidents", "proficiency": "intermediaire"},
        ],
    }, headers=headers)
    assert res.status_code == 200, res.text


def _job(client, headers, title):
    res = client.post("/api/recruiter/jobs", json={
        "title": title,
        "location": "Douala",
        "sector": "Informatique / IT",
        "contract_type": "CDI",
        "description": "Support informatique et gestion des incidents.",
        "requirements": "Rigueur et sens du service.",
        "required_skills": [
            {"name": "Support informatique", "importance": "core"},
            {"name": "Gestion des incidents", "importance": "preferred"},
        ],
    }, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _cv(client, headers, job_id):
    res = client.post(
        f"/api/jobs/{job_id}/cv", json={"template": "classique"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()


def _apply(client, headers, job_id):
    cv = _cv(client, headers, job_id)
    res = client.post(
        f"/api/applications/jobs/{job_id}/submit",
        json={"cv_document_id": cv["id"]},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_grouped_applications_filters_pagination_and_score(client):
    recruiter = _recruiter(
        client, "recruteur.groupes@orientskill.cm", "Groupes SARL"
    )
    candidate = _candidate(
        client, "candidat.groupes@orientskill.cm", "Gaelle Groupe"
    )
    _profile(client, candidate)
    job1 = _job(client, recruiter, "Support groupe 1")
    job2 = _job(client, recruiter, "Support groupe 2")
    _apply(client, candidate, job1["id"])
    _apply(client, candidate, job2["id"])

    grouped = client.get(
        "/api/recruiter/applications/grouped?page_size=1",
        headers=recruiter,
    )
    assert grouped.status_code == 200, grouped.text
    body = grouped.json()
    assert body["total_groups"] == 2
    assert body["total_applications"] == 2
    assert body["total_new"] == 2
    assert body["has_more"] is True
    assert len(body["items"]) == 1
    group = body["items"][0]
    assert group["total"] == 1
    assert group["new_count"] == 1
    app = group["applications"][0]
    assert app["candidate_name"] == "Gaelle Groupe"
    assert app["candidate_title"] == "Technicien support"
    assert app["status"] == "envoyee"
    assert app["status_label"]
    assert app["is_new"] is True
    assert app["match_score"] is not None and app["match_score"] > 0
    assert app["match_level"] in {"forte", "moyenne", "faible"}

    second = client.get(
        "/api/recruiter/applications/grouped?page_size=1&page=2",
        headers=recruiter,
    ).json()
    assert len(second["items"]) == 1
    assert second["has_more"] is False

    # Filtres : offre, statut, recherche et date.
    by_job = client.get(
        f"/api/recruiter/applications/grouped?job_id={job1['id']}",
        headers=recruiter,
    ).json()
    assert by_job["total_groups"] == 1
    assert by_job["items"][0]["job_id"] == job1["id"]

    by_status = client.get(
        "/api/recruiter/applications/grouped?status=refusee",
        headers=recruiter,
    ).json()
    assert by_status["total_groups"] == 0
    assert by_status["items"] == []

    searched = client.get(
        "/api/recruiter/applications/grouped?q=Gaelle",
        headers=recruiter,
    ).json()
    assert searched["total_groups"] == 2

    today = date.today().isoformat()
    dated = client.get(
        f"/api/recruiter/applications/grouped?date_from={today}&date_to={today}",
        headers=recruiter,
    ).json()
    assert dated["total_groups"] == 2

    bad_status = client.get(
        "/api/recruiter/applications/grouped?status=inconnu",
        headers=recruiter,
    )
    assert bad_status.status_code == 422
    bad_job = client.get(
        "/api/recruiter/applications/grouped?job_id=999999",
        headers=recruiter,
    )
    assert bad_job.status_code == 404

    # Une action autorisée met à jour le statut et le compteur de nouvelles.
    first_app = group["applications"][0]
    moved = client.patch(
        f"/api/recruiter/applications/{first_app['id']}",
        json={"status": "en_attente"},
        headers=recruiter,
    )
    assert moved.status_code == 200, moved.text
    refreshed = client.get(
        f"/api/recruiter/applications/grouped?job_id={group['job_id']}",
        headers=recruiter,
    ).json()
    assert refreshed["items"][0]["new_count"] == 0
    assert refreshed["items"][0]["applications"][0]["status"] == "en_attente"

    # Un autre recruteur ne voit aucune de ces candidatures.
    other = _recruiter(
        client, "recruteur.groupes.autre@orientskill.cm", "Autre SARL"
    )
    empty = client.get(
        "/api/recruiter/applications/grouped", headers=other
    ).json()
    assert empty["items"] == []
    assert empty["total_applications"] == 0

    # Un candidat n'accède pas à la page recruteur.
    forbidden = client.get(
        "/api/recruiter/applications/grouped", headers=candidate
    )
    assert forbidden.status_code == 403
