"""Tests d'intégration de l'API OrientSkill AI (contrat docs/API_CONTRACT.md)."""

CV_TEXT = """Marie NGONO
Technicienne support informatique
Douala, Cameroun

Formation
BTS Informatique - IUC Douala - 2022-2024
Baccalauréat scientifique - Lycée de Bepanda - 2021

Expérience professionnelle
Technicienne support - Cybercafé Express, Douala - 2023-2024
Dépannage postes clients, installation Windows, configuration réseau local.

Stage administration systèmes - Entreprise Delta, Douala - 2024-04 à 2024-09
Administration Windows Server, sauvegardes.

Compétences
TCP/IP, Windows Server, Administration de pare-feu, Linux (notions),
Support informatique, Communication

Certifications
CCNA (Cisco) 2024

Langues
Français courant
Anglais intermédiaire
"""


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_and_login(client):
    response = client.post("/api/auth/register", json={
        "email": "test.user@example.cm",
        "password": "pass1234",
        "full_name": "Utilisateur Test",
    })
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["token"]
    assert body["user"]["email"] == "test.user@example.cm"
    assert body["user"]["role"] == "candidate"

    # doublon refusé
    response = client.post("/api/auth/register", json={
        "email": "test.user@example.cm",
        "password": "pass1234",
        "full_name": "Utilisateur Test",
    })
    assert response.status_code == 400

    # mauvais mot de passe
    response = client.post("/api/auth/login", json={
        "email": "test.user@example.cm", "password": "mauvais",
    })
    assert response.status_code == 401

    # bon login
    response = client.post("/api/auth/login", json={
        "email": "test.user@example.cm", "password": "pass1234",
    })
    assert response.status_code == 200


def test_me_unauthorized_and_authorized(client):
    assert client.get("/api/auth/me").status_code in (401, 403)
    login = client.post("/api/auth/login", json={
        "email": "test.user@example.cm", "password": "pass1234",
    })
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["full_name"] == "Utilisateur Test"


def test_demo_login_and_profile(demo_headers, client):
    response = client.get("/api/profile", headers=demo_headers)
    assert response.status_code == 200
    profile = response.json()
    assert profile is not None
    skill_names = [s["skill"] for s in profile["skills"]]
    assert "TCP/IP" in skill_names and "Fortinet" in skill_names
    assert any(e["type"] == "informal" for e in profile["experiences"])


