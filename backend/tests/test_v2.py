"""Tests V2 : cloisonnement (non-HTTP), ingestion multi-source, import
par URL (JSON-LD), shortlists recruteur, statut partagé, digest, bot Telegram."""
import io
import json
from datetime import datetime, timedelta

import pytest

from app import models
from app.services import ingestion, telegram_bot


# ------------------------------------------------ Parsing des flux

RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Offres Cameroun</title>
  <item>
    <title>Ingénieur génie civil recruté chez Sogea à Douala</title>
    <link>https://exemple.cm/offre/1</link>
    <description>BTP : chantier, Lecture de plans, AutoCAD, conduite de chantier.</description>
  </item>
  <item>
    <title>Comptable senior chez SBC Douala</title>
    <link>https://exemple.cm/offre/2</link>
    <description>Comptabilité générale, Sage, Excel avancé.</description>
  </item>
</channel></rss>"""


def test_parse_rss_items():
    items = ingestion.parse_rss(RSS_SAMPLE.encode("utf-8"))
    assert len(items) == 2
    assert "Sogea" in items[0]["title"] or "génie civil" in items[0]["title"]
    assert items[0]["link"] == "https://exemple.cm/offre/1"


def test_parse_json_feed_items():
    raw = json.dumps({"items": [
        {"title": "Technicien labo", "url": "https://x.cm/1",
         "company": "Labo CM", "description": "Santé, statistiques."},
        {"title": "Vendeuse", "url": "https://x.cm/2",
         "company": "Boutique", "description": "Commerce, vente."},
    ]}).encode("utf-8")
    items = ingestion.parse_json_feed(raw)
    assert len(items) == 2
    assert items[0]["author"] == "Labo CM"


# --------------------------------------------------- Import par URL

JSONLD_HTML = """<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "JobPosting",
  "title": "Analyste SOC junior",
  "hiringOrganization": {"name": "CyberSar CM"},
  "jobLocation": {"address": {"addressLocality": "Yaoundé", "addressCountry": "CM"}},
  "employmentType": "FULL_TIME",
  "description": "Surveillance SOC, SIEM, Linux, réseaux TCP/IP.",
  "skills": "SOC, SIEM, Linux"
}
</script>
</head><body></body></html>"""


def test_import_job_from_url(monkeypatch):
    monkeypatch.setattr(ingestion, "_fetch", lambda url, timeout=15: JSONLD_HTML.encode("utf-8"))
    draft = ingestion.import_job_from_url("https://linkedin.com/jobs/view/123")
    assert draft["title"] == "Analyste SOC junior"
    assert draft["company"] == "CyberSar CM"
    assert "Yaoundé" in draft["location"]
    assert draft["contract_type"] == "CDI"
    names = [s["name"] for s in draft["required_skills"]]
    # La taxonomie normalise : « SIEM » → compétence canonique « SOC / SIEM »
    assert any("SIEM" in n for n in names) and "Linux" in names
    assert draft["source_url"].endswith("/123")


def test_import_url_no_markup(monkeypatch):
    monkeypatch.setattr(ingestion, "_fetch", lambda url, timeout=15: b"<html><body>rien</body></html>")
    draft = ingestion.import_job_from_url("https://exemple.fr")
    assert "error" in draft


# ------------------------------------------- Collecte + dédup (admin)

def _admin_headers(client):
    login = client.post("/api/auth/login", json={
        "email": "admin@orientskill.cm", "password": "admin1234",
    })
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _recruiter_headers(client, email="recruteur.v2@tgc.cm"):
    reg = client.post("/api/auth/register/recruiter", json={
        "email": email, "password": "pass1234",
        "recruiter_type": "company",
        "company_name": "V2 Collecte CM",
        "company_sector": "BTP / Construction",
        "company_description": "Test.",
        "company_location": "Douala",
    })
    assert reg.status_code == 201
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def test_sources_crud_and_run(client, monkeypatch):
    headers = _admin_headers(client)

    created = client.post("/api/admin/sources", json={
        "name": "Flux test CM", "kind": "rss",
        "url": "https://exemple.cm/feed.xml", "sector": "BTP / Construction",
    }, headers=headers)
    assert created.status_code == 201, created.text
    source_id = created.json()["id"]

    # Collecte : le flux est servi localement par le monkeypatch
    monkeypatch.setattr(ingestion, "_fetch", lambda url, timeout=15: RSS_SAMPLE.encode("utf-8"))
    run = client.post(f"/api/admin/sources/{source_id}/run", headers=headers)
    assert run.status_code == 200
    assert run.json()["imported"] == 2

    # Fiabilité de la source suivie (§51)
    sources = client.get("/api/admin/sources", headers=headers).json()
    src = next(s for s in sources if s["id"] == source_id)
    assert src["offers_imported"] == 2
    assert "réussite" in src["reliability"]

    # Déduplication : second passage → 0 importé, 2 doublons
    run2 = client.post(f"/api/admin/sources/{source_id}/run", headers=headers)
    assert run2.json()["imported"] == 0
    assert run2.json()["skipped"] == 2

    # Les offres importées sont visibles côté candidat
    login = client.post("/api/auth/login", json={
        "email": "demo@orientskill.cm", "password": "demo1234",
    })
    dheaders = {"Authorization": f"Bearer {login.json()['token']}"}
    jobs = client.get("/api/jobs?search=Ingénieur génie civil", headers=dheaders).json()
    assert len(jobs) == 1
    assert jobs[0]["source"]["name"] == "Collecte · Flux test CM"

    # Suppression de la source
    deleted = client.delete(f"/api/admin/sources/{source_id}", headers=headers)
    assert deleted.status_code == 200


# ------------------------------------------------- Shortlists recruteur

def test_shortlists_flow(client):
    rh = _recruiter_headers(client, email="shortlists@tgc.cm")

    sl = client.post("/api/recruiter/shortlists", json={
        "name": "Shortlist techniciens réseau",
        "note": "Pour le poste de sept.",
    }, headers=rh)
    assert sl.status_code == 201
    sl_id = sl.json()["id"]

    added = client.post(f"/api/recruiter/shortlists/{sl_id}/items", json={
        "candidate_id": 1,
    }, headers=rh)
    assert added.status_code == 200

    # Doublon toléré
    again = client.post(f"/api/recruiter/shortlists/{sl_id}/items", json={
        "candidate_id": 1,
    }, headers=rh)
    assert again.json()["ok"] is True

    lists = client.get("/api/recruiter/shortlists", headers=rh).json()
    target = next(s for s in lists if s["id"] == sl_id)
    assert len(target["items"]) == 1
    assert target["items"][0]["candidate_id"] == 1

    # Retrait puis suppression de la shortlist
    removed = client.delete(f"/api/recruiter/shortlists/{sl_id}/items/1", headers=rh)
    assert removed.status_code == 200
    deleted = client.delete(f"/api/recruiter/shortlists/{sl_id}", headers=rh)
    assert deleted.status_code == 200


def test_shortlist_isolated_between_recruiters(client):
    rh1 = _recruiter_headers(client, email="sl1@tgc.cm")
    rh2 = _recruiter_headers(client, email="sl2@tgc.cm")
    sl = client.post("/api/recruiter/shortlists", json={"name": "Liste privée"}, headers=rh1).json()
    # Le recruteur 2 ne peut ni voir ni modifier la liste du recruteur 1
    assert client.get("/api/recruiter/shortlists", headers=rh2).json() == []
    assert client.delete(f"/api/recruiter/shortlists/{sl['id']}", headers=rh2).status_code == 404


# ---------------------------------------- Statut partagé des candidatures

def test_recruiter_updates_shared_application_status(client):
    rh = _recruiter_headers(client, email="shared.status@tgc.cm")
    job = client.post("/api/recruiter/jobs", json={
        "title": "Technicien support", "company": "V2 Collecte CM",
        "location": "Douala", "sector": "IT", "contract_type": "CDI",
        "required_skills": [],
    }, headers=rh).json()

    login = client.post("/api/auth/login", json={
        "email": "demo@orientskill.cm", "password": "demo1234",
    })
    dheaders = {"Authorization": f"Bearer {login.json()['token']}"}
    app = client.post("/api/applications", json={"job_id": job["id"]},
                      headers=dheaders).json()

    # Le recruteur fait passer la candidature en entretien
    updated = client.patch(f"/api/recruiter/applications/{app['id']}", json={
        "status": "entretien",
    }, headers=rh)
    assert updated.status_code == 200, updated.text

    # Le candidat VOIT le changement dans son pipeline et sa timeline
    mine = client.get("/api/applications", headers=dheaders).json()
    target = next(a for a in mine if a["id"] == app["id"])
    assert target["status"] == "entretien"
    assert any("V2 Collecte CM" in ev["event"] for ev in target["timeline"])

    # Un recruteur ne touche pas les candidatures d'une autre entreprise
    other = _recruiter_headers(client, email="other.rh@tgc.cm")
    assert client.patch(f"/api/recruiter/applications/{app['id']}", json={
        "status": "offre",
    }, headers=other).status_code == 404


# ----------------------------------------------------------- Digest

def test_build_digest_for_candidate(client):
    from fastapi.testclient import TestClient
    from app.main import app  # noqa: F401
    from app.database import SessionLocal
    from app.services.digest import build_digest_for

    db = SessionLocal()
    try:
        demo = db.query(models.User).filter_by(email="demo@orientskill.cm").first()
        body = build_digest_for(db, demo, datetime.utcnow() - timedelta(days=1))
        # Le seed contient des offres récentes correspondant au profil démo
        assert "correspondent à votre profil" in body
        assert "correspondance" in body
    finally:
        db.close()


def test_digest_disabled_by_default(client):
    from app.database import SessionLocal
    from app.services.digest import digest_enabled

    db = SessionLocal()
    try:
        assert digest_enabled(db) is False
    finally:
        db.close()


# ------------------------------------------------------ Bot Telegram

def test_telegram_bot_commands(client):
    assert "Bienvenue" in telegram_bot.handle_command("/start", 1)
    assert "OrientSkill AI" in telegram_bot.handle_command("/help", 1)
    offers = telegram_bot.handle_command("/offres", 1)
    assert "Offres récentes" in offers or "Aucune offre" in offers
    filtered = telegram_bot.handle_command("/offres comptable", 1)
    assert "comptable" in filtered.lower() or "Aucune offre" in filtered
    assert "/offres" in telegram_bot.handle_command("n'importe quoi", 1)


# ------------------------------------------ Cloisonnement des rôles

def test_candidate_pages_forbidden_to_admin(client):
    """L'admin n'a PAS de profil candidat et reçoit une réponse claire."""
    headers = _admin_headers(client)
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["role"] == "admin"
    profile = client.get("/api/profile", headers=headers)
    assert profile.status_code == 200 and profile.json() is None
    # L'espace recruteur lui est interdit
    assert client.get("/api/recruiter/company", headers=headers).status_code == 403
