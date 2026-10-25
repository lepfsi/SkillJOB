"""Tests V1.5 : référentiel de formation (liens typés et vérifiables) et
formations suivies : la preuve déclarée transforme la formation en
expérience vérifiable du profil (§19, §47)."""
import json

from app import config

ALLOWED_LINK_KINDS = {"exact", "catalogue", "search", "local", "interne"}


def _candidate(client, email="candidat.v15@orientskill.cm"):
    """Candidat neuf : on ne touche pas au profil de démonstration."""
    reg = client.post("/api/auth/register", json={
        "email": email, "password": "pass1234", "full_name": "Aline Test",
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def _profile(client, headers, skills=("Docker",)):
    response = client.put("/api/profile", json={
        "title": "Technicienne support",
        "summary": "Profil de test.",
        "skills": [
            {"skill": s, "proficiency": "intermediaire", "source": "declared"}
            for s in skills
        ],
    }, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------ Référentiel (§19)

def test_referential_annotates_and_covers_every_skill():
    """Chaque compétence de la taxonomie a des ressources et chaque lien
    annonce ce qu'il ouvre (formation exacte, catalogue, recherche, local)."""
    referential = json.loads(
        (config.DATA_DIR / "learning_resources.json").read_text(encoding="utf-8")
    )
    taxonomy = json.loads(
        (config.DATA_DIR / "skills_taxonomy.json").read_text(encoding="utf-8")
    )
    names = {t["name"] for t in taxonomy}
    assert set(referential) <= names, sorted(set(referential) - names)
    assert names - set(referential) == set(), sorted(names - set(referential))

    for skill, resources in referential.items():
        assert resources, skill
        for r in resources:
            assert r["link_kind"] in ALLOWED_LINK_KINDS, (skill, r)
            if r["link_kind"] == "exact":
                assert (r.get("url") or "").startswith("http"), (skill, r)
            if r["link_kind"] == "local":
                assert r.get("provider"), (skill, r)
            assert r["type"] in ("course", "certification", "project", "free")


def test_learning_exposes_typed_links(demo_headers, client):
    body = client.get("/api/learning", headers=demo_headers).json()
    items = body["learn_now"] + body["improve"] + body["learn_next"]
    assert items
    for item in items:
        for r in item["resources"]:
            assert r["link_kind"] in ALLOWED_LINK_KINDS


# ------------------------------------------------- Formations suivies (§19)

def test_enrollment_becomes_verifiable_experience(client):
    headers = _candidate(client)
    before = _profile(client, headers)

    # 1) Ouvrir une formation réelle : le suivi démarre.
    created = client.post("/api/learning/enrollments", json={
        "skill": "Docker",
        "title": "Docker Essentials",
        "provider": "IBM / Coursera",
        "url": "https://www.coursera.org/learn/ibm-docker-kubernetes-openshift-crc",
        "kind": "course",
        "link_kind": "exact",
    }, headers=headers)
    assert created.status_code == 201, created.text
    enrollment = created.json()
    assert enrollment["status"] == "commencee"
    assert enrollment["verifiable"] is False

    # 2) Rejouer la même ouverture : aucun doublon.
    again = client.post("/api/learning/enrollments", json={
        "skill": "docker", "title": "Docker Essentials",
        "provider": "IBM / Coursera", "url": enrollment["url"],
    }, headers=headers)
    assert again.status_code == 201
    assert again.json()["id"] == enrollment["id"]

    # 3) Ajouter au profil SANS preuve : refusé (rien n'est inventé).
    refused = client.post(
        f"/api/learning/enrollments/{enrollment['id']}/to-profile",
        headers=headers,
    )
    assert refused.status_code == 400
    assert "preuve" in refused.json()["detail"].lower()

    # 4) Terminer avec un certificat : la référence est obligatoire.
    missing_ref = client.patch(
        f"/api/learning/enrollments/{enrollment['id']}",
        json={"status": "terminee", "proof_kind": "certificat"},
        headers=headers,
    )
    assert missing_ref.status_code == 400

    proof = client.patch(
        f"/api/learning/enrollments/{enrollment['id']}",
        json={
            "status": "terminee",
            "proof_kind": "certificat",
            "proof_reference": "https://coursera.org/verify/ABC123",
            "proof_note": "Formation suivie en ligne, 12 h.",
        },
        headers=headers,
    )
    assert proof.status_code == 200, proof.text
    assert proof.json()["status"] == "terminee"
    assert proof.json()["verifiable"] is True
    assert proof.json()["completed_at"]

    # 5) La preuve devient une expérience vérifiable du profil.
    added = client.post(
        f"/api/learning/enrollments/{enrollment['id']}/to-profile",
        headers=headers,
    )
    assert added.status_code == 200, added.text
    profile = added.json()["profile"]
    experience = next(
        e for e in profile["experiences"] if e["title"] == "Formation « Docker Essentials »"
    )
    assert experience["organization"] == "IBM / Coursera"
    assert experience["skills"] == ["Docker"]
    assert "Formation suivie" in experience["description"]
    certification = next(
        c for c in profile["certifications"] if c["name"] == "Docker Essentials"
    )
    assert certification["url"] == "https://coursera.org/verify/ABC123"
    assert certification["skills"] == ["Docker"]
    assert added.json()["enrollment"]["added_to_profile"] is True

    # Le profil reste cohérent : les compétences d'avant sont conservées.
    assert len(profile["skills"]) == len(before["skills"])
    skill = next(s for s in profile["skills"] if s["skill"] == "Docker")
    assert skill["source"] == "evidence"

    # 6) La progression vérifiable porte la preuve, et le suivi est listé.
    body = client.get("/api/learning", headers=headers).json()
    progress = next(p for p in body["progress"] if p["skill"] == "Docker")
    assert progress["status"] == "verifiee"
    assert any("Docker Essentials" in e["label"] for e in progress["evidences"])
    assert body["stats"]["verifiable"] == 1
    assert body["stats"]["added_to_profile"] == 1
    assert [e["value"] for e in body["proof_kinds"]] == [
        "aucune", "certificat", "attestation", "badge", "portfolio", "autre",
    ]

    # 7) Rejouer l'ajout au profil n'ajoute pas de doublon.
    second = client.post(
        f"/api/learning/enrollments/{enrollment['id']}/to-profile",
        headers=headers,
    )
    assert second.status_code == 200
    assert len(second.json()["profile"]["experiences"]) == len(profile["experiences"])

    # 8) Le suivi se retire ; la preuve validée reste au profil.
    deleted = client.delete(
        f"/api/learning/enrollments/{enrollment['id']}", headers=headers
    )
    assert deleted.status_code == 200
    after = client.get("/api/learning", headers=headers).json()
    assert after["enrollments"] == []
    assert after["progress"]  # la page reste servie
    still = client.get("/api/profile", headers=headers).json()
    assert any(e["title"] == "Formation « Docker Essentials »"
               for e in still["experiences"])


def test_enrollment_is_private(client):
    """Le suivi d'un candidat n'est pas visible d'un autre compte."""
    owner = _candidate(client, "proprietaire.v15@orientskill.cm")
    _profile(client, owner)
    created = client.post("/api/learning/enrollments", json={
        "skill": "Linux", "title": "Linux Essentials",
        "provider": "Cisco Networking Academy", "kind": "course",
    }, headers=owner).json()

    other = _candidate(client, "voisin.v15@orientskill.cm")
    _profile(client, other)
    assert client.patch(
        f"/api/learning/enrollments/{created['id']}",
        json={"status": "en_cours"}, headers=other,
    ).status_code == 404
    assert client.delete(
        f"/api/learning/enrollments/{created['id']}", headers=other
    ).status_code == 404
    assert client.get("/api/learning", headers=other).json()["enrollments"] == []


def test_referential_is_synced_with_the_database():
    """La table de référence reste alignée sur le fichier (liens vérifiés) :
    l'assistant et le graphe de compétences ne citent jamais un lien périmé."""
    from app import models
    from app.database import SessionLocal

    referential = json.loads(
        (config.DATA_DIR / "learning_resources.json").read_text(encoding="utf-8")
    )
    wanted = {
        (skill, r["title"]) for skill, items in referential.items() for r in items
    }
    db = SessionLocal()
    try:
        rows = {(r.skill, r.title) for r in db.query(models.LearningResource)}
    finally:
        db.close()
    assert rows == wanted
    assert len(wanted) >= 240


def test_assistant_reports_tracked_trainings(client):
    """L'assistant connaît les formations réellement suivies et leurs preuves."""
    headers = _candidate(client, "suivi.v15@orientskill.cm")
    _profile(client, headers)
    created = client.post("/api/learning/enrollments", json={
        "skill": "Docker", "title": "Docker Essentials",
        "provider": "KodeKloud", "kind": "course",
        "url": "https://kodekloud.com/courses/docker-training-course-for-the-absolute-beginner",
        "link_kind": "exact",
    }, headers=headers).json()
    client.patch(f"/api/learning/enrollments/{created['id']}", json={
        "status": "terminee", "proof_kind": "attestation",
        "proof_reference": "ATT-2026-0042",
    }, headers=headers)

    reply = client.post("/api/assistant", json={
        "message": "Où en sont mes formations suivies ?",
        "history": [],
    }, headers=headers)
    assert reply.status_code == 200, reply.text
    text = reply.json()["reply"]
    assert "Docker Essentials" in text
    assert "KodeKloud" in text
    assert "Terminée" in text
    assert any(link["href"] == "/learning" for link in reply.json()["links"])
