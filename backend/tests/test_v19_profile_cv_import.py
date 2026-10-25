"""V19 : import d'un CV de la bibliothèque dans le profil.

Le CV choisi doit appartenir au candidat. L'import produit toujours un
brouillon : le profil maître n'est pas modifié avant la validation humaine.
"""

from app import models
from app.database import SessionLocal


def _recruiter_headers(client):
    login = client.post("/api/auth/login", json={
        "email": "recruteur@orientskill.cm", "password": "recruteur1234",
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _current_profile(client, headers):
    response = client.get("/api/profile", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_import_cv_from_library_restores_snapshot_without_saving(client, demo_headers):
    before = _current_profile(client, demo_headers)

    made = client.post("/api/cv", json={
        "template": "moderne", "accent": "bleu",
    }, headers=demo_headers)
    assert made.status_code == 200, made.text
    document = made.json()

    imported = client.post("/api/profile/import-cv/library", json={
        "document_id": document["id"],
    }, headers=demo_headers)
    assert imported.status_code == 200, imported.text
    body = imported.json()
    draft = body["draft"]
    report = body["report"]

    assert draft["user_id"] == before["user_id"]
    assert draft["title"] == before["title"]
    assert [s["skill"] for s in draft["skills"]] == [
        s["skill"] for s in before["skills"]
    ]
    assert len(draft["experiences"]) == len(before["experiences"])
    assert report["skills_found"] == len(before["skills"])
    assert report["experiences_found"] == len(before["experiences"])

    # Un import reste un brouillon : le profil maître est inchangé.
    after = _current_profile(client, demo_headers)
    assert after == before


def test_library_import_rejects_foreign_document_and_non_cv(client, demo_headers):
    made = client.post("/api/cv", json={"template": "classique"},
                       headers=demo_headers)
    assert made.status_code == 200, made.text
    document = made.json()

    foreign = client.post("/api/profile/import-cv/library", json={
        "document_id": document["id"],
    }, headers=_recruiter_headers(client))
    assert foreign.status_code == 404, foreign.text

    letter = client.post("/api/letter", json={"template": "classique"},
                         headers=demo_headers)
    assert letter.status_code == 200, letter.text
    refused = client.post("/api/profile/import-cv/library", json={
        "document_id": letter.json()["id"],
    }, headers=demo_headers)
    assert refused.status_code == 422, refused.text
    assert "cv" in refused.json()["detail"].lower()


def test_library_import_reads_structured_markdown_for_older_cv(client, demo_headers):
    me = client.get("/api/auth/me", headers=demo_headers).json()
    markdown = (
        "# Steve Demo\n"
        "**Technicien support informatique** · Douala, Cameroun\n"
        "Contact : demo@orientskill.cm\n"
        "Disponibilité : Immédiate\n"
        "\n"
        "## Résumé\n"
        "Technicien support orienté réseaux et assistance utilisateurs.\n"
        "\n"
        "## Compétences\n"
        "- **TCP/IP** (intermédiaire)\n"
        "- **Windows Server** (avancé)\n"
        "- **Support informatique** (avancé)\n"
        "\n"
        "## Expérience\n"
        "### Technicien support · Entreprise A\n"
        "*Expérience professionnelle · 2022-01 à 2024-06*\n"
        "Assistance des utilisateurs et administration du réseau local.\n"
        "Compétences mobilisées : TCP/IP, Support informatique\n"
        "\n"
        "### Stage réseau · Entreprise B\n"
        "*Stage / Apprentissage · 2021-06 à 2021-09*\n"
        "Configuration de routeurs.\n"
        "Compétences mobilisées : TCP/IP\n"
        "\n"
        "## Projets\n"
        "### Lab réseau\n"
        "Mise en place de VLAN et de règles de pare-feu.\n"
        "Compétences mobilisées : TCP/IP, Windows Server\n"
        "\n"
        "## Formation\n"
        "- BTS Informatique · Institut Universitaire de la Côte (Systèmes et réseaux) · 2020 à 2022\n"
        "\n"
        "## Certifications\n"
        "- CCNA · Cisco Networking Academy (2024)\n"
        "\n"
        "## Langues\n"
        "Français (courant), Anglais (intermediaire)\n"
    )
    db = SessionLocal()
    try:
        old = models.Document(
            user_id=me["id"], kind="cv", title="Ancien CV importé",
            content_markdown=markdown, source_profile=None,
        )
        db.add(old)
        db.commit()
        db.refresh(old)
        old_id = old.id
    finally:
        db.close()

    imported = client.post("/api/profile/import-cv/library", json={
        "document_id": old_id,
    }, headers=demo_headers)
    assert imported.status_code == 200, imported.text
    body = imported.json()
    draft, report = body["draft"], body["report"]
    assert draft["title"] == "Technicien support informatique"
    assert draft["location"] == "Douala, Cameroun"
    assert draft["availability"] == "Immédiate"
    assert [s["skill"] for s in draft["skills"]] == [
        "TCP/IP", "Windows Server", "Support informatique",
    ]
    assert len(draft["experiences"]) == 2
    assert draft["experiences"][0]["type"] == "formal"
    assert draft["experiences"][1]["type"] == "apprenticeship"
    assert draft["experiences"][0]["start_date"] == "2022-01"
    assert draft["experiences"][0]["end_date"] == "2024-06"
    assert len(draft["projects"]) == 1
    assert draft["projects"][0]["name"] == "Lab réseau"
    assert len(draft["education"]) == 1
    assert draft["education"][0]["institution"] == "Institut Universitaire de la Côte"
    assert draft["education"][0]["field"] == "Systèmes et réseaux"
    assert draft["education"][0]["start_year"] == 2020
    assert draft["education"][0]["end_year"] == 2022
    assert len(draft["certifications"]) == 1
    assert draft["certifications"][0]["name"] == "CCNA"
    assert draft["certifications"][0]["issuer"] == "Cisco Networking Academy"
    assert [l["language"] for l in draft["languages"]] == ["Français", "Anglais"]
    assert report["skills_found"] == 3
    assert report["experiences_found"] == 2
    assert report["degrees_found"] == 1

    # Le document de test est retiré pour ne pas polluer les autres suites.
    client.delete(f"/api/documents/{old_id}", headers=demo_headers)


def test_generic_extraction_keeps_location_out_of_languages():
    from app.services.cv_extractor import extract_profile

    text = (
        "Steve Demo\n"
        "Technicien support informatique\n"
        "Douala, Cameroun\n\n"
        "Experiences\n"
        "Technicien support - Cybercafe NK, Douala\n"
        "2023-01 a 2024-06\n"
        "Depannage de postes clients et configuration du reseau local.\n\n"
        "Formation\n"
        "BTS Informatique - Institut Universitaire de la Cote, Douala\n"
        "2022 a 2024\n"
    )
    draft, _report = extract_profile(text)
    assert draft["languages"] == []
    assert len(draft["experiences"]) == 1
    assert draft["experiences"][0]["start_date"] == "2023-01"
    assert draft["experiences"][0]["end_date"] == "2024-06"
    assert draft["education"][0]["start_year"] == 2022
    assert draft["education"][0]["end_year"] == 2024


def test_startup_purge_removes_long_dashes_from_stored_text():
    from app.main import purge_long_dashes

    db = SessionLocal()
    skill_id = None
    try:
        skill = models.Skill(
            name="Test \u2014 tiret long",
            category="Test",
            aliases=["Alias \u2013 long"],
        )
        db.add(skill)
        db.commit()
        db.refresh(skill)
        skill_id = skill.id

        purge_long_dashes()

        db.expire_all()
        stored = db.get(models.Skill, skill_id)
        assert stored.name == "Test - tiret long"
        assert stored.aliases == ["Alias - long"]
    finally:
        stored = db.get(models.Skill, skill_id) if skill_id else None
        if stored:
            db.delete(stored)
            db.commit()
        db.close()


def test_library_import_refuses_an_unrecognized_document(client, demo_headers):
    me = client.get("/api/auth/me", headers=demo_headers).json()
    db = SessionLocal()
    try:
        old = models.Document(
            user_id=me["id"], kind="cv", title="CV illisible",
            content_markdown="Un texte libre sans structure de CV.",
            source_profile=None,
        )
        db.add(old)
        db.commit()
        db.refresh(old)
        old_id = old.id
    finally:
        db.close()

    imported = client.post("/api/profile/import-cv/library", json={
        "document_id": old_id,
    }, headers=demo_headers)
    assert imported.status_code == 422, imported.text

    client.delete(f"/api/documents/{old_id}", headers=demo_headers)
