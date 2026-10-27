"""Documents v17 : mise à jour, suppression, lettre généraliste, CV ATS
généraliste et familles de couleurs (§16, §17, §47).

Chaque point correspond à un retour utilisateur précis :
- le modèle ATS générait une erreur sur le CV généraliste ;
- la page Documents devait permettre de mettre à jour et supprimer ;
- la lettre généraliste (sans offre) a été ajoutée ;
- chaque couleur d'accent doit changer visiblement le PDF.
"""
from app.services import job_media


def _job_id(client, headers):
    jobs = client.get("/api/jobs", headers=headers).json()
    return next(j for j in jobs if "Administrateur" in j["title"])["id"]


def test_general_cv_ats_no_longer_fails(demo_headers, client):
    """Le CV généraliste fonctionne avec le modèle ATS (correctif None)."""
    made = client.post("/api/cv", json={"template": "ats"}, headers=demo_headers)
    assert made.status_code == 200, made.text
    doc = made.json()
    assert doc["template"] == "ats"
    assert "Steve Demo" in doc["content_markdown"]
    assert "poste visé" not in doc["content_markdown"].lower()
    pdf = client.get(f"/api/documents/{doc['id']}/export?format=pdf",
                     headers=demo_headers)
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")


def test_general_letter_without_job(demo_headers, client):
    """Lettre GÉNÉRALISTE : destinataire à compléter, faits du profil only."""
    made = client.post("/api/letter", json={
        "template": "classique", "accent": "bordeaux",
    }, headers=demo_headers)
    assert made.status_code == 200, made.text
    doc = made.json()
    assert doc["job_id"] is None
    assert doc["kind"] == "cover_letter"
    assert "généraliste" in doc["title"].lower()
    assert "[Nom de l'entreprise]" in doc["content_markdown"]
    assert "Steve Demo" in doc["content_markdown"]

    pdf = client.get(f"/api/documents/{doc['id']}/export?format=pdf",
                     headers=demo_headers)
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")
    assert len(pdf.content) > 1500


def test_general_letter_all_templates_export(demo_headers, client):
    for template in ("classique", "moderne", "email"):
        made = client.post("/api/letter", json={"template": template},
                           headers=demo_headers)
        assert made.status_code == 200, (template, made.text)
        doc = made.json()
        assert doc["template"] == template
        if template == "email":
            assert "Objet :" in doc["content_markdown"]
        pdf = client.get(f"/api/documents/{doc['id']}/export?format=pdf",
                         headers=demo_headers)
        assert pdf.status_code == 200, (template, pdf.text)
        assert pdf.content.startswith(b"%PDF")


def test_refresh_document_updates_template_and_content(demo_headers, client):
    """Mettre à jour : régénère depuis le profil validé, même document."""
    made = client.post("/api/cv", json={"template": "compact"}, headers=demo_headers)
    doc = made.json()
    refreshed = client.post(f"/api/documents/{doc['id']}/refresh", json={
        "template": "deux_colonnes", "accent": "orange",
    }, headers=demo_headers)
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["id"] == doc["id"]
    assert body["template"] == "deux_colonnes"
    assert body["accent"] == "orange"
    assert "deux colonnes" in body["title"].lower() or "Deux colonnes" in body["title"]
    assert "Steve Demo" in body["content_markdown"]

    # Mise à jour d'une lettre ciblée vers le modèle courriel.
    job_id = _job_id(client, demo_headers)
    letter = client.post(f"/api/jobs/{job_id}/cover-letter",
                         json={"template": "classique"}, headers=demo_headers).json()
    refreshed = client.post(f"/api/documents/{letter['id']}/refresh",
                            json={"template": "email"}, headers=demo_headers)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["template"] == "email"
    assert "Objet :" in refreshed.json()["content_markdown"]


