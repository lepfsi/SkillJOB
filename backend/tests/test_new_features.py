"""Tests des fonctionnalités V1.2 : MFA, genre, modèles de CV,
vérification de profil, photos, marché hebdo, espace recruteur."""
import io
import time


def _png_bytes() -> bytes:
    """PNG factice (1x1) valide pour les tests d'upload."""
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
        "53de0000000c4944415408d763f8cfc0f01f0005050202a5cd1a33000000004"
        "9454e44ae426082"
    )


def test_register_with_gender(client):
    response = client.post("/api/auth/register", json={
        "email": "genre.test@example.cm", "password": "pass1234",
        "full_name": "Marie NGO", "gender": "femme",
    })
    assert response.status_code == 201
    assert response.json()["user"]["gender"] == "femme"


def test_mfa_full_flow(client, admin_headers):
    login = client.post("/api/auth/login", json={
        "email": "genre.test@example.cm", "password": "pass1234",
    })
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    # Setup : secret + URI otpauth
    setup = client.post("/api/auth/mfa/setup", headers=headers).json()
    assert setup["secret"]
    assert setup["otpauth_uri"].startswith("otpauth://totp/")

    # Code erroné refusé
    bad = client.post("/api/auth/mfa/enable", json={"code": "000000"},
                      headers=headers)
    assert bad.status_code == 400

    # Code correct (calculé avec le même moteur RFC 6238)
    from app.services import mfa as mfa_service
    code = mfa_service.totp_at(setup["secret"], int(time.time()) // 30)
    enabled = client.post("/api/auth/mfa/enable", json={"code": code},
                          headers=headers)
    assert enabled.status_code == 200, enabled.text
    codes = enabled.json()["recovery_codes"]
    assert len(codes) == 8

    # Login : le MFA est exigé, pas de jeton de session direct
    login2 = client.post("/api/auth/login", json={
        "email": "genre.test@example.cm", "password": "pass1234",
    }).json()
    assert login2["mfa_required"] is True
    assert login2.get("token") is None

    # Mauvais code refusé
    bad2 = client.post("/api/auth/login/mfa", json={
        "mfa_token": login2["mfa_token"], "code": "000000",
    })
    assert bad2.status_code == 401

    # Code de récupération accepté puis consommé
    ok1 = client.post("/api/auth/login/mfa", json={
        "mfa_token": login2["mfa_token"], "code": codes[0],
    })
    assert ok1.status_code == 200 and ok1.json()["token"]
    ok2 = client.post("/api/auth/login/mfa", json={
        "mfa_token": login2["mfa_token"], "code": codes[0],
    })
    assert ok2.status_code == 401

    # Réinitialisation par l'administrateur (cas extrême) :
    # on cible l'utilisateur genre.test par son email, pas par un id figé.
    users = client.get("/api/admin/users", headers=admin_headers).json()
    target_id = next(u["id"] for u in users if u["email"] == "genre.test@example.cm")
    response = client.delete(f"/api/admin/users/{target_id}/mfa",
                             headers=admin_headers)
    assert response.status_code == 200
    login3 = client.post("/api/auth/login", json={
        "email": "genre.test@example.cm", "password": "pass1234",
    }).json()
    assert login3.get("token")  # plus de MFA : accès direct


def test_letter_gender_no_parentheses(demo_headers, client):
    """Plus de « (se) » : la lettre s'accorde avec le genre enregistré."""
    doc = client.post("/api/jobs/1/cover-letter", headers=demo_headers).json()
    assert "(-se)" not in doc["content_markdown"]
    assert "(se)" not in doc["content_markdown"]
    # Le compte démo (Steve, homme) reçoit la formulation masculine
    assert "Je serais heureux d" in doc["content_markdown"]


# ---------------------------------------------------- Modèles de CV

def test_cv_templates_catalog(demo_headers, client):
    response = client.get("/api/cv-templates", headers=demo_headers)
    assert response.status_code == 200
    ids = [t["id"] for t in response.json()]
    assert {"classique", "ats", "moderne"} <= set(ids)
    assert any(t["ats_friendly"] for t in response.json())


def test_cv_generated_with_ats_template(demo_headers, client):
    doc = client.post("/api/jobs/1/cv", json={"template": "ats"},
                      headers=demo_headers).json()
    assert doc["template"] == "ats"
    assert "Core Skills" in doc["content_markdown"]
    pdf = client.get(f"/api/documents/{doc['id']}/export?format=pdf",
                     headers=demo_headers)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


def test_cv_generated_with_moderne_template(demo_headers, client):
    doc = client.post("/api/jobs/1/cv", json={"template": "moderne"},
                      headers=demo_headers).json()
    assert doc["template"] == "moderne"
    pdf = client.get(f"/api/documents/{doc['id']}/export?format=pdf",
                     headers=demo_headers)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


def test_cv_template_inconnu_refuse(demo_headers, client):
    response = client.post("/api/jobs/1/cv", json={"template": "fancy"},
                           headers=demo_headers)
    assert response.status_code == 422


# ------------------------------------------------- Vérification profil

def test_verification_flow(demo_headers, admin_headers, client):
    files = {"file": ("cni.png", io.BytesIO(_png_bytes()), "image/png")}
    response = client.post("/api/profile/verification/request",
                           files=files, headers=demo_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "pending"

    status = client.get("/api/profile/verification", headers=demo_headers)
    assert status.json()["status"] == "pending"

    pending = client.get("/api/admin/verifications", headers=admin_headers).json()
    assert any(v["user_id"] == 1 for v in pending)

    approve = client.post("/api/admin/verifications/1/approve",
                          headers=admin_headers)
    assert approve.status_code == 200
    status = client.get("/api/profile/verification", headers=demo_headers)
    assert status.json()["status"] == "verified"
    me = client.get("/api/auth/me", headers=demo_headers).json()
    assert me["verification_status"] == "verified"

    # Le document d'identité est accessible à l'admin uniquement
    doc = client.get("/api/admin/verifications/1/document",
                     headers=admin_headers)
    assert doc.status_code == 200


def test_admin_users_view(admin_headers, client):
    response = client.get("/api/admin/users", headers=admin_headers)
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 2
    fields = {"id", "email", "full_name", "role", "mfa_enabled",
              "verification_status", "has_profile", "applications_count"}
    assert fields <= set(users[0].keys())


# ---------------------------------------------------- Marché hebdo

def test_dashboard_weekly_indicators(demo_headers, client):
    body = client.get("/api/dashboard", headers=demo_headers).json()
    week = body["market_week"]
    assert "offers_in_period" in week
    assert "period_label" in week
    if body["market_trends"]:
        assert all("count" in t for t in body["market_trends"])


# ---------------------------------------------------- Espace recruteur

def _recruiter_headers(client, email: str = "recruteur@tgc.cm") -> dict:
    reg = client.post("/api/auth/register/recruiter", json={
        "email": email, "password": "pass1234",
        "full_name": "Directeur RH", "gender": "homme",
        "company_name": "Tracabilite Test CM",
        "company_sector": "Informatique / IT",
        "company_description": "Entreprise de services numeriques a Douala.",
        "company_location": "Douala",
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def test_recruiter_space(client, demo_headers):
    rheaders = _recruiter_headers(client)

    company = client.get("/api/recruiter/company", headers=rheaders).json()
    assert company["name"] == "Tracabilite Test CM"

    job = client.post("/api/recruiter/jobs", json={
        "title": "Technicien reseau", "company": "Tracabilite Test CM",
        "location": "Douala", "sector": "Informatique / IT",
        "contract_type": "CDI", "description": "Poste terrain.",
        "required_skills": [{"name": "TCP/IP", "importance": "core"},
                            {"name": "Fortinet", "importance": "preferred"}],
    }, headers=rheaders)
    assert job.status_code == 201, job.text
    job_id = job.json()["id"]

    # L'offre publique porte le branding de l'entreprise
    detail = client.get(f"/api/jobs/{job_id}", headers=rheaders).json()
    assert detail["job"]["company_branding"]["name"] == "Tracabilite Test CM"

    # Talent search explicable
    candidates = client.get(
        "/api/recruiter/candidates?skills=TCP/IP,Fortinet",
        headers=rheaders).json()
    assert candidates
    top = candidates[0]
    assert top["match"]["score"] > 0
    assert "covered" in top["match"] and "missing" in top["match"]

    # Le candidat démo postule ; le recruteur voit la candidature
    app_resp = client.post("/api/applications", json={"job_id": job_id},
                            headers=demo_headers)
    assert app_resp.status_code == 201
    received = client.get("/api/recruiter/applications", headers=rheaders).json()
    assert any(a["job_id"] == job_id for a in received)

    # Un candidat n'a pas accès à l'espace recruteur
    forbidden = client.get("/api/recruiter/company", headers=demo_headers)
    assert forbidden.status_code == 403


def test_recruiter_job_crud(client):
    rh = _recruiter_headers(client, email="recruteur2@tgc.cm")
    job = client.post("/api/recruiter/jobs", json={
        "title": "Admin sys", "company": "Tracabilite Test CM",
        "location": "Douala", "sector": "IT", "contract_type": "CDD",
        "required_skills": [],
    }, headers=rh)
    assert job.status_code == 201
    jid = job.json()["id"]
    updated = client.put(f"/api/recruiter/jobs/{jid}", json={
        "title": "Administrateur systemes",
    }, headers=rh)
    assert updated.status_code == 200
    assert updated.json()["title"] == "Administrateur systemes"
    assert client.delete(f"/api/recruiter/jobs/{jid}",
                         headers=rh).status_code == 200


def test_photo_upload(demo_headers, client):
    files = {"file": ("photo.png", io.BytesIO(_png_bytes()), "image/png")}
    response = client.post("/api/profile/photo", files=files,
                           headers=demo_headers)
    assert response.status_code == 200
    assert response.json()["photo_path"]

    photo = client.get("/api/profile/photo", headers=demo_headers)
    assert photo.status_code == 200

    # Le CV PDF généré ensuite embarque la photo sans erreur
    doc = client.post("/api/jobs/1/cv", headers=demo_headers).json()
    pdf = client.get(f"/api/documents/{doc['id']}/export?format=pdf",
                     headers=demo_headers)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"
