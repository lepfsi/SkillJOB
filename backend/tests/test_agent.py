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
