"""Points 13/14 : réglages de l'agent réellement persistés et appliqués.

On vérifie les valeurs par défaut, la validation des choix, la réservation
aux candidats, la règle du mode autonome, le blocage des générations
désactivées et le filtrage de l'inbox.
"""
from datetime import datetime
from types import SimpleNamespace

from app.services import agent_prefs


def _candidate(client, email: str) -> dict:
    res = client.post("/api/auth/register", json={
        "email": email,
        "password": "pass1234",
        "full_name": "Candidat Agent",
    })
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def _recruiter(client, email: str, company: str) -> dict:
    res = client.post("/api/auth/register/recruiter", json={
        "email": email,
        "password": "pass1234",
        "recruiter_type": "company",
        "company_name": company,
        "company_sector": "IT",
        "company_description": "Test agent.",
        "company_location": "Douala",
    })
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


def _profile(client, headers: dict) -> None:
    res = client.put("/api/profile", json={
        "title": "Technicien support",
        "summary": "Profil de test pour l'agent.",
        "skills": [
            {
                "skill": "Docker",
                "proficiency": "intermediaire",
                "source": "declared",
            }
        ],
    }, headers=headers)
    assert res.status_code == 200, res.text


def _job(client, headers: dict, title: str, skills=("Docker",)) -> dict:
    res = client.post("/api/recruiter/jobs", json={
        "title": title,
        "company": "Agent SARL",
        "location": "Douala",
        "sector": "IT",
        "contract_type": "CDI",
        "required_skills": [
            {"name": skill, "importance": "core"} for skill in skills
        ],
    }, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _admin_headers(client) -> dict:
    login = client.post("/api/auth/login", json={
        "email": "admin@orientskill.cm",
        "password": "admin1234",
    })
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['token']}"}


