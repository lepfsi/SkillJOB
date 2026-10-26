"""Candidature publique : lien d'une offre, compte automatique.

Un candidat non inscrit saisit nom, e-mail et téléphone ; le compte et la
candidature sont créés, la session est ouverte, l'e-mail d'accès est tenté.
Les offres externes et les offres closes restent honnêtement refusées.
"""
from datetime import timedelta

from app import models
from app.database import SessionLocal


def _recruiter_job(client, email="recruteur.public@tgc.cm"):
    reg = client.post("/api/auth/register/recruiter", json={
        "email": email,
        "password": "pass1234",
        "recruiter_type": "company",
        "company_name": "Entreprise Publique SARL",
        "company_sector": "Informatique / IT",
        "company_description": "Entreprise de test.",
        "company_location": "Douala",
    })
    assert reg.status_code == 201, reg.text
    rh = {"Authorization": f"Bearer {reg.json()['token']}"}
    job = client.post("/api/recruiter/jobs", json={
        "title": "Chargé de clientèle",
        "company": "Entreprise Publique SARL",
        "location": "Douala",
        "sector": "Services",
        "contract_type": "CDI",
        "description": "Accueillir et conseiller les clients.",
        "required_skills": [{"name": "Relation client", "importance": "core"}],
    }, headers=rh)
    assert job.status_code == 201, job.text
    return rh, job.json()


def test_public_job_card_and_quick_application(client):
    _rh, job = _recruiter_job(client)

    public = client.get(f"/api/public/jobs/{job['id']}")
    assert public.status_code == 200, public.text
    card = public.json()
    assert card["title"] == "Chargé de clientèle"
    assert card["company"] == "Entreprise Publique SARL"
    assert card["apply_channel"] == "platform"
    assert card["required_skills"][0]["name"] == "Relation client"

    apply = client.post(f"/api/public/jobs/{job['id']}/apply", json={
        "full_name": "Awa Ngo Bell",
        "email": "Awa.Public@orientskill.cm",
        "phone": "+237 699 00 00 00",
        "motivation": "Je souhaite rejoindre votre équipe.",
    })
    assert apply.status_code == 201, apply.text
    body = apply.json()
    assert body["email_sent"] is False
    assert body["user"]["email"] == "awa.public@orientskill.cm"
    assert body["user"]["phone"] == "+237 699 00 00 00"
    headers = {"Authorization": f"Bearer {body['token']}"}

    # La session est immédiatement utilisable et la candidature existe.
    assert client.get("/api/dashboard", headers=headers).status_code == 200
    apps = client.get("/api/applications", headers=headers).json()
    mine = next(a for a in apps if a["id"] == body["application_id"])
    assert mine["job_id"] == job["id"]
    assert mine["apply_channel"] == "platform"
    assert mine["submitted_at"] is not None

    # Un compte existe déjà : on invite à se connecter, sans doublon.
    duplicate = client.post(f"/api/public/jobs/{job['id']}/apply", json={
        "full_name": "Awa Ngo Bell",
        "email": "awa.public@orientskill.cm",
        "phone": "+237 699 00 00 00",
    })
    assert duplicate.status_code == 409
    assert "connectez-vous" in duplicate.json()["detail"].lower()

    # Adresse invalide refusée avant toute création.
    invalid = client.post(f"/api/public/jobs/{job['id']}/apply", json={
        "full_name": "Test Invalide",
        "email": "pas-un-email",
        "phone": "+237 600 00 00 00",
    })
    assert invalid.status_code == 400


def test_public_apply_refuses_external_and_closed_jobs(client):
    with SessionLocal() as db:
        now = models.utcnow()
        external = (
            db.query(models.Job)
            .filter(
                models.Job.company_id.is_(None),
                (models.Job.deadline.is_(None)) | (models.Job.deadline >= now),
            )
            .first()
        )
    if external is not None:
        card = client.get(f"/api/public/jobs/{external.id}")
        assert card.status_code == 200
        assert card.json()["apply_channel"] == "external"
        refused = client.post(f"/api/public/jobs/{external.id}/apply", json={
            "full_name": "Candidat Externe",
            "email": "candidat.externe@orientskill.cm",
            "phone": "+237 677 00 00 00",
        })
        assert refused.status_code == 400
        assert "entreprise" in refused.json()["detail"].lower()

    _rh, job = _recruiter_job(client, email="recruteur.clos@tgc.cm")
    with SessionLocal() as db:
        row = db.get(models.Job, job["id"])
        row.deadline = models.utcnow() - timedelta(days=1)
        db.commit()
    closed = client.post(f"/api/public/jobs/{job['id']}/apply", json={
        "full_name": "Candidat Tardif",
        "email": "candidat.tardif@orientskill.cm",
        "phone": "+237 655 00 00 00",
    })
    assert closed.status_code == 400
    assert "closes" in closed.json()["detail"].lower()
