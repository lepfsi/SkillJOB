"""Tests V2.1 : inscription recruteur via le bon endpoint côté client
(simulé backend), questionnaire « sans diplôme » (débrouillardise),
et linéarisation des erreurs 422."""

def _recruiter_headers(client, email="recruteur.v21@tgc.cm", recruiter_type="company"):
    reg = client.post("/api/auth/register/recruiter", json={
        "email": email, "password": "pass1234",
        "full_name": "" if recruiter_type != "independent" else "Jean Recruteur",
        "recruiter_type": recruiter_type,
        "company_name": "V2 Entreprise CM",
        "company_sector": "Commerce / Vente",
        "company_description": "Test.",
        "company_location": "Douala",
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def test_recruiter_company_registration_flow(client):
    """Le flux envoyé par le frontend (full_name vide pour une entreprise)
    doit fonctionner sur l'endpoint recruteur et créer un vrai recruteur."""
    rheaders = _recruiter_headers(client)
    me = client.get("/api/auth/me", headers=rheaders).json()
    assert me["role"] == "recruiter"
    assert me["full_name"] == "V2 Entreprise CM"  # nom = structure
    company = client.get("/api/recruiter/company", headers=rheaders).json()
    assert company["name"] == "V2 Entreprise CM"


def test_candidate_endpoint_rejects_empty_name_with_readable_error(client):
    """422 avec detail = liste : le client doit linéariser (le bug de la
    page blanche venait du rendu React de ce tableau d'objets)."""
    response = client.post("/api/auth/register", json={
        "email": "vide@exemple.cm", "password": "pass1234", "full_name": "",
    })
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)  # format FastAPI que le frontend linéarise


SANS_DIPLÔME = "Compétences acquises sur le terrain (sans diplôme)"


def test_questionnaire_sans_diplome_domain(client):
    """« Sans diplôme » : pas de filière/établissement/certifications
    demandées ; le domaine de débrouillardise structure le profil et
    nourrit la détection de compétences."""
    login = client.post("/api/auth/login", json={
        "email": "demo@orientskill.cm", "password": "demo1234",
    })
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    # Le questionnaire expose bien la question de domaine
    steps = client.get("/api/questionnaire").json()["steps"]
    formation = next(s for s in steps if s["id"] == "formation")
    ids = {q["id"] for q in formation["questions"]}
    assert "q_domain" in ids

    response = client.post("/api/questionnaire/submit", json={
        "answers": {
            "q_title": "",
            "q_education_level": SANS_DIPLÔME,
            "q_domain": "Plomberie et installation sanitaire dans les "
                        "quartiers : réparation de fuites, pose de robinetterie, "
                        "petits travaux de manœuvre sur chantier.",
            "q_skills": "",
            "q_experience_desc": "Plombier de quartier depuis 5 ans.",
        },
    }, headers=headers)
    assert response.status_code == 200
    draft = response.json()["draft"]

    # Aucune formation ni certification imposée
    assert draft["education"] == []
    assert draft["certifications"] == []

    # Le domaine devient le titre et le résumé de débrouillardise
    assert draft["title"]
    assert "plomberie" in draft["title"].lower()
    assert "terrain" in draft["summary"].lower()

    # Les compétences réelles sont déduites du domaine décrit
    names = [s["skill"] for s in draft["skills"]]
    assert any("plomberie" in n.lower() for n in names)


def test_questionnaire_with_diplome_still_academic(client):
    """Avec un diplôme : filière et établissement restent demandés
    (vérifié via le draft) et fonctionnent comme avant."""
    login = client.post("/api/auth/login", json={
        "email": "demo@orientskill.cm", "password": "demo1234",
    })
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    response = client.post("/api/questionnaire/submit", json={
        "answers": {
            "q_education_level": "BTS / DUT",
            "q_field": "Systèmes et réseaux",
            "q_institution": "IUC Douala",
            "q_certifications": "CCNA, Cisco, 2024",
        },
    }, headers=headers)
    assert response.status_code == 200
    draft = response.json()["draft"]
    assert len(draft["education"]) == 1
    assert draft["education"][0]["field"] == "Systèmes et réseaux"
    assert len(draft["certifications"]) == 1
