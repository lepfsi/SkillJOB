"""Tests V3 : vérification avec motif de rejet, dashboard institutionnel
(agrégats anonymisés), Skill Graph, CRUD contenus publics."""
import io


def _png_bytes() -> bytes:
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
        "53de0000000c4944415408d763f8cfc0f01f0005050202a5cd1a33000000004"
        "9454e44ae426082"
    )


def _admin_headers(client):
    login = client.post("/api/auth/login", json={
        "email": "admin@orientskill.cm", "password": "admin1234",
    })
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _demo_headers(client):
    login = client.post("/api/auth/login", json={
        "email": "demo@orientskill.cm", "password": "demo1234",
    })
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _fresh_candidate(client, email="verif.v3@example.cm"):
    """Candidat vierge : les tests de vérification ne dépendent pas de
    l'état du compte démo (déjà vérifié par d'autres tests)."""
    reg = client.post("/api/auth/register", json={
        "email": email, "password": "pass1234",
        "full_name": "Freshe Vérification", "gender": "femme",
    })
    assert reg.status_code == 201
    token = reg.json()["token"]
    user_id = reg.json()["user"]["id"]
    return {"Authorization": f"Bearer {token}"}, user_id


# ------------------------------------- Vérification : motif obligatoire

def test_verification_reject_requires_reason(client):
    dheaders, uid = _fresh_candidate(client)
    aheaders = _admin_headers(client)

    files = {"file": ("cni.png", io.BytesIO(_png_bytes()), "image/png")}
    assert client.post("/api/profile/verification/request",
                      files=files, headers=dheaders).status_code == 200

    # Refus SANS motif : 422 avec message clair
    no_reason = client.post(f"/api/admin/verifications/{uid}/reject",
                            json={"note": ""}, headers=aheaders)
    assert no_reason.status_code == 422
    assert "Motif du rejet requis" in no_reason.json()["detail"]

    # Refus AVEC motif : le candidat voit la raison exacte
    reason = "Le nom sur la pièce ne correspond pas au nom du profil."
    ok = client.post(f"/api/admin/verifications/{uid}/reject",
                     json={"note": reason}, headers=aheaders)
    assert ok.status_code == 200
    status = client.get("/api/profile/verification", headers=dheaders).json()
    assert status["status"] == "rejected"
    assert status["note"] == reason


def test_verification_review_shows_profile_for_comparison(client):
    """Le bordereau d'exposition inclut le profil pour la comparaison."""
    dheaders, uid = _fresh_candidate(client, email="verif.v3b@example.cm")
    # Un profil riche facilite la comparaison admin ↔ pièce
    client.put("/api/profile", json={
        "title": "Technicienne maintenance",
        "education": [{"degree": "BTS Électrotechnique", "institution": "IUC",
                        "field": "Électrotechnique", "start_year": 2020, "end_year": 2022}],
    }, headers=dheaders)

    aheaders = _admin_headers(client)
    files = {"file": ("cni.png", io.BytesIO(_png_bytes()), "image/png")}
    client.post("/api/profile/verification/request", files=files, headers=dheaders)

    items = client.get("/api/admin/verifications", headers=aheaders).json()
    item = next(i for i in items if i["user_id"] == uid)
    assert item["profile"] is not None
    assert item["profile"]["title"] == "Technicienne maintenance"
    assert item["profile"]["education"]       # diplômes pour comparaison

    # Approbation avec note optionnelle
    approve = client.post(f"/api/admin/verifications/{uid}/approve",
                          json={"note": "Pièce conforme au profil."}, headers=aheaders)
    assert approve.status_code == 200
    assert client.get("/api/profile/verification", headers=dheaders).json()[
        "status"] == "verified"


# ---------------------------------------- Dashboard institutionnel (§39)

def test_institutional_dashboard_anonymized(client):
    aheaders = _admin_headers(client)
    body = client.get("/admin/institutional-dashboard".replace("/admin", "/api/admin"),
                      headers=aheaders).json()
    assert body["candidates"] >= 1 and body["jobs"] >= 15
    assert any("skill" in g for g in body["top_demand"])
    # Les écarts croisent demande du marché et offre de compétences
    for gap in body["skill_gaps"]:
        assert gap["demand"] > 0 and "ratio" in gap
    assert body["regions"]  # répartition géographique
    # Aucune donnée individuelle : pas d'email ni de nom
    assert "email" not in str(body)
    assert "full_name" not in str(body)


def test_institutional_dashboard_forbidden_for_candidates(client):
    dheaders = _demo_headers(client)
    response = client.get("/api/admin/institutional-dashboard", headers=dheaders)
    assert response.status_code == 403


# ------------------------------------------------ Skill Graph (§41)

def test_skill_graph_entry_points_and_node(client):
    aheaders = _admin_headers(client)
    body = client.get("/api/admin/skill-graph", headers=aheaders).json()
    assert body["entry_points"]
    assert all("demand" in e and "supply" in e for e in body["entry_points"])

    node = client.get("/api/admin/skill-graph?skill=TCP/IP", headers=aheaders).json()
    assert node["node"]["skill"] == "TCP/IP"
    assert node["careers"]            # métiers exigeant TCP/IP
    assert node["jobs_count"] >= 1
    assert node["talents_count"] >= 1  # le profil démo possède TCP/IP
    assert node["talents_by_level"]
    assert node["related_skills"]      # co-occurrences = trajectoires


# ------------------------------------- CRUD contenus publics (admin)

def test_public_content_crud(client):
    aheaders = _admin_headers(client)

    # Programmes publics
    created = client.post("/api/admin/public-content/institutional", json={
        "category": "concours", "subcategory": "sante",
        "title": "Concours infirmiers de test",
        "description": "Programme de test.",
        "eligibility": "Bac scientifique",
    }, headers=aheaders)
    assert created.status_code == 201, created.text
    pid = created.json()["id"]

    listing = client.get("/api/admin/public-content/institutional", headers=aheaders).json()
    assert any(i["id"] == pid for i in listing)

    updated = client.put(f"/api/admin/public-content/institutional/{pid}", json={
        "category": "concours", "subcategory": "sante",
        "title": "Concours infirmiers (mis à jour)",
        "description": "Programme de test.", "eligibility": "Bac",
        "url": None, "deadline": "Session de juin",
    }, headers=aheaders)
    assert updated.status_code == 200

    # Visible côté public
    public = client.get("/api/institutional?category=concours").json()
    assert any("mis à jour" in i["title"] for i in public)

    assert client.delete(f"/api/admin/public-content/institutional/{pid}",
                         headers=aheaders).status_code == 200

    # Entrepreneuriat
    created = client.post("/api/admin/public-content/entrepreneurship", json={
        "kind": "concours", "title": "Challenge de test",
        "description": "Dotation de test.", "organizer": "Ministère",
        "sectors": ["Numérique"],
    }, headers=aheaders)
    assert created.status_code == 201
    eid = created.json()["id"]
    public = client.get("/api/entrepreneurship").json()
    assert any(i["id"] == eid for i in public["resources"])
    assert client.delete(f"/api/admin/public-content/entrepreneurship/{eid}",
                         headers=aheaders).status_code == 200