def test_refresh_rejects_unknown_template(demo_headers, client):
    made = client.post("/api/cv", json={"template": "classique"}, headers=demo_headers)
    doc = made.json()
    r = client.post(f"/api/documents/{doc['id']}/refresh",
                    json={"template": "fantaisie"}, headers=demo_headers)
    assert r.status_code == 422


def test_delete_document(demo_headers, client):
    made = client.post("/api/letter", json={"template": "moderne"}, headers=demo_headers)
    doc = made.json()
    deleted = client.delete(f"/api/documents/{doc['id']}", headers=demo_headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/documents/{doc['id']}",
                      headers=demo_headers).status_code == 404
    listed = client.get("/api/documents", headers=demo_headers).json()
    assert all(d["id"] != doc["id"] for d in listed)


def test_accents_change_the_rendered_pdf(demo_headers, client):
    """Deux accents différents produisent deux PDF différents (familles de
    couleurs distinctes), pour le même contenu."""
    pdfs = {}
    for accent in ("vert", "orange", "bordeaux", "bleu", "ardoise"):
        made = client.post("/api/cv", json={
            "template": "deux_colonnes", "accent": accent,
        }, headers=demo_headers)
        assert made.status_code == 200, (accent, made.text)
        doc = made.json()
        pdf = client.get(f"/api/documents/{doc['id']}/export?format=pdf",
                         headers=demo_headers)
        assert pdf.status_code == 200
        pdfs[accent] = pdf.content
    assert len(set(pdfs.values())) == len(pdfs), "chaque accent doit différer"


def test_assistant_drafts_application_email(demo_headers, client):
    """L'agent rédige le courriel d'accompagnement depuis le profil validé."""
    reply = client.post("/api/assistant", json={
        "message": "Rédige mon mail de candidature pour l'offre « Administrateur Systèmes et Réseaux »",
        "history": [],
    }, headers=demo_headers)
    assert reply.status_code == 200, reply.text
    body = reply.json()
    text = body["reply"]
    assert "Objet :" in text
    assert "Madame, Monsieur," in text
    assert "Steve Demo" in text
    hrefs = [l["href"] for l in body.get("links", [])]
    assert any("galerie=lettre" in h for h in hrefs)


def test_assistant_offers_generalist_documents_and_completion(demo_headers, client):
    """Sans offre : l'agent propose CV et LETTRE généralistes, et liste ce
    qu'il reste à ajouter si des sections du profil sont vides."""
    reply = client.post("/api/assistant", json={
        "message": "Je veux un CV généraliste, et une lettre sans offre",
        "history": [],
    }, headers=demo_headers)
    assert reply.status_code == 200, reply.text
    body = reply.json()
    hrefs = [l["href"] for l in body.get("links", [])]
    assert any(h == "/documents" for h in hrefs)
    assert any("lettre=1" in h for h in hrefs)


# ------------------------------- Photo FACULTATIVE des offres (§51)
import base64  # noqa: E402

PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9Y9Zl1sAAAAASUVORK5CYII="
)
PDF_MIN = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


def _new_admin_job(client, admin_headers, title="Offre photo de test"):
    made = client.post("/api/admin/jobs", json={
        "title": title,
        "company": "Entreprise de test",
        "location": "Douala",
        "sector": "Informatique",
        "contract_type": "CDI",
        "description": "Offre créée pour vérifier la photo facultative.",
        "requirements": "Aucune.",
        "required_skills": [],
        "source_name": "Test",
        "source_url": "https://example.test/offre",
    }, headers=admin_headers)
    assert made.status_code == 201, made.text
    return made.json()


