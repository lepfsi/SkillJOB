"""Modèles de documents (§16, §17) : catalogue étendu, accents, rendus PDF.

Six modèles de CV (classique, ats, moderne, deux_colonnes, elegant,
compact), trois modèles de lettre (classique, moderne, email), et une
couleur d'accent au choix. Le contenu reste exclusivement issu du profil
validé (§47) : un modèle est une mise en page, jamais une autre histoire.
"""

CV_IDS = ("classique", "ats", "moderne", "deux_colonnes", "elegant", "compact")
LETTER_IDS = ("classique", "moderne", "email")


def _job_id(client, headers):
    jobs = client.get("/api/jobs", headers=headers).json()
    return next(j for j in jobs if "Administrateur" in j["title"])["id"]


def test_cv_template_catalog_lists_six(demo_headers, client):
    """Le catalogue expose six modèles, avec colonnes et compatibilité ATS."""
    body = client.get("/api/cv-templates", headers=demo_headers).json()
    assert [t["id"] for t in body] == list(CV_IDS)
    by_id = {t["id"]: t for t in body}
    assert by_id["ats"]["ats_friendly"] is True
    assert by_id["deux_colonnes"]["columns"] == 2
    assert by_id["deux_colonnes"]["ats_friendly"] is False
    assert all(t["description"] for t in body)


def test_letter_template_catalog_lists_three(demo_headers, client):
    body = client.get("/api/letter-templates", headers=demo_headers).json()
    assert [t["id"] for t in body] == list(LETTER_IDS)
    assert all(t["description"] for t in body)


def test_all_cv_templates_generate_and_export_pdf(demo_headers, client):
    """Chaque modèle produit un CV ciblé et un PDF A4 valide (y compris
    la mise en page deux colonnes)."""
    job_id = _job_id(client, demo_headers)
    for template in CV_IDS:
        made = client.post(f"/api/jobs/{job_id}/cv",
                           json={"template": template}, headers=demo_headers)
        assert made.status_code == 200, (template, made.text)
        doc = made.json()
        assert doc["template"] == template
        assert "Steve Demo" in doc["content_markdown"]  # §47 : rien d'inventé

        pdf = client.get(f"/api/documents/{doc['id']}/export?format=pdf",
                         headers=demo_headers)
        assert pdf.status_code == 200, (template, pdf.text)
        assert pdf.headers["content-type"] == "application/pdf"
        assert pdf.content.startswith(b"%PDF")
        assert len(pdf.content) > 1500, template


def test_cv_two_columns_keeps_facts_and_stores_accent(demo_headers, client):
    """Deux colonnes + accent choisi : le markdown reste factuel, l'accent
    est enregistré pour l'export."""
    job_id = _job_id(client, demo_headers)
    made = client.post(f"/api/jobs/{job_id}/cv", json={
        "template": "deux_colonnes", "accent": "bleu",
    }, headers=demo_headers)
    assert made.status_code == 200, made.text
    doc = made.json()
    assert doc["template"] == "deux_colonnes"
    assert doc["accent"] == "bleu"
    # Le markdown ne contient aucune couleur : c'est une mise en page PDF.
    assert "bleu" not in doc["content_markdown"].lower()

    listed = client.get("/api/documents", headers=demo_headers).json()
    mine = next(d for d in listed if d["id"] == doc["id"])
    assert mine["accent"] == "bleu"


def test_unknown_template_and_accent_are_rejected(demo_headers, client):
    job_id = _job_id(client, demo_headers)
    assert client.post(f"/api/jobs/{job_id}/cv",
                       json={"template": "fantaisie"},
                       headers=demo_headers).status_code == 422
    assert client.post(f"/api/jobs/{job_id}/cv",
                       json={"template": "classique", "accent": "fantaisie"},
                       headers=demo_headers).status_code == 422
    assert client.post(f"/api/jobs/{job_id}/cover-letter",
                       json={"template": "fantaisie"},
                       headers=demo_headers).status_code == 422