def test_agent_preferences_defaults_and_persistence(client):
    headers = _candidate(client, "agent.prefs1@orientskill.cm")
    res = client.get("/api/agent/preferences", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["mode"] == "preparation"
    assert body["prefs"] == {
        "scope": "tous",
        "frequency": "quotidienne",
        "validation": "documents",
        "actions": {
            "prepare_cv": True,
            "prepare_letter": True,
            "prepare_interview": True,
            "watch_jobs": True,
            "alert_deadlines": True,
        },
    }
    assert {item["id"] for item in body["scopes"]} == {
        "tous", "secteur", "region"
    }
    assert {item["id"] for item in body["frequencies"]} == {
        "quotidienne", "hebdomadaire", "manuelle"
    }
    assert {item["id"] for item in body["validations"]} == {
        "documents", "toujours"
    }
    assert body["channels"] == ["In-app"]
    assert body["channels_href"] == "/notifications"

    updated = client.put("/api/agent/preferences", json={
        "scope": "secteur",
        "frequency": "hebdomadaire",
        "validation": "toujours",
        "actions": {"prepare_cv": False, "prepare_letter": False},
    }, headers=headers)
    assert updated.status_code == 200, updated.text
    prefs = updated.json()["prefs"]
    assert prefs["scope"] == "secteur"
    assert prefs["frequency"] == "hebdomadaire"
    assert prefs["validation"] == "toujours"
    assert prefs["actions"]["prepare_cv"] is False
    assert prefs["actions"]["prepare_letter"] is False
    assert prefs["actions"]["watch_jobs"] is True

    # Une mise à jour partielle ne réinitialise pas les autres actions.
    again = client.put("/api/agent/preferences", json={
        "actions": {"prepare_interview": False},
    }, headers=headers)
    assert again.status_code == 200, again.text
    final = again.json()["prefs"]["actions"]
    assert final["prepare_cv"] is False
    assert final["prepare_interview"] is False
    assert final["watch_jobs"] is True


def test_agent_preferences_reject_unknown_values(client):
    headers = _candidate(client, "agent.prefs2@orientskill.cm")
    cases = [
        {"scope": "monde"},
        {"frequency": "rare"},
        {"validation": "aucune"},
        {"actions": {"action_inconnue": True}},
        {"actions": "pas-un-dictionnaire"},
        {"mode": "auto"},
    ]
    for payload in cases:
        res = client.put("/api/agent/preferences", json=payload, headers=headers)
        assert res.status_code == 422, (payload, res.text)


def test_agent_preferences_are_candidate_only(client):
    recruiter = _recruiter(client, "agent.rh1@tgc.cm", "Agent RH 1")
    assert client.get(
        "/api/agent/preferences", headers=recruiter
    ).status_code == 403
    assert client.put(
        "/api/agent/preferences",
        json={"scope": "tous"},
        headers=recruiter,
    ).status_code == 403

    admin = _admin_headers(client)
    assert client.get(
        "/api/agent/preferences", headers=admin
    ).status_code == 403
    assert client.put(
        "/api/agent/mode", json={"mode": "veille"}, headers=admin
    ).status_code == 403


def test_autonomous_mode_requires_document_validation(client):
    headers = _candidate(client, "agent.prefs3@orientskill.cm")
    refused = client.put("/api/agent/preferences", json={
        "validation": "toujours",
        "mode": "autonome",
    }, headers=headers)
    assert refused.status_code == 422, refused.text
    assert "validation par document" in refused.json()["detail"]

    # La validation à chaque étape a bien été refusée avec le mode :
    # on l'enregistre seule, puis l'API historique du mode doit refuser
    # le mode autonome.
    saved = client.put("/api/agent/preferences", json={
        "validation": "toujours",
    }, headers=headers)
    assert saved.status_code == 200, saved.text
    refused_mode = client.put(
        "/api/agent/mode", json={"mode": "autonome"}, headers=headers
    )
    assert refused_mode.status_code == 422, refused_mode.text

    accepted = client.put("/api/agent/preferences", json={
        "validation": "documents",
        "mode": "autonome",
    }, headers=headers)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["mode"] == "autonome"

    # Repasser en validation à chaque étape n'est pas rétroactif sur le
    # mode, mais le mode autonome est refusé tant qu'il est actif.
    client.put(
        "/api/agent/preferences",
        json={"validation": "toujours"},
        headers=headers,
    )
    refused_again = client.put(
        "/api/agent/mode", json={"mode": "autonome"}, headers=headers
    )
    assert refused_again.status_code == 422


def test_frequency_and_action_helpers():
    monday = datetime(2026, 10, 26, 10, 0)
    wednesday = datetime(2026, 10, 28, 10, 0)
    daily = SimpleNamespace(agent_prefs={"frequency": "quotidienne"})
    weekly = SimpleNamespace(agent_prefs={"frequency": "hebdomadaire"})
    manual = SimpleNamespace(agent_prefs={"frequency": "manuelle"})
    assert agent_prefs.frequency_allows_auto(daily, wednesday)
    assert agent_prefs.frequency_allows_auto(weekly, monday)
    assert not agent_prefs.frequency_allows_auto(weekly, wednesday)
    assert not agent_prefs.frequency_allows_auto(manual, monday)

    disabled = SimpleNamespace(
        agent_prefs={"actions": {"prepare_cv": False}}
    )
    assert not agent_prefs.action_enabled(disabled, "prepare_cv")
    assert agent_prefs.action_enabled(disabled, "prepare_letter")

    assert agent_prefs.mode_allowed(
        SimpleNamespace(agent_prefs={"validation": "documents"}), "autonome"
    )
    assert not agent_prefs.mode_allowed(
        SimpleNamespace(agent_prefs={"validation": "toujours"}), "autonome"
    )
    assert agent_prefs.mode_allowed(
        SimpleNamespace(agent_prefs={"validation": "toujours"}), "veille"
    )


def test_disabled_actions_block_document_generation(client):
    headers = _candidate(client, "agent.prefs4@orientskill.cm")
    _profile(client, headers)
    recruiter = _recruiter(client, "agent.rh2@tgc.cm", "Agent RH 2")
    job = _job(client, recruiter, "Poste agent 1")

    disabled_cv = client.put("/api/agent/preferences", json={
        "actions": {"prepare_cv": False},
    }, headers=headers)
    assert disabled_cv.status_code == 200, disabled_cv.text
    for url, payload in [
        (f"/api/jobs/{job['id']}/cv", {"template": "classique"}),
        ("/api/cv", {"template": "classique"}),
    ]:
        res = client.post(url, json=payload, headers=headers)
        assert res.status_code == 403, res.text
        assert "réglages d'agent" in res.json()["detail"]

    # La lettre reste autorisée tant qu'elle n'est pas désactivée.
    letter = client.post(
        f"/api/jobs/{job['id']}/cover-letter",
        json={"template": "classique"},
        headers=headers,
    )
    assert letter.status_code == 200, letter.text
    client.put("/api/agent/preferences", json={
        "actions": {"prepare_letter": False},
    }, headers=headers)
    refused_letter = client.post(
        f"/api/jobs/{job['id']}/cover-letter",
        json={"template": "classique"},
        headers=headers,
    )
    assert refused_letter.status_code == 403

    # L'entretien reste autorisé, puis est bloqué à son tour.
    prep = client.post(
        f"/api/jobs/{job['id']}/interview-prep", headers=headers
    )
    assert prep.status_code == 200, prep.text
    client.put("/api/agent/preferences", json={
        "actions": {"prepare_interview": False},
    }, headers=headers)
    refused_prep = client.post(
        f"/api/jobs/{job['id']}/interview-prep", headers=headers
    )
    assert refused_prep.status_code == 403


def test_agent_mode_changes_real_priority(client):
    """Chaque mode a un effet vérifiable sur la prochaine action."""
    headers = _candidate(client, "agent.prefs6@orientskill.cm")
    _profile(client, headers)
    recruiter = _recruiter(client, "agent.rh4@tgc.cm", "Agent RH 4")
    _job(client, recruiter, "Poste Docker", skills=("Docker",))
    _job(client, recruiter, "Poste Kubernetes", skills=("Kubernetes",))

    client.put("/api/agent/mode", json={"mode": "accompagnement"}, headers=headers)
    advice = client.get("/api/dashboard", headers=headers).json()
    assert advice["next_action"]["type"] == "learn"
    assert advice["next_action"]["skill"]

    client.put("/api/agent/mode", json={"mode": "preparation"}, headers=headers)
    preparation = client.get("/api/dashboard", headers=headers).json()
    assert preparation["next_action"]["type"] == "adapt_cv"

    client.put("/api/agent/mode", json={"mode": "veille"}, headers=headers)
    watch = client.get("/api/dashboard", headers=headers).json()
    assert watch["next_action"]["type"] == "apply"


def test_inbox_respects_watch_jobs_action(client):
    headers = _candidate(client, "agent.prefs5@orientskill.cm")
    _profile(client, headers)
    recruiter = _recruiter(client, "agent.rh3@tgc.cm", "Agent RH 3")
    _job(client, recruiter, "Poste agent 2")

    with_watch = client.get("/api/inbox", headers=headers)
    assert with_watch.status_code == 200, with_watch.text
    assert any(e["kind"] == "new_job" for e in with_watch.json())

    client.put("/api/agent/preferences", json={
        "actions": {"watch_jobs": False},
    }, headers=headers)
    without_watch = client.get("/api/inbox", headers=headers)
    assert without_watch.status_code == 200, without_watch.text
    assert not any(
        e["kind"] in {"new_job", "strong_match", "learning"}
        for e in without_watch.json()
    )