def test_job_photo_is_optional_then_uploadable(client, admin_headers):
    """Publier sans photo reste possible ; l'admin peut en joindre une."""
    job = _new_admin_job(client, admin_headers)
    assert job["photo_url"] is None
    assert client.get(f"/api/jobs/{job['id']}/photo").status_code == 404

    upload = client.post(
        f"/api/admin/jobs/{job['id']}/photo",
        files={"file": ("photo.png", PNG_1PX, "image/png")},
        headers=admin_headers,
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["photo_url"] == f"/api/jobs/{job['id']}/photo"

    photo = client.get(f"/api/jobs/{job['id']}/photo")
    assert photo.status_code == 200
    assert photo.headers["content-type"] == "image/png"
    assert photo.content == PNG_1PX

    detail = client.get(f"/api/jobs/{job['id']}").json()["job"]
    assert detail["photo_url"] == f"/api/jobs/{job['id']}/photo"

    bad = client.post(
        f"/api/admin/jobs/{job['id']}/photo",
        files={"file": ("notes.txt", b"texte", "text/plain")},
        headers=admin_headers,
    )
    assert bad.status_code == 400

    assert client.delete(f"/api/admin/jobs/{job['id']}/photo",
                         headers=admin_headers).status_code == 200
    assert client.get(f"/api/jobs/{job['id']}/photo").status_code == 404

    client.delete(f"/api/admin/jobs/{job['id']}", headers=admin_headers)


def test_missing_job_photo_falls_back_to_domain_visual(client, admin_headers):
    """Un fichier perdu après redéploiement ne casse pas la fiche d'offre."""
    job = _new_admin_job(client, admin_headers)
    upload = client.post(
        f"/api/admin/jobs/{job['id']}/photo",
        files={"file": ("photo.png", PNG_1PX, "image/png")},
        headers=admin_headers,
    )
    assert upload.status_code == 200, upload.text

    # Simule le stockage local éphémère : la base garde photo_path, le
    # fichier n'existe plus sur le disque.
    for path in job_media.JOBS_DIR.glob(f"offre-{job['id']}.*"):
        path.unlink()

    res = client.get(f"/api/jobs/{job['id']}/photo")
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("image/svg+xml")
    assert "Informatique" in res.text
    assert job["title"] in res.text

    client.delete(f"/api/admin/jobs/{job['id']}", headers=admin_headers)


def test_recruiter_job_photo_is_optional(client):
    """Le recruteur publie avec ou sans photo (zone facultative)."""
    login = client.post("/api/auth/login", json={
        "email": "recruteur@orientskill.cm", "password": "recruteur1234",
    })
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['token']}"}

    made = client.post("/api/recruiter/jobs", json={
        "title": "Offre recruteur avec photo facultative",
        "company": "Entreprise test",
        "location": "Yaoundé",
        "sector": "Services",
        "contract_type": "CDD",
        "description": "Test.",
        "requirements": "Test.",
        "required_skills": [],
        "source_url": "https://example.test/recruteur",
    }, headers=headers)
    assert made.status_code == 201, made.text
    job = made.json()
    assert job["photo_url"] is None

    upload = client.post(
        f"/api/recruiter/jobs/{job['id']}/photo",
        files={"file": ("visuel.png", PNG_1PX, "image/png")},
        headers=headers,
    )
    assert upload.status_code == 200, upload.text
    assert client.get(f"/api/jobs/{job['id']}/photo").status_code == 200

    client.delete(f"/api/recruiter/jobs/{job['id']}", headers=headers)


