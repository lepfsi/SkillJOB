"""Tests « pleins pouvoirs » de l'agent : contexte LLM enrichi (formations
avec liens, métiers, candidatures), écarts orientés métiers, accès web
borné (analyse d'une URL fournie par l'utilisateur), liens markdown."""


def _demo_headers(client):
    login = client.post("/api/auth/login", json={
        "email": "demo@orientskill.cm", "password": "demo1234",
    })
    return {"Authorization": f"Bearer {login.json()['token']}"}


def _ask(client, headers, message):
    response = client.post("/api/assistant", json={
        "message": message, "history": [],
    }, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def test_assistant_gaps_are_career_oriented(client):
    """Fin du contresens « Excel pour un technicien réseau » : les écarts
    suivent les MÉTIERS recommandés du profil (IT), pas toutes les offres."""
    body = _ask(client, _demo_headers(client),
                "Quelles compétences me manquent ?")
    reply = body["reply"].lower()
    assert "métiers recommandés" in reply
    # Les écarts du profil démo (IT réseau) : Cisco, Azure, cybersécurité…
    # — pas de compétences hors domaine en tête de liste.
    assert "excel" not in reply.split("\n")[0].lower()


def test_assistant_formations_include_real_links(client):
    """« Quelles formations ? » renvoie les LIENS réels (markdown + links)."""
    body = _ask(client, _demo_headers(client),
                "Quelles formations me conseilles-tu ?")
    assert "](http" in body["reply"], body["reply"]  # lien markdown
    external = [l for l in body["links"] if l["href"].startswith("http")]
    assert external, "au moins un lien externe vers une plateforme"


def test_assistant_specific_formation_links(client):
    body = _ask(client, _demo_headers(client),
                "Quelles formations suivre pour Cisco ?")
    assert "cisco" in body["reply"].lower()
    assert "](http" in body["reply"]
    assert any("netacad" in l["href"] or "coursera" in l["href"] or "http" in l["href"]
               for l in body["links"])


def test_context_document_contains_formations_and_careers(client):
    """Le document de contexte transmis au LLM contient TOUT : métiers,
    écarts, formations AVEC URL, candidatures. C'est ce qui donne à
    l'agent ses pouvoirs même en mode LLM."""
    from app import models
    from app.database import SessionLocal
    from app.services.assistant import _Context
    from app.services.profile_store import get_profile_row, profile_to_dict
    from app.services.skills_taxonomy import load_taxonomy
    from app.api.assistant import _resources_map

    db = SessionLocal()
    try:
        user = db.query(models.User).filter_by(email="demo@orientskill.cm").first()
        profile = profile_to_dict(get_profile_row(db, user.id), user.id)
        ctx = _Context(
            profile, db.query(models.Job).all(), db.query(models.Career).all(),
            load_taxonomy(), resources=_resources_map(db),
            applications=[{"job_title": "X", "status": "entretien"}],
            verified=True,
        )
        doc = ctx.context_document()
        assert "MÉTIER RECOMMANDÉ" in doc
        assert "ÉCARTS PRIORITAIRES" in doc
        assert "FORMATIONS DISPONIBLES" in doc
        assert "](http" in doc              # liens markdown exacts
        assert "CANDIDATURES" in doc
        assert "identité vérifiée" in doc
    finally:
        db.close()


def test_assistant_fetches_user_provided_url(client, monkeypatch):
    """Accès internet BORNÉ : l'utilisateur colle une URL, l'agent lit
    la page (une seule, timeout court) et en fait un résumé honnête."""
    from app.services import assistant as assistant_service

    HTML = """<html><head><title>Offre Administrateur Systèmes</title>
    <meta name="description" content="Nous recrutons un administrateur
    systèmes et réseaux confirmé à Douala, CDI, compétences Linux et
    virtualisation."></head><body>x</body></html>"""

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, limit=None):
            return HTML.encode("utf-8")

    def fake_urlopen(req, timeout=10):
        return FakeResponse()

    monkeypatch.setattr(assistant_service.urllib.request, "urlopen", fake_urlopen)

    body = _ask(client, _demo_headers(client),
                "Que penses-tu de cette offre ? https://exemple.cm/offre/42")
    reply = body["reply"]
    assert "Administrateur Systèmes" in reply
    assert "page" in reply.lower()
    assert any(l["href"] == "https://exemple.cm/offre/42" for l in body["links"])


