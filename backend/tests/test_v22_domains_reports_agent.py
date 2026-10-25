"""Référentiel domaines, préférences, signalements et agent.

Ces tests couvrent les chantiers transversaux : sélection d'un domaine
et de spécialités, signalement d'une offre traité par l'administration,
mode de travail de l'agent et liens profonds vers les formations.
"""


def _candidate(client, email="candidat.v22@orientskill.cm"):
    reg = client.post("/api/auth/register", json={
        "email": email,
        "password": "pass1234",
        "full_name": "Aline Referentiel",
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def _domains(client):
    response = client.get("/api/domains")
    assert response.status_code == 200, response.text
    return response.json()


def _informatique(tree):
    return next(d for d in tree if d["name"] == "Informatique et numérique")


def _job_id(client):
    jobs = client.get("/api/jobs").json()
    assert jobs, "le seed doit fournir au moins une offre"
    return jobs[0]["id"]


def test_domain_referential_is_seeded_with_informal_and_other(client):
    tree = _domains(client)
    names = {d["name"] for d in tree}
    assert len(tree) >= 25
    assert {"Informatique et numérique", "Secteur informel", "Autres"} <= names
    total_specialties = sum(len(d.get("specialties", [])) for d in tree)
    assert total_specialties >= 250
    info = _informatique(tree)
    assert any(s["name"] == "Cybersécurité" for s in info["specialties"])


def test_candidate_selects_domain_and_specialties(client):
    headers = _candidate(client)
    info = _informatique(_domains(client))
    network = next(s for s in info["specialties"] if s["name"] == "Réseaux et systèmes")
    cyber = next(s for s in info["specialties"] if s["name"] == "Cybersécurité")

    saved = client.put("/api/profile", json={
        "title": "Technicienne réseaux",
        "summary": "Profil de test.",
        "skills": [{"skill": "Cisco", "proficiency": "intermediaire"}],
        "preferences": {
            "domain_id": info["id"],
            "specialty_ids": [network["id"], cyber["id"]],
        },
    }, headers=headers)
    assert saved.status_code == 200, saved.text
    prefs = saved.json()["preferences"]
    assert prefs["domain_id"] == info["id"]
    assert set(prefs["specialty_ids"]) == {network["id"], cyber["id"]}

    # Le CV ATS reprend le domaine choisi dans son en-tête, sans invention.
    doc = client.post("/api/cv", json={"template": "ats"}, headers=headers)
    assert doc.status_code == 200, doc.text
    content = doc.json()["content_markdown"]
    assert "Domaines : Informatique et numérique" in content
    assert "Réseaux et systèmes" in content


def test_admin_manages_domain_then_disables_without_breaking(client, admin_headers):
    created = client.post("/api/admin/domains", json={
        "name": "Économie bleue",
        "description": "Métiers de la mer, des fleuves et des lacs.",
        "aliases": ["mer", "fleuve"],
    }, headers=admin_headers)
    assert created.status_code == 201, created.text
    domain = created.json()

    specialty = client.post(
        f"/api/admin/domains/{domain['id']}/specialties",
        json={"name": "Aquaculture", "description": "Élevage aquatique."},
        headers=admin_headers,
    )
    assert specialty.status_code == 201, specialty.text
    assert specialty.json()["name"] == "Aquaculture"

    public_names = {d["name"] for d in _domains(client)}
    assert "Économie bleue" in public_names

    disabled = client.delete(
        f"/api/admin/domains/{domain['id']}", headers=admin_headers
    )
    assert disabled.status_code == 200, disabled.text
    public_names = {d["name"] for d in _domains(client)}
    assert "Économie bleue" not in public_names
    admin_names = {
        d["name"]
        for d in client.get("/api/admin/domains", headers=admin_headers).json()
    }
    assert "Économie bleue" in admin_names


def test_candidate_reports_job_and_admin_processes_it(client, admin_headers):
    headers = _candidate(client, "candidat.signalement@orientskill.cm")
    job_id = _job_id(client)

    report = client.post(f"/api/jobs/{job_id}/reports", json={
        "reason": "contenu_trompeur",
        "details": "Le salaire annoncé ne correspond pas à la description.",
    }, headers=headers)
    assert report.status_code == 201, report.text
    body = report.json()
    assert body["status"] == "nouveau"
    assert body["job_id"] == job_id

    duplicate = client.post(f"/api/jobs/{job_id}/reports", json={
        "reason": "doublon", "details": "",
    }, headers=headers)
    assert duplicate.status_code == 409

    detail = client.get(f"/api/jobs/{job_id}", headers=headers).json()
    assert detail["my_report"]["id"] == body["id"]

    listed = client.get("/api/admin/reports?status=nouveau", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    mine = next(r for r in listed.json() if r["id"] == body["id"])
    assert mine["user_email"] == "candidat.signalement@orientskill.cm"
    assert mine["job_title"]

    handled = client.put(f"/api/admin/reports/{body['id']}", json={
        "status": "traite",
        "admin_note": "Offre vérifiée et corrigée avec le recruteur.",
    }, headers=admin_headers)
    assert handled.status_code == 200, handled.text
    assert handled.json()["status"] == "traite"

    detail = client.get(f"/api/jobs/{job_id}", headers=headers).json()
    assert detail["my_report"]["status"] == "traite"
    assert "corrigée" in detail["my_report"]["admin_note"]

    stats = client.get("/api/admin/stats", headers=admin_headers).json()
    assert "open_reports" in stats


def test_report_reason_is_validated(client):
    headers = _candidate(client, "candidat.signalement2@orientskill.cm")
    job_id = _job_id(client)
    bad = client.post(f"/api/jobs/{job_id}/reports", json={
        "reason": "inconnu", "details": "",
    }, headers=headers)
    assert bad.status_code == 422


def test_agent_mode_is_persisted_and_validated(client):
    headers = _candidate(client, "candidat.mode@orientskill.cm")
    initial = client.get("/api/agent/mode", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["mode"] == "preparation"

    changed = client.put("/api/agent/mode", json={"mode": "veille"},
                         headers=headers)
    assert changed.status_code == 200, changed.text
    assert client.get("/api/agent/mode", headers=headers).json()["mode"] == "veille"

    bad = client.put("/api/agent/mode", json={"mode": "automatique"},
                     headers=headers)
    assert bad.status_code == 422


def test_agent_next_action_uses_real_data(client):
    headers = _candidate(client, "candidat.action@orientskill.cm")
    client.put("/api/profile", json={
        "title": "Technicienne support",
        "summary": "Profil de test.",
        "skills": [{"skill": "Cisco", "proficiency": "intermediaire"}],
    }, headers=headers)
    reply = client.post("/api/assistant", json={
        "message": "Que dois-je faire maintenant ?",
        "history": [],
    }, headers=headers)
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert "prochaine action" in body["reply"].lower()
    hrefs = {link["href"] for link in body["links"]}
    assert "/documents" in hrefs
    assert any(
        h.startswith("/learning/") or h.startswith("/jobs") or h in ("/profile", "/applications")
        for h in hrefs
    )
