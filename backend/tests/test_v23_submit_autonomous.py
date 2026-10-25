"""Soumission de candidature, mode autonome, spécialités IT et briefing.

Le bouton « Soumettre ma candidature » envoie réellement les documents au
recruteur (canal plateforme) ou trace l'envoi externe. Le mode autonome
prépare les documents automatiquement. Le briefing de l'agent est
contextuel et actionnable.
"""


def _candidate(client, email="candidat.submit@orientskill.cm"):
    reg = client.post("/api/auth/register", json={
        "email": email, "password": "pass1234", "full_name": "Paula Submit",
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def _profile_with_cv(client, headers, job_id):
    """Profil minimal + CV ciblé pour l'offre donnée."""
    client.put("/api/profile", json={
        "title": "Technicienne support",
        "summary": "Profil de test.",
        "skills": [
            {"skill": "Support informatique", "proficiency": "avance"},
            {"skill": "Gestion des incidents", "proficiency": "intermediaire"},
        ],
    }, headers=headers)
    cv = client.post(f"/api/jobs/{job_id}/cv", json={"template": "classique"},
                     headers=headers)
    assert cv.status_code == 200, cv.text
    return cv.json()


def test_it_specialties_are_synced(client):
    """Les spécialités IT granulaires sont ajoutées au référentiel."""
    tree = client.get("/api/domains").json()
    info = next(d for d in tree if d["name"] == "Informatique et numérique")
    names = {s["name"] for s in info["specialties"]}
    assert {"Administration systèmes", "Réseaux et télécommunications",
            "Intelligence artificielle", "Data science et analytics",
            "Ingénierie des données", "Génie logiciel",
            "Analyse programme et besoins"} <= names
    # Les spécialités historiques restent (compatibilité ascendante).
    assert "Réseaux et systèmes" in names
    assert "Data science et intelligence artificielle" in names


def test_submit_application_platform_channel(client, demo_headers, admin_headers):
    """La soumission envoie le CV au recruteur et trace l'envoi."""
    # Offre publiée par un VRAI recruteur : canal plateforme.
    reg = client.post("/api/auth/register/recruiter", json={
        "email": "recruteur.submit@orientskill.cm", "password": "pass1234",
        "recruiter_type": "company",
        "company_name": "Express Union",
        "company_sector": "Finance",
        "company_description": "Test canal plateforme.",
        "company_location": "Douala",
    })
    assert reg.status_code == 201, reg.text
    rh = {"Authorization": f"Bearer {reg.json()['token']}"}
    job = client.post("/api/recruiter/jobs", json={
        "title": "Technicien support IT", "company": "Express Union",
        "location": "Douala", "sector": "IT", "contract_type": "CDI",
        "required_skills": [],
    }, headers=rh).json()

    headers = _candidate(client)
    cv = _profile_with_cv(client, headers, job["id"])

    # Soumettre la candidature avec le CV
    submit = client.post(f"/api/applications/jobs/{job['id']}/submit", json={
        "cv_document_id": cv["id"],
        "cover_note": "Bonjour, je suis très intéressée par ce poste.",
    }, headers=headers)
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["status"] == "envoyee"
    assert body["submitted_at"] is not None
    assert body["apply_channel"] == "platform"
    assert body["cover_note"].startswith("Bonjour")

    # Le recruteur de l'entreprise est notifié dans sa messagerie interne.
    threads = client.get("/api/messages", headers=rh).json()
    assert any("Nouvelle candidature" in (t.get("last_body") or "") for t in threads), threads
    thread = next(t for t in threads
                  if "Nouvelle candidature" in (t.get("last_body") or ""))
    full = client.get(f"/api/messages/{thread['other_user_id']}", headers=rh).json()
    text = " ".join(m.get("body", "") for m in full.get("messages", []))
    assert job["title"] in text
    assert "Paula Submit" in text

    # Double soumission refusée
    resubmit = client.post(f"/api/applications/jobs/{job['id']}/submit", json={
        "cv_document_id": cv["id"],
    }, headers=headers)
    assert resubmit.status_code == 400

    # CV d'un autre utilisateur refusé
    other = _candidate(client, "candidat.other@orientskill.cm")
    bad = client.post(f"/api/applications/jobs/{job['id']}/submit", json={
        "cv_document_id": cv["id"],
    }, headers=other)
    assert bad.status_code == 422

    # L'admin voit la candidature envoyée
    listing = client.get("/api/admin/applications?status=envoyee",
                         headers=admin_headers)
    assert listing.status_code == 200, listing.text
    rows = listing.json()
    assert any(
        r["candidate_email"] == "candidat.submit@orientskill.cm"
        and r["job_id"] == job["id"]
        and r["document_count"] >= 1
        for r in rows
    ), rows


def test_submit_application_external_channel(client, admin_headers):
    """Une offre externe trace l'envoi et affiche les instructions."""
    headers = _candidate(client, "candidat.externe@orientskill.cm")
    # Offre externe créée par l'admin SANS compte recruteur rattaché.
    job = client.post("/api/admin/jobs", json={
        "title": "Technicien fibre optique (externe)",
        "company": "CamTel",
        "location": "Yaoundé",
        "sector": "Télécoms",
        "contract_type": "CDD",
        "description": "Installation et maintenance fibre.",
        "requirements": "Expérience terrain.",
        "source_name": "Site CamTel",
        "source_url": "https://camtel.cm/carrieres/offre-123",
        "required_skills": [
            {"name": "Support informatique", "importance": "core"},
        ],
    }, headers=admin_headers).json()

    cv = _profile_with_cv(client, headers, job["id"])
    submit = client.post(f"/api/applications/jobs/{job['id']}/submit", json={
        "cv_document_id": cv["id"],
    }, headers=headers)
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["apply_channel"] == "external"
    assert body["submitted_at"] is not None
    # Les instructions externes sont exposées au candidat.
    assert body["apply_url"] == "https://camtel.cm/carrieres/offre-123"


def test_agent_briefing_is_actionable(client, demo_headers):
    """Le briefing contient des données réelles, pas du texte statique."""
    dash = client.get("/api/dashboard", headers=demo_headers).json()
    assert dash["ai_briefing"]
    assert dash["ai_label"]
    # Le briefing n'est PAS le texte générique d'avant.
    assert "Chaque grande carrière" not in dash["ai_briefing"]
    assert "transforme votre potentiel" not in dash["ai_briefing"]


def test_autonomous_mode_prepares_cv(client, admin_headers):
    """En mode autonome, l'agent prépare un CV pour la meilleure offre sans CV."""
    headers = _candidate(client, "candidat.autonome@orientskill.cm")
    # Offre dédiée avec les compétences exactes du candidat : correspondance
    # forte garantie quel que soit l'état de la base des autres tests.
    job = client.post("/api/admin/jobs", json={
        "title": "Support IT niveau 2 (autonome)",
        "company": "Autonome SARL",
        "location": "Douala",
        "sector": "Informatique / IT",
        "contract_type": "CDI",
        "description": "Support technique avancé.",
        "requirements": "Autonomie et rigueur.",
        "source_name": "Saisie manuelle",
        "source_url": "https://autonome.cm/offre",
        "required_skills": [
            {"name": "Support informatique", "importance": "core"},
            {"name": "Gestion des incidents", "importance": "core"},
            {"name": "Windows Server", "importance": "core"},
            {"name": "Relation client", "importance": "preferred"},
        ],
    }, headers=admin_headers).json()

    client.put("/api/profile", json={
        "title": "Technicienne support",
        "summary": "Profil de test autonome.",
        "skills": [
            {"skill": "Support informatique", "proficiency": "avance"},
            {"skill": "Gestion des incidents", "proficiency": "avance"},
            {"skill": "Windows Server", "proficiency": "avance"},
            {"skill": "Relation client", "proficiency": "avance"},
        ],
    }, headers=headers)

    # Activer le mode autonome
    put = client.put("/api/agent/mode", json={"mode": "autonome"}, headers=headers)
    assert put.status_code == 200, put.text

    # Visiter le dashboard : l'agent doit préparer un CV automatiquement
    dash = client.get("/api/dashboard", headers=headers).json()
    assert dash["autonomous_prepared"] is not None, dash["ai_briefing"]
    prepared = dash["autonomous_prepared"]
    assert prepared["job_id"]
    assert prepared["job_title"]
    assert "préparé" in prepared["message"].lower()

    # Une seconde visite ne re-prépare pas le MÊME CV : le premier reste
    # unique dans la bibliothèque, même si l'agent enchaîne sur une autre
    # offre forte dépourvue de CV.
    dash2 = client.get("/api/dashboard", headers=headers).json()
    docs = client.get("/api/documents", headers=headers).json()
    targeted_cvs = [
        d for d in docs
        if d["kind"] == "cv" and d["job_id"] == prepared["job_id"]
    ]
    assert len(targeted_cvs) == 1, "le même CV ne doit pas être régénéré"

    # Le CV auto-préparé existe dans la bibliothèque
    auto_cvs = [d for d in docs if "ciblé" in d["title"].lower()]
    assert len(auto_cvs) >= 1

    # La candidature est marquée « cv_prepare »
    apps = client.get("/api/applications", headers=headers).json()
    assert any(a["status"] == "cv_prepare" for a in apps)


def test_autonomous_mode_can_be_disabled(client, demo_headers):
    """Le mode autonome se désactive et ne prépare plus rien."""
    headers = _candidate(client, "candidat.noautonome@orientskill.cm")
    client.put("/api/profile", json={
        "title": "Développeuse",
        "summary": "Profil de test.",
        "skills": [{"skill": "JavaScript", "proficiency": "intermediaire"}],
    }, headers=headers)

    client.put("/api/agent/mode", json={"mode": "autonome"}, headers=headers)
    client.get("/api/dashboard", headers=headers)

    # Repasser en mode préparation : plus de préparation auto
    client.put("/api/agent/mode", json={"mode": "preparation"}, headers=headers)
    dash = client.get("/api/dashboard", headers=headers).json()
    assert dash["autonomous_prepared"] is None