def test_custom_accent_is_accepted_and_stored(demo_headers, client):
    """Une couleur libre #RRGGBB est valide, y compris pour le modèle ATS."""
    job_id = _job_id(client, demo_headers)
    made = client.post(f"/api/jobs/{job_id}/cv", json={
        "template": "ats", "accent": "#1a9e7c",
    }, headers=demo_headers)
    assert made.status_code == 200, made.text
    doc = made.json()
    assert doc["accent"] == "#1A9E7C"
    pdf = client.get(f"/api/documents/{doc['id']}/export?format=pdf",
                     headers=demo_headers)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"


def test_general_cv_without_job(demo_headers, client):
    """CV GÉNÉRALISTE (aucune offre ciblée) : profil complet, tri par
    preuves, aucune mention de « poste visé » (§47)."""
    made = client.post("/api/cv", json={
        "template": "deux_colonnes", "accent": "bleu",
    }, headers=demo_headers)
    assert made.status_code == 200, made.text
    doc = made.json()
    assert doc["job_id"] is None
    assert doc["template"] == "deux_colonnes"
    assert doc["accent"] == "bleu"
    assert "généraliste" in doc["title"].lower()
    assert "Steve Demo" in doc["content_markdown"]
    assert "poste visé" not in doc["content_markdown"].lower()

    pdf = client.get(f"/api/documents/{doc['id']}/export?format=pdf",
                     headers=demo_headers)
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 1500


def test_general_cv_requires_profile(client):
    """Sans profil validé : refus explicite, jamais de CV vide."""
    r = client.post("/api/auth/register", json={
        "full_name": "Sans Profil", "email": "sprofil.v16@orientskill.cm",
        "password": "motdepasse123", "role": "candidate",
    })
    assert r.status_code == 201, r.text
    login = client.post("/api/auth/login", json={
        "email": "sprofil.v16@orientskill.cm", "password": "motdepasse123",
    })
    headers = {"Authorization": f"Bearer {login.json()['token']}"}
    made = client.post("/api/cv", json={"template": "classique"}, headers=headers)
    assert made.status_code == 400
    assert "profil" in made.json()["detail"].lower()


def test_assistant_proposes_adaptation_texts(demo_headers, client):
    """L'agent propose les textes d'adaptation (accroche + lettre) pour
    l'offre MENTIONNÉE, puis renvoie vers la galerie de modèles."""
    reply = client.post("/api/assistant", json={
        "message": "Adapte mon CV pour l'offre « Administrateur Systèmes et Réseaux »",
        "history": [],
    }, headers=demo_headers)
    assert reply.status_code == 200, reply.text
    body = reply.json()
    text = body["reply"]
    assert "Accroche du CV" in text
    assert "Lettre (ouverture)" in text
    assert "Administrateur Systèmes et Réseaux" in text
    assert any(a.get("type") == "generate_cv" for a in body.get("actions", []))
    hrefs = [l["href"] for l in body.get("links", [])]
    assert any("galerie=cv" in h for h in hrefs)


def test_letter_templates_generate_and_export(demo_headers, client):
    """Trois mises en page de lettre, mêmes faits ; ``email`` se présente
    comme un courriel."""
    job_id = _job_id(client, demo_headers)
    for template in LETTER_IDS:
        made = client.post(f"/api/jobs/{job_id}/cover-letter",
                            json={"template": template, "accent": "vert"},
                            headers=demo_headers)
        assert made.status_code == 200, (template, made.text)
        doc = made.json()
        assert doc["template"] == template
        assert doc["accent"] == "vert"
        assert "Steve Demo" in doc["content_markdown"]
        if template == "email":
            assert "Objet :" in doc["content_markdown"]

        pdf = client.get(f"/api/documents/{doc['id']}/export?format=pdf",
                         headers=demo_headers)
        assert pdf.status_code == 200, (template, pdf.text)
        assert pdf.content.startswith(b"%PDF")