# ------------------------- PDF joints aux programmes publics (admin)
def test_program_pdf_attachment_is_optional_and_downloadable(client, admin_headers):
    made = client.post("/api/admin/public-content/institutional", json={
        "category": "minfopra",
        "subcategory": "concours_direct",
        "title": "Programme test · PDF joint",
        "description": "Fiche de test pour le dépôt de PDF.",
        "eligibility": "Test.",
        "url": None,
        "deadline": "Test",
    }, headers=admin_headers)
    assert made.status_code == 201, made.text
    pid = made.json()["id"]

    # Sans document : la fiche publique n'annonce aucun PDF.
    public = client.get("/api/institutional?category=minfopra").json()
    item = next(i for i in public if i["id"] == pid)
    assert item["documents"] == []

    upload = client.post(
        f"/api/admin/public-content/institutional/{pid}/documents",
        files={"file": ("avis-officiel.pdf", PDF_MIN, "application/pdf")},
        data={"label": "Avis officiel (test)"},
        headers=admin_headers,
    )
    assert upload.status_code == 200, upload.text
    docs = upload.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["label"] == "Avis officiel (test)"

    public = client.get("/api/institutional?category=minfopra").json()
    item = next(i for i in public if i["id"] == pid)
    assert item["documents"][0]["url"] == docs[0]["url"]

    dl = client.get(item["documents"][0]["url"])
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/pdf"
    assert dl.content == PDF_MIN

    bad = client.post(
        f"/api/admin/public-content/institutional/{pid}/documents",
        files={"file": ("notes.txt", b"texte", "text/plain")},
        headers=admin_headers,
    )
    assert bad.status_code == 400

    assert client.delete(
        f"/api/admin/public-content/institutional/{pid}/documents/{docs[0]['key']}",
        headers=admin_headers,
    ).status_code == 200
    assert client.get(item["documents"][0]["url"]).status_code == 404

    client.delete(f"/api/admin/public-content/institutional/{pid}",
                  headers=admin_headers)


def test_referential_sync_recreates_missing_offer_with_title(client):
    """Une fiche du référentiel supprimée est recréée avec son titre :
    l'insertion ne doit jamais laisser ``title`` vide."""
    from app.database import SessionLocal
    from app.main import sync_institutional_offers
    from app import models

    db = SessionLocal()
    try:
        row = (
            db.query(models.InstitutionalOffer)
            .filter(models.InstitutionalOffer.source == "referentiel")
            .first()
        )
        assert row is not None
        title = row.title
    finally:
        db.close()

    db = SessionLocal()
    try:
        row = (
            db.query(models.InstitutionalOffer)
            .filter(models.InstitutionalOffer.title == title)
            .first()
        )
        db.delete(row)
        db.commit()
        sync_institutional_offers(db)
        restored = (
            db.query(models.InstitutionalOffer)
            .filter(models.InstitutionalOffer.title == title)
            .first()
        )
        assert restored is not None
        assert restored.title == title
    finally:
        db.close()


def test_admin_programs_and_documents_survive_referential_sync(client, admin_headers):
    """Le référentiel ne doit jamais effacer un ajout de l'administration,
    ni les PDF joints à une fiche existante."""
    from app.database import SessionLocal
    from app.main import sync_institutional_offers
    from app import models

    made = client.post("/api/admin/public-content/institutional", json={
        "category": "minefop",
        "subcategory": "fne",
        "title": "Programme ajouté par l'administration (test)",
        "description": "Doit survivre à la synchronisation.",
        "eligibility": "",
        "url": None,
        "deadline": None,
    }, headers=admin_headers)
    pid = made.json()["id"]

    # PDF joint à une fiche issue du référentiel.
    listing = client.get("/api/admin/public-content/institutional",
                         headers=admin_headers).json()
    ref = next(i for i in listing if i["source"] == "referentiel")
    upload = client.post(
        f"/api/admin/public-content/institutional/{ref['id']}/documents",
        files={"file": ("document.pdf", PDF_MIN, "application/pdf")},
        data={"label": "Document de test"},
        headers=admin_headers,
    )
    assert upload.status_code == 200, upload.text
    key = upload.json()["key"]

    db = SessionLocal()
    try:
        sync_institutional_offers(db)
        assert db.get(models.InstitutionalOffer, pid) is not None
        refreshed = db.get(models.InstitutionalOffer, ref["id"])
        assert any(d.get("key") == key for d in (refreshed.documents or []))
    finally:
        db.close()

    client.delete(
        f"/api/admin/public-content/institutional/{ref['id']}/documents/{key}",
        headers=admin_headers,
    )
    client.delete(f"/api/admin/public-content/institutional/{pid}",
                  headers=admin_headers)