def test_assistant_url_fetch_failure_is_honest(client, monkeypatch):
    """Échec réseau : réponse honnête, pas d'invention."""
    from app.services import assistant as assistant_service

    def fake_urlopen(req, timeout=10):
        raise OSError("DNS unreachable")

    monkeypatch.setattr(assistant_service.urllib.request, "urlopen", fake_urlopen)
    body = _ask(client, _demo_headers(client),
                "analyse https://site-injoignable.cm")
    assert "pas pu ouvrir" in body["reply"]


# ------------------------------------- Agent conversationnel + web

def test_greeting_is_casual_not_a_report(client):
    """« Bonjour » → une vraie salutation, pas un état des lieux."""
    body = _ask(client, _demo_headers(client), "Bonjour")
    reply = body["reply"]
    assert reply.startswith("Salut")
    assert len(reply) < 250           # conversation, pas un dump
    assert "correspondance" not in reply.lower()
    assert "écarts" not in reply.lower()


def test_detect_search_queries():
    from app.services.assistant import _detect_search

    q = _detect_search("Cherche-moi des informations sur les bourses MINFOP")
    assert q and "bourses" in q and "MINFOP" in q
    assert _detect_search("Quelles sont mes compétences ?") is None


def test_web_search_parsing(client, monkeypatch):
    """Fouille web : DuckDuckGo HTML → titres + vraies URL dépliées."""
    from app.services import assistant as svc

    HTML = """
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.minfop.gov.cm%2Fbourses&rut=abc">Bourses MINFOP 2026</a>
    <a class="result__snippet">Conditions d'éligibilité et calendrier officiel.</a>
    """
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self, limit=None):
            return HTML.encode("utf-8")

    monkeypatch.setattr(svc.urllib.request, "urlopen", lambda req, timeout=10: FakeResponse())
    results = svc._web_search("bourses minfop")
    assert len(results) == 1
    assert results[0]["url"] == "https://www.minfop.gov.cm/bourses"
    assert results[0]["title"] == "Bourses MINFOP 2026"
    assert "éligibilité" in results[0]["snippet"]


def test_search_request_returns_web_results(client, monkeypatch):
    """« Cherche-moi X » : l'agent fouille le web et répond AVEC liens,
    même sans LLM configuré (moteur de règles)."""
    from app.services import assistant as svc

    HTML = """
    <a class="result__a" href="https://www.emploi.cm/offre/123">Offre technicien Douala</a>
    <a class="result__snippet">Poste de technicien support à Douala, CDI.</a>
    """
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self, limit=None):
            return HTML.encode("utf-8")

    monkeypatch.setattr(svc.urllib.request, "urlopen", lambda req, timeout=10: FakeResponse())
    body = _ask(client, _demo_headers(client),
                "Cherche-moi des offres de technicien support sur internet")
    assert "trouvé sur le web" in body["reply"]
    assert "](https://" in body["reply"]
    assert any(l["href"].startswith("https://") for l in body["links"])


def test_web_search_failure_is_honest(client, monkeypatch):
    from app.services import assistant as svc

    def boom(req, timeout=10):
        raise OSError("no network")

    monkeypatch.setattr(svc.urllib.request, "urlopen", boom)
    body = _ask(client, _demo_headers(client),
                "cherche les actualités sur l'emploi au Cameroun")
    # Pas de résultats web → réponse normale du moteur (pas de plantage,
    # pas de résultats inventés)
    assert "reply" in body
    assert "trouvé sur le web" not in body["reply"]


# ------------------------------------- Actions réelles de l'agent

def test_cv_intent_proposes_actions(client):
    """« Prépare mon CV » : Ori propose de GÉNÉRER le CV (bouton d'action),
    pas seulement d'ouvrir la page."""
    body = _ask(client, _demo_headers(client), "Prépare mon CV pour mon meilleur match")
    actions = body.get("actions", [])
    types = [a["type"] for a in actions]
    assert "generate_cv" in types and "generate_letter" in types
    assert all(a.get("job_id") for a in actions)


def test_interview_intent_proposes_simulation(client):
    body = _ask(client, _demo_headers(client), "Prépare mon entretien")
    actions = body.get("actions", [])
    assert any(a["type"] == "interview_prep" for a in actions)


