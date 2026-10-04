"""Tests V1.3 : référentiels Cameroun (géo, programmes publics,
entrepreneuriat) et messagerie recruteur ↔ talent."""
import io
import time


def _png_bytes() -> bytes:
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
        "53de0000000c4944415408d763f8cfc0f01f0005050202a5cd1a33000000004"
        "9454e44ae426082"
    )


def test_geo_cameroon(client):
    response = client.get("/api/geo")
    assert response.status_code == 200
    data = response.json()
    regions = [r["name"] for r in data["regions"]]
    # Les 10 régions du Cameroun
    assert set(regions) == {
        "Adamaoua", "Centre", "Est", "Extrême-Nord", "Littoral",
        "Nord", "Nord-Ouest", "Ouest", "Sud", "Sud-Ouest",
    }
    centre = next(r for r in data["regions"] if r["name"] == "Centre")
    deps = [d["name"] for d in centre["departments"]]
    assert "Mfoundi" in deps
    wouri = next(
        d for r in data["regions"] if r["name"] == "Littoral"
        for d in r["departments"] if d["name"] == "Wouri"
    )
    assert "Douala I" in wouri["arrondissements"]


def test_register_with_geo(client):
    response = client.post("/api/auth/register", json={
        "email": "geo.test@example.cm", "password": "pass1234",
        "full_name": "Paul Mbarga", "gender": "homme",
        "region": "Littoral", "department": "Wouri",
        "arrondissement": "Douala V", "city": "Douala",
    })
    assert response.status_code == 201
    user = response.json()["user"]
    assert user["region"] == "Littoral"
    assert user["department"] == "Wouri"
    assert user["arrondissement"] == "Douala V"
    assert user["city"] == "Douala"


def test_education_levels_cover_all_profiles(demo_headers, client):
    """CEP, FSLC, GCE, ingénieur et parcours sans diplôme sont proposés."""
    questionnaire = client.get("/api/questionnaire").json()
    levels = next(
        q["options"] for s in questionnaire["steps"] if s["id"] == "formation"
        for q in s["questions"] if q["id"] == "q_education_level"
    )
    labels = " ".join(levels)
    assert "CEP" in labels
    assert "First School Leaving Certificate" in labels
    assert "GCE Advanced Level" in labels
    assert "ingénieur" in labels
    assert "recyclage" in labels
    assert "sans diplôme" in labels


def test_institutional_programs(client):
    response = client.get("/api/institutional")
    assert response.status_code == 200
    items = response.json()
    categories = {i["category"] for i in items}
    # Refonte : concours (avec sous-catégories), FNE, MINFOP, MINPME
    assert {"fne", "minfop", "minpme", "concours"} <= categories
    concours = [i for i in items if i["category"] == "concours"]
    subs = {i["subcategory"] for i in concours}
    assert {"fonction_publique", "grandes_ecoles", "sante", "forets_faune", "armees"} <= subs
    fp = next(i for i in concours if i["subcategory"] == "fonction_publique")
    assert "fonction publique" in fp["subcategory_label"].lower()

    # Filtre par catégorie
    minfop = client.get("/api/institutional?category=minfop").json()
    assert all(i["category"] == "minfop" for i in minfop)


def test_entrepreneurship_space(client):
    response = client.get("/api/entrepreneurship")
    assert response.status_code == 200
    data = response.json()
    kinds = {r["kind"] for r in data["resources"]}
    assert {"concours", "accompagnement", "financement", "formation"} <= kinds
    # Préparation bancaire : répertoire documenté des exigences des banques
    steps = {b["step"] for b in data["bank_prep"]}
    assert "Business plan complet" in steps
    assert "Garanties" in steps


def _recruiter_and_candidate(client):
    reg = client.post("/api/auth/register/recruiter", json={
        "email": "recruteur.msg@tgc.cm", "password": "pass1234",
        "full_name": "RH Test", "gender": "femme",
        "company_name": "Messagerie CM",
        "company_sector": "Informatique / IT",
        "company_description": "Test.",
        "company_location": "Douala",
        "region": "Littoral", "department": "Wouri",
        "arrondissement": "Douala I", "city": "Douala",
    })
    assert reg.status_code == 201
    rheaders = {"Authorization": f"Bearer {reg.json()['token']}"}
    login = client.post("/api/auth/login", json={
        "email": "demo@orientskill.cm", "password": "demo1234",
    })
    cheaders = {"Authorization": f"Bearer {login.json()['token']}"}
    return rheaders, cheaders


def test_messaging_flow(client):
    rheaders, cheaders = _recruiter_and_candidate(client)

    # Le recruteur contacte le talent (id 1 = demo)
    sent = client.post("/api/messages", json={
        "recipient_id": 1,
        "body": "Bonjour, votre profil correspond à notre poste de technicien. Êtes-vous disponible pour un échange ?",
    }, headers=rheaders)
    assert sent.status_code == 201, sent.text
    msg = sent.json()
    assert msg["recipient_id"] == 1 and not msg["read"]

    # Non-lus visibles côté candidat
    unread = client.get("/api/messages/unread-count", headers=cheaders).json()
    assert unread["count"] >= 1

    # Fil de conversations côté candidat : identité recruteur visible
    threads = client.get("/api/messages", headers=cheaders).json()
    thread = next(t for t in threads if t["other_user_id"] == msg["sender_id"])
    assert thread["unread"] >= 1
    assert thread["other_company"] and thread["other_company"]["name"] == "Messagerie CM"

    # Le fil complet marque comme lu et révèle l'identité de l'expéditeur
    full = client.get(f"/api/messages/{msg['sender_id']}", headers=cheaders)
    assert full.status_code == 200
    body = full.json()
    assert all(m["read"] for m in body["messages"])
    assert body["identity"]["company"]["name"] == "Messagerie CM"
    assert body["identity"]["role"] == "recruiter"
    unread = client.get("/api/messages/unread-count", headers=cheaders).json()
    assert unread["count"] == 0

    # Le candidat répond
    reply = client.post("/api/messages", json={
        "recipient_id": msg["sender_id"],
        "body": "Bonjour, oui avec plaisir.",
    }, headers=cheaders)
    assert reply.status_code == 201

    # Un candidat ne peut pas écrire à un autre candidat
    client.post("/api/auth/register", json={
        "email": "autre.candidat@example.cm", "password": "pass1234",
        "full_name": "Autre Candidat",
    })
    login2 = client.post("/api/auth/login", json={
        "email": "autre.candidat@example.cm", "password": "pass1234",
    })
    h2 = {"Authorization": f"Bearer {login2.json()['token']}"}
    forbidden = client.post("/api/messages", json={
        "recipient_id": 1, "body": "salut",
    }, headers=h2)
    assert forbidden.status_code == 403


def test_recruiter_candidates_visible_with_verification_state(client):
    """La carte de profil côté recruteur : pas d'email exposé, état de
    vérification visible, matching explicable."""
    reg = client.post("/api/auth/register/recruiter", json={
        "email": "recruteur.card@tgc.cm", "password": "pass1234",
        "full_name": "RH Card", "gender": "homme",
        "company_name": "Card CM",
        "company_sector": "IT",
        "company_description": "Test.",
        "company_location": "Douala",
    })
    rheaders = {"Authorization": f"Bearer {reg.json()['token']}"}
    candidates = client.get("/api/recruiter/candidates", headers=rheaders).json()
    assert candidates
    for c in candidates:
        assert "email" not in c          # coordonnées non exposées
        assert "verified" in c            # badge de vérification
        assert "match" in c               # explication