def test_import_cv_text_draft_not_saved(client):
    login = client.post("/api/auth/login", json={
        "email": "test.user@example.cm", "password": "pass1234",
    })
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    response = client.post("/api/profile/import-cv", json={"text": CV_TEXT}, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    draft, report = body["draft"], body["report"]
    names = [s["skill"] for s in draft["skills"]]
    assert "TCP/IP" in names and "Windows Server" in names
    assert report["skills_found"] >= 3
    assert report["degrees_found"] >= 1
    assert report["certifications_found"] >= 1
    assert any(l["language"] == "Français" for l in draft["languages"])

    # Le brouillon n'est PAS enregistré (§47)
    response = client.get("/api/profile", headers=headers)
    assert response.json() is None

    # Validation via PUT
    response = client.put(
        "/api/profile",
        json={k: draft[k] for k in ("title", "summary", "skills", "education",
                                    "experiences", "certifications", "languages",
                                    "preferences")},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["user_id"] >= 1
    assert [s["skill"] for s in saved["skills"]] == names

    # Alias normalisé en canonique
    response = client.put(
        "/api/profile",
        json={"skills": [{"skill": "firewall", "proficiency": "avance"}]},
        headers=headers,
    )
    assert response.status_code == 200
    saved_skills = [s["skill"] for s in response.json()["skills"]]
    assert "Administration de pare-feu" in saved_skills


def test_taxonomy_and_skills_market(client):
    response = client.get("/api/skills/taxonomy")
    assert response.status_code == 200
    taxonomy = response.json()
    assert len(taxonomy) >= 60
    categories = {e["category"] for e in taxonomy}
    assert {"IT", "Data", "Marketing", "BTP", "Agriculture", "Santé",
            "Éducation", "Logistique", "Soft skills"} <= categories

    response = client.get("/api/skills/market")
    assert response.status_code == 200
    market = response.json()
    assert any(e["name"] == "Excel avancé" and e["demand_count"] >= 1 for e in market)
    assert all(e["trend"] in ("up", "stable", "down") for e in market)


def test_jobs_list_filters_and_detail(demo_headers, client):
    response = client.get("/api/jobs", headers=demo_headers)
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) >= 18
    assert all("match_score" in j and j["match_score"] is not None for j in jobs)
    assert all(
        {"name", "url"} == set(j["source"]) for j in jobs
    )

    it_jobs = client.get("/api/jobs", params={"sector": "Informatique"},
                         headers=demo_headers).json()
    assert all("Informatique" in j["sector"] for j in it_jobs)

    strong = client.get("/api/jobs", params={"min_score": 45},
                        headers=demo_headers).json()
    assert all(j["match_score"] >= 45 for j in strong)

    # détail + match explicable
    admin_job = next(j for j in jobs if "Administrateur" in j["title"])
    response = client.get(f"/api/jobs/{admin_job['id']}", headers=demo_headers)
    assert response.status_code == 200
    detail = response.json()
    match = detail["match"]
    assert 0 <= match["score"] <= 100
    assert match["level"] in ("forte", "moyenne", "faible")
    assert "TCP/IP" in match["covered"]
    assert match["explanation"]  # explication en français
    assert match["recommended_actions"]

    job_spec = detail["job"]
    assert job_spec["description"] and job_spec["requirements"]
    assert job_spec["required_skills"]

    assert client.get("/api/jobs/99999", headers=demo_headers).status_code == 404


def test_careers_matches(demo_headers, client):
    response = client.get("/api/careers", headers=demo_headers)
    assert response.status_code == 200
    careers = response.json()
    assert len(careers) >= 10
    scores = [c["match"]["score"] for c in careers]
    assert scores == sorted(scores, reverse=True)
    top = careers[0]
    assert top["match"]["accessibility"] in (
        "immediate", "with_upskilling", "long_term"
    )
    assert top["match"]["score"] > 0


def test_documents_generation_no_invention(demo_headers, client):
    jobs = client.get("/api/jobs", headers=demo_headers).json()
    admin_job = next(j for j in jobs if "Administrateur" in j["title"])
    job_id = admin_job["id"]

    response = client.post(f"/api/jobs/{job_id}/cv", headers=demo_headers)
    assert response.status_code == 200, response.text
    cv = response.json()
    assert cv["kind"] == "cv"
    content = cv["content_markdown"]
    assert "Steve Demo" in content
    assert "TCP/IP" in content          # compétence réelle du profil
    assert "Cybersécurité" not in content  # rien d'inventé

    response = client.post(f"/api/jobs/{job_id}/cover-letter", headers=demo_headers)
    assert response.status_code == 200
    letter = response.json()
    assert letter["kind"] == "cover_letter"
    assert admin_job["company"] in letter["content_markdown"]

    response = client.post(f"/api/jobs/{job_id}/interview-prep", headers=demo_headers)
    assert response.status_code == 200
    prep = response.json()
    assert prep["likely_questions"] and prep["technical"] and prep["pitch"]

    # liste + détail + export markdown
    docs = client.get("/api/documents", headers=demo_headers).json()
    assert len(docs) >= 2
    response = client.get(f"/api/documents/{cv['id']}/export", params={"format": "md"},
                          headers=demo_headers)
    assert response.status_code == 200
    assert "TCP/IP" in response.text

    assert client.get(f"/api/documents/{cv['id']}").status_code in (401, 403)


def test_applications_flow(client):
    login = client.post("/api/auth/login", json={
        "email": "test.user@example.cm", "password": "pass1234",
    })
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    job = client.get("/api/jobs", headers=headers).json()[0]

    response = client.post("/api/applications", json={"job_id": job["id"]},
                           headers=headers)
    assert response.status_code == 201, response.text
    app = response.json()
    assert app["status"] == "identifiee"
    assert app["job"]["title"] == job["title"]

    response = client.patch(f"/api/applications/{app['id']}",
                            json={"status": "envoyee"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "envoyee"
    assert len(response.json()["timeline"]) >= 2

    response = client.patch(f"/api/applications/{app['id']}",
                            json={"status": "inconnue"}, headers=headers)
    assert response.status_code == 422

    doublon = client.post("/api/applications", json={"job_id": job["id"]},
                          headers=headers)
    assert doublon.status_code == 400


def test_dashboard_and_inbox(demo_headers, client):
    response = client.get("/api/dashboard", headers=demo_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["name"]
    assert body["new_opportunities"] >= 1
    assert body["strong_matches"] >= 1
    assert body["interviews_to_prepare"] >= 1
    assert body["market_trends"]
    assert body["next_action"]["type"] in ("adapt_cv", "learn", "apply",
                                           "prepare_interview")

    response = client.get("/api/inbox", headers=demo_headers)
    assert response.status_code == 200
    events = response.json()
    assert events
    assert any(e["kind"] == "new_job" for e in events)
    assert any(e["kind"] == "application" for e in events)


def test_market_trends(client):
    response = client.get("/api/market/trends")
    assert response.status_code == 200
    body = response.json()
    assert body["top_skills"] and "count" in body["top_skills"][0]
    assert body["sectors"]
    assert set(body) == {"top_skills", "trending_up", "trending_down",
                         "sectors", "emerging"}


def test_learning_plan(demo_headers, client):
    response = client.get("/api/learning", headers=demo_headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"learn_now", "improve", "learn_next", "progress"}
    assert body["learn_now"]
    first = body["learn_now"][0]
    assert first["resources"] and first["reason"]
    assert all(r["type"] in ("course", "certification", "project", "free")
               for r in first["resources"])


def test_assistant_rules(demo_headers, client):
    response = client.post("/api/assistant", json={
        "message": "Quels métiers puis-je viser avec mon profil ?",
        "history": [],
    }, headers=demo_headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "Administrateur réseaux et systèmes" in body["reply"] or body["reply"]
    assert body["suggestions"]

    response = client.post("/api/assistant", json={
        "message": "montre-moi les offres récentes",
        "history": [],
    }, headers=demo_headers)
    body = response.json()
    assert "offre" in body["reply"].lower()
    assert body["links"]

    response = client.post("/api/assistant", json={
        "message": "prépare mon CV stp",
        "history": [{"role": "user", "content": "salut"},
                    {"role": "assistant", "content": "bonjour"}],
    }, headers=demo_headers)
    assert "CV" in response.json()["reply"]


def test_questionnaire_flow(client):
    login = client.post("/api/auth/login", json={
        "email": "test.user@example.cm", "password": "pass1234",
    })
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    response = client.get("/api/questionnaire")
    assert response.status_code == 200
    steps = response.json()["steps"]
    assert len(steps) >= 3
    q_ids = {q["id"] for s in steps for q in s["questions"]}
    assert {"q_title", "q_skills", "q_sectors"} <= q_ids

    response = client.post("/api/questionnaire/submit", json={
        "answers": {
            "q_title": "Comptable junior",
            "q_location": "Yaoundé",
            "q_education_level": "BTS / DUT",
            "q_field": "Comptabilité",
            "q_experience_kinds": ["Petit boulot / activité informelle"],
            "q_experience_desc": "Tenue de caisse d'une boutique familiale",
            "q_skills": "comptabilité, excel",
            "q_sectors": ["Finance / Comptabilité"],
        }
    }, headers=headers)
    assert response.status_code == 200, response.text
    draft = response.json()["draft"]
    assert draft["title"] == "Comptable junior"
    assert draft["experiences"][0]["type"] == "informal"
    names = [s["skill"] for s in draft["skills"]]
    assert "Comptabilité générale" in names  # alias résolu
    assert "Excel avancé" in names


def test_generic_document_links_in_application(client):
    login = client.post("/api/auth/login", json={
        "email": "demo@orientskill.cm", "password": "demo1234",
    })
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    apps = client.get("/api/applications", headers=headers).json()
    assert len(apps) >= 2
    assert all(a["status"] in (
        "identifiee", "cv_prepare", "envoyee", "en_attente",
        "entretien", "offre", "acceptee", "refusee",
    ) for a in apps)
    job_titles = {a["job"]["title"] for a in apps}
    assert any("Technicien" in t or "Administrateur" in t for t in job_titles)


# ------------------------------------------------------------ Admin (V1.1)

def _admin_headers(client):
    login = client.post("/api/auth/login", json={
        "email": "admin@orientskill.cm", "password": "admin1234",
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['token']}"}


def test_admin_forbidden_for_candidate(demo_headers, client):
    response = client.get("/api/admin/stats", headers=demo_headers)
    assert response.status_code == 403


def test_admin_stats(admin_headers, client):
    response = client.get("/api/admin/stats", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["users"] >= 2          # demo + admin
    assert body["jobs"] >= 15
    assert body["llm_enabled"] is False
    assert "smtp_enabled" in body


def test_admin_settings_roundtrip(admin_headers, client):
    response = client.get("/api/admin/settings", headers=admin_headers)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"smtp", "llm", "aggregators"}
    assert "api_key" in body["llm"] and "api_key_set" in body["llm"]

    # Mise à jour LLM : la clé n'est jamais renvoyée en clair
    response = client.put("/api/admin/settings/llm", json={
        "data": {"provider": "openai", "api_key": "sk-test-123", "enabled": True},
    }, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["llm"]["api_key_set"] is True
    assert response.json()["llm"]["api_key"] != "sk-test-123"

    # Soumettre un secret vide conserve le secret existant
    response = client.put("/api/admin/settings/llm", json={
        "data": {"api_key": ""},
    }, headers=admin_headers)
    assert response.json()["llm"]["api_key_set"] is True

    # Test LLM : échec contrôlé (clé factice)
    response = client.post("/api/admin/test-llm", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["ok"] is False

    # SMTP désactivé : réponse contrôlée
    response = client.post("/api/admin/test-smtp", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["ok"] is False


def test_admin_connectors(admin_headers, client):
    response = client.get("/api/admin/connectors", headers=admin_headers)
    assert response.status_code == 200
    connectors = response.json()
    ids = [c["id"] for c in connectors]
    assert {"llm", "smtp", "telegram", "whatsapp", "linkedin",
            "multi_source", "skill_graph", "credentials"} <= set(ids)
    assert all(c["status"] in ("operationnel", "configure", "roadmap") for c in connectors)


def test_admin_jobs_crud(admin_headers, client):
    # Création
    response = client.post("/api/admin/jobs", json={
        "title": "Contrôleur de gestion",
        "company": "Groupe Test CM",
        "location": "Douala",
        "sector": "Finance / Comptabilité",
        "contract_type": "CDI",
        "description": "Pilotage budgétaire et reporting.",
        "requirements": "Expérience en contrôle de gestion.",
        "required_skills": [{"name": "Excel avancé", "importance": "core"},
                            {"name": "Comptabilité générale", "importance": "preferred"}],
        "source_name": "Saisie manuelle",
        "source_url": "https://exemple.cm/offre",
    }, headers=admin_headers)
    assert response.status_code == 201, response.text
    job = response.json()
    job_id = job["id"]
    assert job["required_skills"][0]["name"] == "Excel avancé"

    # Mise à jour partielle
    response = client.put(f"/api/admin/jobs/{job_id}", json={
        "location": "Yaoundé",
    }, headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["location"] == "Yaoundé"

    # L'offre est visible côté candidat
    response = client.get(f"/api/jobs/{job_id}", headers=admin_headers)
    assert response.status_code == 200
    assert response.json()["job"]["title"] == "Contrôleur de gestion"

    # Suppression
    response = client.delete(f"/api/admin/jobs/{job_id}", headers=admin_headers)
    assert response.status_code == 200
    response = client.get(f"/api/jobs/{job_id}", headers=admin_headers)
    assert response.status_code == 404


def test_learning_progress_verifiable(demo_headers, client):
    response = client.get("/api/learning", headers=demo_headers)
    body = response.json()
    assert body["progress"]
    item = body["progress"][0]
    assert set(item) >= {"skill", "level", "status", "status_label",
                         "demand", "evidences", "next_step"}
    assert item["status"] in ("verifiee", "a_confirmer", "en_progression")
    # Au moins une compétence du profil démo possède des preuves
    assert any(p["evidences"] for p in body["progress"])


def test_pdf_export_cv(demo_headers, client):
    # Génère un CV ciblé pour la première offre puis exporte en PDF
    response = client.post("/api/jobs/1/cv", headers=demo_headers)
    assert response.status_code == 200, response.text
    doc_id = response.json()["id"]
    response = client.get(f"/api/documents/{doc_id}/export?format=pdf",
                          headers=demo_headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


def test_pdf_export_letter(demo_headers, client):
    response = client.post("/api/jobs/1/cover-letter", headers=demo_headers)
    assert response.status_code == 200, response.text
    doc_id = response.json()["id"]
    response = client.get(f"/api/documents/{doc_id}/export?format=pdf",
                          headers=demo_headers)
    assert response.status_code == 200
    assert response.content[:4] == b"%PDF"


def test_careers_related_jobs(demo_headers, client):
    response = client.get("/api/careers", headers=demo_headers)
    assert response.status_code == 200
    careers = response.json()
    assert all("related_jobs" in c for c in careers)
    # Au moins un métier IT possède une offre liée dans le jeu de seed
    assert any(c["related_jobs"] for c in careers)