def test_no_profile_reply_proposes_building(client):
    """Sans profil : Ori propose de CONSTRUIRE le profil ensemble
    (l'utilisateur garde le contrôle : questionnaire + validation)."""
    client.post("/api/auth/register", json={
        "email": "no.profile@example.cm", "password": "pass1234",
        "full_name": "Sans Profil", "gender": "homme"})
    tok = client.post("/api/auth/login", json={
        "email": "no.profile@example.cm", "password": "pass1234"}).json()["token"]
    body = _ask(client, {"Authorization": f"Bearer {tok}"},
                "Quels métiers puis-je viser ?")
    assert "profil" in body["reply"].lower()
    assert "construit ensemble" in body["reply"]
    assert any(a["type"] == "build_profile" for a in body.get("actions", []))


def test_actions_always_present(client):
    body = _ask(client, _demo_headers(client), "bonjour")
    assert isinstance(body.get("actions", []), list)


def test_llm_links_become_buttons(client):
    """Robustesse : les liens markdown cités dans une réponse (mode LLM)
    sont extraits en boutons cliquables, même en texte brut."""
    from app.services import assistant as svc
    from app.services.assistant import answer

    fake_reply = (
        "Pour Cisco, commence par [CCNA intro](https://www.netacad.com/x) "
        "puis [AZ-900](https://learn.microsoft.com/y)."
    )
    original = svc.llm_client.chat_completion

    class _Cfg:
        enabled = True

    svc.llm_client.get_llm_config = lambda db: {"enabled": True}
    svc.llm_client.chat_completion = lambda db, messages, max_tokens=450: fake_reply
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        res = answer(
            "formations", [], None, [], [], None, db=db, role="candidate",
        )
    finally:
        svc.llm_client.chat_completion = original
        svc.llm_client.get_llm_config = lambda db: {"enabled": False}
        db.close()
    hrefs = [l["href"] for l in res["links"]]
    assert "https://www.netacad.com/x" in hrefs
    assert "https://learn.microsoft.com/y" in hrefs


# --------------------- Mode moteur + bilan + remises à niveau

def test_response_reports_engine_mode(client):
    """Confidentialité : l'utilisateur NE SAIT PAS s'il y a un modèle
    derrière (mode neutre « orientskill »). Seul l'admin voit la réalité."""
    body = _ask(client, _demo_headers(client), "bonjour")
    assert body["mode"] == "orientskill"

    # L'admin, lui, connaît le moteur réel
    login = client.post("/api/auth/login", json={
        "email": "admin@orientskill.cm", "password": "admin1234"})
    aheaders = {"Authorization": f"Bearer {login.json()['token']}"}
    body = _ask(client, aheaders, "bonjour")
    assert body["mode"] == "local"  # pas de modèle configuré dans les tests


def test_assistant_status_endpoint(client):
    # Non-admin : AUCUNE information sur le modèle (ne sait même pas
    # s'il y en a un)
    response = client.get("/api/assistant/status",
                          headers=_demo_headers(client))
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "orientskill"
    assert "llm_enabled" not in body
    assert "model" not in body

    # Admin : réalité complète
    login = client.post("/api/auth/login", json={
        "email": "admin@orientskill.cm", "password": "admin1234"})
    aheaders = {"Authorization": f"Bearer {login.json()['token']}"}
    body = client.get("/api/assistant/status", headers=aheaders).json()
    assert body["llm_enabled"] is False
    assert body["mode"] == "local"


def test_bilan_intent_uses_observed_data(client):
    """« C'est à toi de me dire, d'après ce que tu observes » : Ori
    résume ce qu'il voit (métiers, piste, écarts), pas une liste creuse."""
    body = _ask(client, _demo_headers(client),
                "C'est à toi de me dire, basé sur ce que tu as observé autour de moi")
    reply = body["reply"]
    assert "colle bien" in reply.lower()
    assert "Technicien" in reply or "Administrateur" in reply
    assert "On commence par quoi ?" in reply


def test_remises_en_niveau_triggers_formations(client):
    """« remises en niveau » est compris comme une demande de formation."""
    body = _ask(client, _demo_headers(client),
                "Quelles sont les remises en niveau dispo ?")
    assert "prioritaires" in body["reply"] or "écarts" in body["reply"]
    assert "Apprentissage" in [l["label"] for l in body["links"]] or \
           any(l["href"] == "/learning" for l in body["links"])


