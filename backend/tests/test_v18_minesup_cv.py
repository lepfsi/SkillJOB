"""V18 : explorateur MINESUP et partage du CV généraliste aux recruteurs.

Deux garanties distinctes sont vérifiées :
- le catalogue MINESUP est hiérarchisé en base et reste éditable par
  l'administration sans que le seed de démarrage écrase ses corrections ;
- un recruteur ne peut lire que le CV généraliste explicitement partagé
  par le talent, jamais un CV ciblé sur une offre ni un autre document.
"""


def _recruiter_headers(client):
    login = client.post("/api/auth/login", json={
        "email": "recruteur@orientskill.cm", "password": "recruteur1234",
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _candidate_id(client, headers):
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    return me.json()["id"]


def test_minesup_catalogue_is_public_and_hierarchical(client):
    response = client.get("/api/institutional/minesup")
    assert response.status_code == 200, response.text
    universities = response.json()
    assert len(universities) >= 6
    university = next(u for u in universities if u["slug"] == "universite-yaounde-1")
    assert university["name"] == "Université de Yaoundé I"
    assert university["city"] == "Yaoundé"
    assert len(university["schools"]) >= 3
    school = university["schools"][0]
    assert school["name"]
    assert school["admission"]
    assert school["eligibility"]


def test_admin_can_create_edit_and_delete_minesup_university(client, admin_headers):
    created = client.post("/api/admin/public-content/minesup/universities", json={
        "name": "Université de démonstration MINESUP",
        "short_name": "UDM",
        "city": "Ebolowa",
        "region": "Sud",
        "description": "Fiche créée par le test de régression.",
        "source_url": "https://www.minesup.gov.cm",
        "sort_order": 999,
    }, headers=admin_headers)
    assert created.status_code == 201, created.text
    university_id = created.json()["id"]

    school = client.post(
        f"/api/admin/public-content/minesup/universities/{university_id}/schools",
        json={
            "name": "École de démonstration",
            "short_name": "ED",
            "kind": "Grande école",
            "admission": "Concours d'entrée",
            "eligibility": "Baccalauréat, selon l'avis annuel.",
            "url": "https://www.minesup.gov.cm",
            "deadline": "Session annuelle",
            "sort_order": 1,
        },
        headers=admin_headers,
    )
    assert school.status_code == 201, school.text
    school_id = school.json()["id"]

    public = client.get("/api/institutional/minesup").json()
    item = next(u for u in public if u["id"] == university_id)
    assert item["schools"][0]["name"] == "École de démonstration"

    updated = client.put(
        f"/api/admin/public-content/minesup/schools/{school_id}",
        json={
            "name": "École de démonstration corrigée",
            "short_name": "EDC",
            "kind": "Institut spécialisé",
            "admission": "Sélection sur dossier",
            "eligibility": "Diplôme requis, selon l'avis annuel.",
            "url": "https://www.minesup.gov.cm",
            "deadline": "Calendrier de l'université",
            "sort_order": 2,
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    public = client.get("/api/institutional/minesup").json()
    item = next(u for u in public if u["id"] == university_id)
    assert item["schools"][0]["name"] == "École de démonstration corrigée"

    # La publication reste une action réservée à l'administration.
    assert client.post(
        "/api/admin/public-content/minesup/universities",
        json={"name": "Interdit"}, headers={},
    ).status_code == 401

    assert client.delete(
        f"/api/admin/public-content/minesup/schools/{school_id}",
        headers=admin_headers,
    ).status_code == 200
    assert client.delete(
        f"/api/admin/public-content/minesup/universities/{university_id}",
        headers=admin_headers,
    ).status_code == 200
    public = client.get("/api/institutional/minesup").json()
    assert all(u["id"] != university_id for u in public)


def test_only_general_cv_can_be_shared_with_recruiters(client, demo_headers):
    candidate_id = _candidate_id(client, demo_headers)
    recruiter_headers = _recruiter_headers(client)

    # État initial propre, même si un autre test a déjà partagé un CV.
    client.put("/api/profile/cv-visibility", json={"visible": False},
               headers=demo_headers)

    made = client.post("/api/cv", json={
        "template": "moderne", "accent": "bleu",
    }, headers=demo_headers)
    assert made.status_code == 200, made.text
    cv = made.json()
    assert cv["job_id"] is None

    shared = client.put("/api/profile/cv-visibility", json={
        "visible": True, "document_id": cv["id"],
    }, headers=demo_headers)
    assert shared.status_code == 200, shared.text
    state = shared.json()
    assert state["visible"] is True
    assert state["document_id"] == cv["id"]
    assert state["document"]["id"] == cv["id"]

    detail = client.get(
        f"/api/recruiter/candidates/{candidate_id}", headers=recruiter_headers,
    )
    assert detail.status_code == 200, detail.text
    card = detail.json()
    assert card["cv"] is not None
    assert card["cv"]["id"] == cv["id"]
    assert card["cv"]["download_url"].endswith(f"/{candidate_id}/cv")
    assert "certifications" in card
    assert card["certification_count"] == len(card["certifications"])
    assert "education" in card and "experiences" in card

    pdf = client.get(
        f"/api/recruiter/candidates/{candidate_id}/cv", headers=recruiter_headers,
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 1500

    # Un CV ciblé sur une offre ne peut pas être partagé par ce canal.
    jobs = client.get("/api/jobs", headers=demo_headers).json()
    targeted = client.post(
        f"/api/jobs/{jobs[0]['id']}/cv",
        json={"template": "classique"},
        headers=demo_headers,
    )
    assert targeted.status_code == 200, targeted.text
    refused = client.put("/api/profile/cv-visibility", json={
        "visible": True, "document_id": targeted.json()["id"],
    }, headers=demo_headers)
    assert refused.status_code == 422, refused.text
    assert "généraliste" in refused.json()["detail"].lower()

    # Le retrait du partage coupe immédiatement l'accès recruteur.
    off = client.put("/api/profile/cv-visibility", json={"visible": False},
                     headers=demo_headers)
    assert off.status_code == 200
    assert off.json()["visible"] is False
    assert client.get(
        f"/api/recruiter/candidates/{candidate_id}/cv", headers=recruiter_headers,
    ).status_code == 404


def test_deleting_shared_cv_disables_recruiter_access(client, demo_headers):
    recruiter_headers = _recruiter_headers(client)
    candidate_id = _candidate_id(client, demo_headers)

    made = client.post("/api/cv", json={"template": "compact"},
                       headers=demo_headers)
    assert made.status_code == 200, made.text
    document = made.json()
    shared = client.put("/api/profile/cv-visibility", json={
        "visible": True, "document_id": document["id"],
    }, headers=demo_headers)
    assert shared.status_code == 200, shared.text

    removed = client.delete(f"/api/documents/{document['id']}",
                            headers=demo_headers)
    assert removed.status_code == 204, removed.text
    state = client.get("/api/profile/cv-visibility", headers=demo_headers).json()
    assert state["visible"] is False
    assert state["document_id"] is None
    assert client.get(
        f"/api/recruiter/candidates/{candidate_id}/cv", headers=recruiter_headers,
    ).status_code == 404
