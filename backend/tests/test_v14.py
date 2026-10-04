"""Tests V1.4 : parseur d'offres IA, entrepreneuriat interactif
(business plan, guidance), notifications multi-canaux, inscription
recruteur par type, filtres talents, refonte programmes publics."""
import io


def _recruiter_headers(client, email="recruteur.v14@tgc.cm", recruiter_type="company"):
    reg = client.post("/api/auth/register/recruiter", json={
        "email": email, "password": "pass1234",
        "full_name": "" if recruiter_type != "independent" else "Jean Recruteur",
        "recruiter_type": recruiter_type,
        "company_name": "Parse Test CM",
        "company_sector": "Informatique / IT",
        "company_description": "Entreprise test.",
        "company_location": "Douala",
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['token']}"}, reg.json()["user"]


def _demo_headers(client):
    login = client.post("/api/auth/login", json={
        "email": "demo@orientskill.cm", "password": "demo1234",
    })
    return {"Authorization": f"Bearer {login.json()['token']}"}


# ------------------------------------------------- Parseur d'offres IA

def test_job_parser_extracts_structure(client):
    rheaders, _ = _recruiter_headers(client)
    response = client.post("/api/jobs/parse", json={
        "description": (
            "Nous recrutons un technicien support informatique chez "
            "Numérik Services à Douala. CDI. Compétences : Windows Server, "
            "TCP/IP, support utilisateurs. Salaire : 250000 FCFA."
        ),
    }, headers=rheaders)
    assert response.status_code == 200
    draft = response.json()
    assert draft["title"].lower().startswith("technicien support")
    assert draft["company"] == "Numérik Services"
    assert draft["location"] == "Douala"
    assert draft["sector"] == "Informatique / IT"
    assert draft["contract_type"] == "CDI"
    names = [s["name"] for s in draft["required_skills"]]
    assert "Windows Server" in names and "TCP/IP" in names
    assert "warning" in draft

    # Le brouillon est publiable par le recruteur après vérification
    created = client.post("/recruiter/jobs".replace("/recruiter", "/api/recruiter"), json={
        "title": draft["title"], "company": draft["company"],
        "location": draft["location"], "sector": draft["sector"],
        "contract_type": draft["contract_type"],
        "description": draft["description"],
        "required_skills": draft["required_skills"],
    }, headers=rheaders)
    assert created.status_code == 201


def test_job_parser_forbidden_for_candidates(client):
    dheaders = _demo_headers(client)
    response = client.post("/api/jobs/parse", json={
        "description": "Recrute un technicien support informatique à Douala, CDI, Windows Server.",
    }, headers=dheaders)
    assert response.status_code == 403


# ------------------------------------------ Entrepreneuriat interactif

def test_business_plan_generation(client):
    dheaders = _demo_headers(client)
    response = client.post("/api/entrepreneurship/business-plan", json={
        "activity": "Installation et maintenance informatique pour PME",
        "target": "Petites entreprises de Douala",
        "capital": "350 000 FCFA",
        "location": "Douala",
    }, headers=dheaders)
    assert response.status_code == 200, response.text
    doc = response.json()
    assert doc["kind"] == "business_plan"
    content = doc["content_markdown"]
    # Aucune invention : le contenu reprend les données fournies et le profil
    assert "Installation et maintenance informatique" in content
    assert "350 000 FCFA" in content
    assert "Petites entreprises de Douala" in content
    assert "Windows Server" in content  # compétence réelle du profil démo
    assert "garantie" in content.lower() or "Aucune promesse" in content


def test_entrepreneur_guidance_personalized(client):
    dheaders = _demo_headers(client)
    response = client.get("/api/entrepreneurship/guidance", headers=dheaders)
    assert response.status_code == 200
    body = response.json()
    # Le profil démo (IT réseau) doit recevoir la guidance « Numérique »
    assert body["category_label"] == "Numérique"
    assert body["opportunities"] and body["steps"]
    assert "profil" in body["introduction"].lower()


def test_entrepreneurship_financing_institutions(client):
    response = client.get("/api/entrepreneurship")
    data = response.json()
    names = " ".join(i["name"] for i in data["financing_institutions"])
    assert "Fonds National de l'Emploi" in names
    assert "microfinance" in names.lower()
    assert any("Banques" in i["name"] for i in data["financing_institutions"])


# ------------------------------------------------------ Notifications

def test_notification_prefs_roundtrip(client):
    dheaders = _demo_headers(client)
    current = client.get("/api/profile/notifications", headers=dheaders)
    assert current.status_code == 200
    assert "email_enabled" in current.json()

    updated = client.put("/api/profile/notifications", json={
        "email_enabled": True,
        "email": "steve.demo@example.cm",
        "telegram_enabled": True,
        "telegram_username": "@steve_demo",
    }, headers=dheaders)
    assert updated.status_code == 200
    body = updated.json()
    assert body["email"] == "steve.demo@example.cm"
    assert body["telegram_enabled"] is True

    # Test d'envoi : échec propre, détails explicites (services non configurés)
    results = client.post("/api/profile/notifications/test", headers=dheaders)
    assert results.status_code == 200
    channels = {r["channel"]: r for r in results.json()}
    assert channels["email"]["ok"] is False
    assert "administrateur" in channels["email"]["detail"]


# --------------------------------------- Inscription recruteur par type

def test_recruiter_company_type_no_personal_fields(client):
    rheaders, user = _recruiter_headers(client, email="corp@tgc.cm", recruiter_type="company")
    # Le nom affiché est celui de l'entreprise, pas d'un individu
    assert user["full_name"] == "Parse Test CM"
    assert user["gender"] is None

    company = client.get("/api/recruiter/company", headers=rheaders).json()
    assert company["name"] == "Parse Test CM"


def test_recruiter_agency_type(client):
    rheaders, user = _recruiter_headers(client, email="agence@tgc.cm", recruiter_type="agency")
    assert user["full_name"] == "Parse Test CM"
    company = client.get("/api/recruiter/company", headers=rheaders).json()
    assert "Cabinet RH" in company["description"]


def test_recruiter_independent_type_full_fields(client):
    rheaders, user = _recruiter_headers(
        client, email="independant@tgc.cm", recruiter_type="independent")
    assert user["full_name"] == "Jean Recruteur"


# -------------------------------------------------- Filtres talents

def test_recruiter_candidate_filters(client):
    rheaders, _ = _recruiter_headers(client, email="filtres@tgc.cm")
    # Filtre par compétences
    by_skills = client.get(
        "/api/recruiter/candidates?skills=Windows Server", headers=rheaders).json()
    assert by_skills and all("Windows Server" in c["match"]["covered"] for c in by_skills)

    # Filtre par recherche texte
    by_text = client.get(
        "/api/recruiter/candidates?q=technicien", headers=rheaders).json()
    assert any(c["user_id"] == 1 for c in by_text)

    # Filtre par région (le compte démo est à Douala / Littoral dans le seed
    # seulement via profil ; le filtre s'appuie sur user.region)
    by_region = client.get(
        "/api/recruiter/candidates?region=Inexistante", headers=rheaders).json()
    assert all(c["user_id"] != 1 for c in by_region) or by_region == []


def test_geo_arrondissements_extended(client):
    response = client.get("/api/geo")
    data = response.json()
    total = sum(
        len(d["arrondissements"]) for r in data["regions"] for d in r["departments"]
    )
    assert total >= 300  # couverture nationale quasi complète


def test_assistant_parses_offer_for_recruiter(client):
    rheaders, _ = _recruiter_headers(client, email="assistant@tgc.cm")
    response = client.post("/api/assistant", json={
        "message": (
            "Publie une offre : nous recrutons un technicien support "
            "informatique chez Numérik Services à Douala. CDI. "
            "Compétences : Windows Server, TCP/IP."
        ),
        "history": [],
    }, headers=rheaders)
    assert response.status_code == 200
    body = response.json()
    assert "Poste" in body["reply"]
    assert "technicien support" in body["reply"].lower()
    assert any(l["href"].startswith("/recruiter/jobs") for l in body["links"])


def test_assistant_offer_intent_not_for_candidates(client):
    dheaders = _demo_headers(client)
    response = client.post("/api/assistant", json={
        "message": "publie une offre de technicien",
        "history": [],
    }, headers=dheaders)
    body = response.json()
    # Pas de brouillon d'offre pour un candidat : réponse normale
    assert "Poste :" not in body["reply"]