def test_internet_followup_uses_previous_question(client, monkeypatch):
    """« Et sur internet il y a rien ? » : la recherche porte sur la
    question précédente (remises en niveau), pas sur du vide."""
    from app.services import assistant as svc

    HTML = '<a class="result__a" href="https://exemple.cm/formation">Formation remise à niveau</a><a class="result__snippet">Programme de remise à niveau en informatique.</a>'

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def read(self, limit=None):
            return HTML.encode("utf-8")

    captured = {}
    def fake_urlopen(req, timeout=10):
        captured["url"] = req.full_url if hasattr(req, "full_url") else str(req)
        return FakeResponse()

    monkeypatch.setattr(svc.urllib.request, "urlopen", fake_urlopen)
    body = _ask_with_history(client, _demo_headers(client),
                             "Quelles sont les remises en niveau dispo ?",
                             "Et sur internet il y a rien ?")
    assert "trouvé sur le web" in body["reply"]
    assert "remise" in captured.get("url", "").lower() or "niveau" in captured.get("url", "").lower()


def _ask_with_history(client, headers, previous, message):
    response = client.post("/api/assistant", json={
        "message": message,
        "history": [{"role": "user", "content": previous},
                    {"role": "assistant", "content": "réponse précédente"}],
    }, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# --------------------- Agent recruteur + compréhension

def _recruiter_headers_v2(client, email="agent.recruiter@tgc.cm"):
    reg = client.post("/api/auth/register/recruiter", json={
        "email": email, "password": "pass1234",
        "recruiter_type": "company",
        "company_name": "Agent RH CM",
        "company_sector": "Informatique / IT",
        "company_description": "Test agent.",
        "company_location": "Douala",
    })
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def test_recruiter_agent_talent_search(client):
    rh = _recruiter_headers_v2(client)
    body = _ask(client, rh,
                "Montre-moi les talents disponibles en réseaux et firewall")
    assert "talents" in body["reply"].lower() or "compétences" in body["reply"].lower()
    # Lien vers la recherche pré-remplie avec les compétences détectées
    talent_links = [l for l in body["links"] if "/recruiter/candidates" in l["href"]]
    assert talent_links
    assert "skills=" in talent_links[0]["href"]
    # Suggestions adaptées au rôle recruteur
    assert any("offre" in s.lower() for s in body["suggestions"])


def test_recruiter_agent_received_applications(client):
    rh = _recruiter_headers_v2(client, email="agent2@tgc.cm")
    body = _ask(client, rh, "Où en sont les candidatures reçues ?")
    assert "candidatures" in body["reply"].lower()
    assert any("/recruiter" in l["href"] for l in body["links"])


def test_recruiter_agent_offer_writing(client):
    rh = _recruiter_headers_v2(client, email="agent3@tgc.cm")
    body = _ask(client, rh, "Comment rédiger une offre claire ?")
    assert "compétences" in body["reply"].lower()
    assert any("/recruiter/jobs" in l["href"] for l in body["links"])


def test_pending_dashboard_intent(client):
    """« ce qu'il y a de pending sur mon dashboard, tâches non accomplies »
    → vrai bilan des tâches en cours, pas un fallback."""
    body = _ask(client, _demo_headers(client),
                "Parle moi de ce qu'il y a de pending sur mon dashboard ou des tâches que je n'ai pas accomplies")
    reply = body["reply"]
    assert "Administrateur Systèmes" in reply or "En cours" in reply
    assert "On commence par quoi ?" in reply
    assert "pas saisi" not in reply.lower()


def test_continuation_replays_previous_request(client):
    """« Vas-y génère la réponse complète » après une réponse tronquée :
    l'agent relance la demande précédente au lieu de tomber en fallback."""
    body = client.post("/api/assistant", json={
        "message": "Vas-y génère la réponse complète",
        "history": [
            {"role": "user", "content": "Parle moi de ce qu'il y a de pending sur mon dashboard"},
            {"role": "assistant", "content": "Côté candidatures, tu as ton dossier d'Administrateur Systèmes et"},
        ],
    }, headers=_demo_headers(client))
    assert body.status_code == 200
    reply = body.json()["reply"]
    assert "pas saisi" not in reply.lower()
    assert "pas compris" not in reply.lower()
    # La réponse régénère le contenu du bilan de la question précédente
    assert "On commence par quoi ?" in reply or "candidature" in reply.lower()
