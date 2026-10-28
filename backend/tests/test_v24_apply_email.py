"""Transfert automatique des candidatures externes par e-mail (V24).

Une offre externe avec adresse de candidature (``apply_email``) est
transmise par la plateforme : CV et lettre en PDF joints, réponse
adressée au candidat (Reply-To). Sans SMTP configuré ou sans adresse,
la candidature reste tracée et le candidat suit les instructions.
"""
import pytest

from app.services import notifications


class FakeSMTP:
    """SMTP capturé : aucune connexion réelle, les messages sont gardés."""

    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.messages = []
        self.tls = False
        self.login_args = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        self.tls = True

    def login(self, username, password):
        self.login_args = (username, password)

    def send_message(self, msg):
        self.messages.append(msg)


def _candidate(client, email):
    reg = client.post("/api/auth/register", json={
        "email": email, "password": "pass1234", "full_name": "Paula Mail",
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def _profile_and_documents(client, headers, job_id, with_letter=True):
    client.put("/api/profile", json={
        "title": "Technicienne support",
        "summary": "Profil de test e-mail.",
        "skills": [
            {"skill": "Support informatique", "proficiency": "avance"},
            {"skill": "Gestion des incidents", "proficiency": "intermediaire"},
        ],
    }, headers=headers)
    cv = client.post(f"/api/jobs/{job_id}/cv", json={"template": "classique"},
                    headers=headers)
    assert cv.status_code == 200, cv.text
    letter_id = None
    if with_letter:
        letter = client.post(f"/api/jobs/{job_id}/cover-letter",
                             json={"template": "classique"}, headers=headers)
        assert letter.status_code == 200, letter.text
        letter_id = letter.json()["id"]
    return cv.json()["id"], letter_id


def _external_job(client, admin_headers, **extra):
    payload = {
        "title": "Technicien support externe (mail)",
        "company": "Externe Mail SARL",
        "location": "Douala",
        "sector": "Informatique / IT",
        "contract_type": "CDD",
        "description": "Support de premier niveau.",
        "requirements": "Rigueur.",
        "source_name": "Site Externe Mail",
        "source_url": "https://externe-mail.cm/offre/42",
        "apply_channel": "external",
        "apply_instructions": "Postulez via le formulaire du site.",
        "apply_email": "recrutement@externe-mail.cm",
        "required_skills": [
            {"name": "Support informatique", "importance": "core"},
        ],
    }
    payload.update(extra)
    job = client.post("/api/admin/jobs", json=payload, headers=admin_headers)
    assert job.status_code == 201, job.text
    return job.json()


def _smtp(client, admin_headers, enabled):
    res = client.put("/api/admin/settings/smtp", json={
        "data": {"provider": "smtp", "enabled": enabled,
                 "host": "smtp.exemple.cm", "port": 587,
                 "username": "candidatures@orientskill.cm", "password": "secret",
                 "from_email": "candidatures@orientskill.cm", "use_tls": True},
    }, headers=admin_headers)
    assert res.status_code == 200, res.text


def test_external_application_is_transferred_by_email(
    client, admin_headers, monkeypatch
):
    """SMTP configuré : la plateforme envoie CV + lettre, réponse au candidat."""
    _smtp(client, admin_headers, True)
    FakeSMTP.instances = []
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)

    headers = _candidate(client, "candidat.mail@orientskill.cm")
    job = _external_job(client, admin_headers)
    cv_id, letter_id = _profile_and_documents(client, headers, job["id"])

    try:
        submit = client.post(f"/api/applications/jobs/{job['id']}/submit", json={
            "cv_document_id": cv_id,
            "cover_letter_document_id": letter_id,
            "cover_note": "Bonjour, je suis motivée et disponible.",
        }, headers=headers)
        assert submit.status_code == 200, submit.text
        body = submit.json()
        assert body["apply_channel"] == "external"
        assert body["apply_email"] == "recrutement@externe-mail.cm"

        # Un seul envoi, au bon destinataire, réponse adressée au candidat.
        assert len(FakeSMTP.instances) == 1
        server = FakeSMTP.instances[0]
        assert server.tls is True
        assert server.login_args == ("candidatures@orientskill.cm", "secret")
        assert len(server.messages) == 1
        msg = server.messages[0]
        assert msg["To"] == "recrutement@externe-mail.cm"
        assert msg["Reply-To"] == "candidat.mail@orientskill.cm"
        assert job["title"] in msg["Subject"]

        # CV et lettre partent en PDF joints.
        attachments = list(msg.iter_attachments())
        assert len(attachments) == 2, "CV + lettre attendus en pièces jointes"
        for part in attachments:
            assert part.get_content_type() == "application/pdf"
            payload = part.get_payload(decode=True)
            assert payload[:4] == b"%PDF"
        filenames = sorted(p.get_filename() for p in attachments)
        assert any(f.lower().endswith(".pdf") for f in filenames)

        # Le message rappelle l'offre et le message du candidat.
        body_part = msg.get_body(preferencelist=("plain",))
        raw = body_part.get_content()
        assert "OrientSkill AI" in raw
        assert "je suis motivée" in raw

        # La timeline trace la transmission automatique.
        events = " ".join(e["event"] for e in body["timeline"])
        assert "transmise automatiquement par e-mail" in events

        # Côté admin : le suivi expose l'e-mail et l'URL de l'offre.
        rows = client.get("/api/admin/applications?channel=external",
                          headers=admin_headers).json()
        row = next(r for r in rows if r["job_id"] == job["id"])
        assert row["apply_email"] == "recrutement@externe-mail.cm"
        assert row["apply_url"] == "https://externe-mail.cm/offre/42"
    finally:
        _smtp(client, admin_headers, False)


def test_external_application_without_smtp_stays_traced(client, admin_headers):
    """Sans SMTP configuré : candidature tracée, message explicite."""
    _smtp(client, admin_headers, False)
    headers = _candidate(client, "candidat.nomail@orientskill.cm")
    job = _external_job(client, admin_headers,
                        title="Technicien sans SMTP (mail)")
    cv_id, _ = _profile_and_documents(client, headers, job["id"],
                                      with_letter=False)

    submit = client.post(f"/api/applications/jobs/{job['id']}/submit", json={
        "cv_document_id": cv_id,
    }, headers=headers)
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["submitted_at"] is not None
    events = " ".join(e["event"] for e in body["timeline"])
    assert "transmission automatique non effectuée" in events
    assert body["apply_instructions"].startswith("Postulez")


def test_apply_email_without_address_falls_back(client, admin_headers):
    """Offre externe sans adresse de candidature : instructions uniquement."""
    _smtp(client, admin_headers, False)
    headers = _candidate(client, "candidat.sansadresse@orientskill.cm")
    job = _external_job(client, admin_headers,
                        title="Technicien sans adresse (mail)",
                        apply_email="")
    cv_id, _ = _profile_and_documents(client, headers, job["id"],
                                      with_letter=False)

    submit = client.post(f"/api/applications/jobs/{job['id']}/submit", json={
        "cv_document_id": cv_id,
    }, headers=headers)
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["apply_email"] == ""
    events = " ".join(e["event"] for e in body["timeline"])
    assert "transmission automatique non effectuée" in events


def test_admin_job_apply_fields_roundtrip(client, admin_headers):
    """Les champs de candidature sont renvoyés par la console admin."""
    job = _external_job(client, admin_headers,
                        title="Offre champs roundtrip (mail)")
    listed = client.get("/api/admin/jobs", headers=admin_headers).json()
    row = next(j for j in listed if j["id"] == job["id"])
    assert row["apply_channel"] == "external"
    assert row["apply_email"] == "recrutement@externe-mail.cm"
    assert row["apply_instructions"].startswith("Postulez")

    # Mise à jour : vider l'adresse supprime la transmission auto.
    updated = client.put(f"/api/admin/jobs/{job['id']}", json={
        "apply_email": "",
    }, headers=admin_headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["apply_email"] == ""


def _png_bytes():
    # En-tête PNG minimale : seul le format est vérifié côté serveur.
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_recruiter_sees_candidate_photo_and_links(client):
    """Photo du candidat et lien de postulation visibles du recruteur."""
    reg = client.post("/api/auth/register/recruiter", json={
        "email": "recruteur.photo@tgc.cm", "password": "pass1234",
        "recruiter_type": "company",
        "company_name": "Photo RH SARL",
        "company_sector": "Informatique / IT",
        "company_description": "Test photo.",
        "company_location": "Douala",
    })
    assert reg.status_code == 201, reg.text
    rh = {"Authorization": f"Bearer {reg.json()['token']}"}

    job = client.post("/api/recruiter/jobs", json={
        "title": "Technicien photo (mail)",
        "company": "Photo RH SARL",
        "location": "Douala", "sector": "IT", "contract_type": "CDI",
        "source_url": "https://photo-rh.cm/offre",
        "required_skills": [],
    }, headers=rh).json()

    headers = _candidate(client, "candidat.photomail@orientskill.cm")
    up = client.post("/api/profile/photo",
                     files={"file": ("photo.png", _png_bytes(), "image/png")},
                     headers=headers)
    assert up.status_code == 200, up.text

    cv_id, _ = _profile_and_documents(client, headers, job["id"],
                                      with_letter=False)
    submit = client.post(f"/api/applications/jobs/{job['id']}/submit", json={
        "cv_document_id": cv_id,
    }, headers=headers)
    assert submit.status_code == 200, submit.text

    # La liste des candidatures reçues expose la photo et le lien externe.
    received = client.get("/api/recruiter/applications", headers=rh).json()
    row = next(r for r in received if r["job_id"] == job["id"])
    assert row["candidate_photo_url"].endswith("/photo")
    assert row["apply_url"] == "https://photo-rh.cm/offre"

    # La photo est servie au recruteur, refusée au simple candidat.
    candidate_id = row["candidate_id"]
    photo = client.get(row["candidate_photo_url"], headers=rh)
    assert photo.status_code == 200
    assert photo.headers["content-type"].startswith("image/")
    forbidden = client.get(row["candidate_photo_url"], headers=headers)
    assert forbidden.status_code == 403

    # La carte talent expose aussi la photo.
    card = client.get(f"/api/recruiter/candidates/{candidate_id}",
                      headers=rh).json()
    assert card["photo_url"].endswith("/photo")
