"""Photo de profil de l'entreprise ou du recruteur (point 25).

Le logo est facultatif, public, et sert d'identité visuelle dans le profil
recruteur, les offres et la messagerie. Sans logo, le frontend conserve
les initiales comme repli neutre.
"""
from __future__ import annotations

import base64

# PNG 1 x 1 valide, suffisant pour vérifier le stockage et le service HTTP.
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8"
    "/x8AAusB9Wl2nWQAAAAASUVORK5CYII="
)


def _recruiter(client, email="logo.recruteur@tgc.cm", company="Logo Entreprise CM"):
    res = client.post("/api/auth/register/recruiter", json={
        "email": email,
        "password": "pass1234",
        "recruiter_type": "company",
        "company_name": company,
        "company_sector": "Informatique / IT",
        "company_description": "Test de la photo de profil.",
        "company_location": "Douala",
    })
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def _job(client, headers, title="Développeur web"):
    res = client.post("/api/recruiter/jobs", json={
        "title": title,
        "location": "Douala",
        "sector": "Informatique / IT",
        "contract_type": "CDI",
        "description": "Développement d'applications web.",
        "requirements": "Maîtrise de JavaScript et des API.",
        "required_skills": [
            {"name": "JavaScript", "importance": "core"},
        ],
    }, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_company_logo_upload_public_and_job_branding(client):
    headers = _recruiter(client)
    company = client.get("/api/recruiter/company", headers=headers).json()
    assert company["has_logo"] is False
    assert company["logo_url"] is None

    uploaded = client.post(
        "/api/recruiter/company/logo",
        files={"file": ("logo.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    company = uploaded.json()
    assert company["has_logo"] is True
    assert company["logo_url"].startswith(
        f"/api/public/companies/{company['id']}/logo?v="
    )

    public = client.get(company["logo_url"])
    assert public.status_code == 200
    assert public.headers["content-type"].startswith("image/png")
    assert public.content == PNG_BYTES

    job = _job(client, headers)
    detail = client.get(f"/api/jobs/{job['id']}")
    assert detail.status_code == 200
    branding = detail.json()["job"]["company_branding"]
    assert branding["has_logo"] is True
    assert branding["logo_url"] == company["logo_url"]

    listing = client.get("/api/jobs")
    assert listing.status_code == 200
    row = next(item for item in listing.json() if item["id"] == job["id"])
    assert row["company_branding"]["logo_url"] == company["logo_url"]

    # Un nouveau fichier change l'URL : l'ancien visuel ne reste pas en cache.
    old_url = company["logo_url"]
    replaced = client.post(
        "/api/recruiter/company/logo",
        files={"file": ("logo2.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    assert replaced.status_code == 200, replaced.text
    new_url = replaced.json()["logo_url"]
    assert new_url != old_url
    assert client.get(new_url).status_code == 200

    deleted = client.delete("/api/recruiter/company/logo", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["has_logo"] is False
    assert deleted.json()["logo_url"] is None
    assert client.get(new_url).status_code == 404

    detail = client.get(f"/api/jobs/{job['id']}")
    assert detail.json()["job"]["company_branding"]["logo_url"] is None


def test_company_logo_validation_roles_and_missing_file(client, demo_headers):
    headers = _recruiter(client, "logo.validation@tgc.cm", "Logo Validation CM")

    invalid = client.post(
        "/api/recruiter/company/logo",
        files={"file": ("logo.gif", b"GIF89a", "image/gif")},
        headers=headers,
    )
    assert invalid.status_code == 400
    assert "JPG" in invalid.json()["detail"]

    empty = client.post(
        "/api/recruiter/company/logo",
        files={"file": ("logo.png", b"", "image/png")},
        headers=headers,
    )
    assert empty.status_code == 400

    too_big = client.post(
        "/api/recruiter/company/logo",
        files={
            "file": ("logo.png", b"x" * (5 * 1024 * 1024 + 1), "image/png")
        },
        headers=headers,
    )
    assert too_big.status_code == 400
    assert "5 Mo" in too_big.json()["detail"]

    forbidden = client.post(
        "/api/recruiter/company/logo",
        files={"file": ("logo.png", PNG_BYTES, "image/png")},
        headers=demo_headers,
    )
    assert forbidden.status_code == 403
    assert client.delete(
        "/api/recruiter/company/logo", headers=demo_headers
    ).status_code == 403

    assert client.get("/api/public/companies/999999/logo").status_code == 404
    # Suppression idempotente : aucun logo, aucune erreur.
    deleted = client.delete("/api/recruiter/company/logo", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["logo_url"] is None


def test_company_logo_in_messaging_identity(client, demo_headers):
    headers = _recruiter(client, "logo.messages@tgc.cm", "Logo Messages CM")
    uploaded = client.post(
        "/api/recruiter/company/logo",
        files={"file": ("logo.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    logo_url = uploaded.json()["logo_url"]

    sent = client.post("/api/messages", json={
        "recipient_id": 1,
        "body": "Bonjour, notre entreprise recrute un développeur web.",
    }, headers=headers)
    assert sent.status_code == 201, sent.text
    sender_id = sent.json()["sender_id"]

    threads = client.get("/api/messages", headers=demo_headers).json()
    thread = next(t for t in threads if t["other_user_id"] == sender_id)
    assert thread["other_company"]["logo_url"] == logo_url

    full = client.get(f"/api/messages/{sender_id}", headers=demo_headers)
    assert full.status_code == 200
    assert full.json()["identity"]["company"]["logo_url"] == logo_url
