"""Console admin : suspension de comptes et catalogue de formations.

- Un compte banni ne peut plus se connecter (motif communiqué), et son
  jeton existant est refusé sur toute l'API authentifiée.
- Les formations ajoutées en console (source « admin ») apparaissent
  dans le catalogue ET survivent à la synchronisation du référentiel.
"""
from app import models
from app.database import SessionLocal
from app.main import sync_learning_resources


def _register(client, email):
    reg = client.post("/api/auth/register", json={
        "email": email, "password": "pass1234", "full_name": "Banny Test",
    })
    assert reg.status_code == 201, reg.text
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def test_admin_bans_user_and_login_is_refused(client, admin_headers):
    """Bannissement : connexion refusée avec le motif, API verrouillée."""
    headers = _register(client, "candidat.banni@orientskill.cm")
    assert client.get("/api/dashboard", headers=headers).status_code == 200

    me = client.get("/api/auth/me", headers=headers).json()
    ban = client.put(f"/api/admin/users/{me['id']}/ban", json={
        "reason": "Compte de test banni pour vérification",
    }, headers=admin_headers)
    assert ban.status_code == 200, ban.text
    assert ban.json()["is_banned"] is True

    # Le jeton existant est refusé sur l'espace authentifié.
    blocked = client.get("/api/dashboard", headers=headers)
    assert blocked.status_code == 403
    assert "Compte suspendu" in blocked.json()["detail"]

    # La connexion est refusée avec le motif.
    login = client.post("/api/auth/login", json={
        "email": "candidat.banni@orientskill.cm", "password": "pass1234",
    })
    assert login.status_code == 403
    assert "banni pour vérification" in login.json()["detail"]

    # La suspension se lève : l'utilisateur se reconnecte.
    unban = client.delete(f"/api/admin/users/{me['id']}/ban",
                          headers=admin_headers)
    assert unban.status_code == 200, unban.text
    login2 = client.post("/api/auth/login", json={
        "email": "candidat.banni@orientskill.cm", "password": "pass1234",
    })
    assert login2.status_code == 200, login2.text
    assert client.get("/api/dashboard", headers=headers).status_code == 200


def test_admin_cannot_ban_admin_or_without_reason(client, admin_headers):
    """Un compte admin ne peut être banni ; le motif est obligatoire."""
    me = client.get("/api/auth/me", headers=admin_headers).json()
    ban_self = client.put(f"/api/admin/users/{me['id']}/ban", json={
        "reason": "Auto-suspension interdite",
    }, headers=admin_headers)
    assert ban_self.status_code == 400

    headers = _register(client, "candidat.banni2@orientskill.cm")
    uid = client.get("/api/auth/me", headers=headers).json()["id"]
    no_reason = client.put(f"/api/admin/users/{uid}/ban", json={
        "reason": "ok",
    }, headers=admin_headers)
    assert no_reason.status_code == 422

    # Nettoyage : le compte reste actif.
    assert client.get("/api/dashboard", headers=headers).status_code == 200


def test_admin_learning_crud_and_candidate_visibility(
    client, admin_headers
):
    """Ajout de formation en console : visible, modifiable, supprimable."""
    # Compétence absente du référentiel JSON : la formation console est
    # la seule ressource pour cette compétence, donc toujours proposée.
    payload = {
        "skill": "Ergonomie des postes de travail",
        "title": "Aménager un espace de bureaux sain et productif",
        "provider": "Console Test",
        "type": "course",
        "url": "https://exemple.cm/ergonomie",
    }
    created = client.post("/api/admin/learning", json=payload,
                          headers=admin_headers)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["source"] == "admin"

    listed = client.get("/api/admin/learning?skill=Ergonomie",
                        headers=admin_headers).json()
    assert any(r["id"] == row["id"] for r in listed)

    # Les doublons (même compétence + intitulé) sont refusés.
    dup = client.post("/api/admin/learning", json=payload,
                      headers=admin_headers)
    assert dup.status_code == 400

    # Mise à jour en console.
    updated = client.put(f"/api/admin/learning/{row['id']}", json={
        "provider": "Console Test Pro",
    }, headers=admin_headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["provider"] == "Console Test Pro"

    # La formation apparaît dans le plan du candidat qui vise la compétence.
    headers = _register(client, "candidat.learnadmin@orientskill.cm")
    client.put("/api/profile", json={
        "title": "Assistant administratif",
        "summary": "Profil test formations admin.",
        "skills": [
            {"skill": "Ergonomie des postes de travail",
             "proficiency": "debutant"},
        ],
        "preferences": {"target_roles": ["Assistant administratif"]},
    }, headers=headers)
    plan = client.get("/api/learning", headers=headers).json()
    all_resources = [
        res
        for section in ("learn_now", "improve", "learn_next")
        for item in plan.get(section, [])
        for res in item.get("resources", [])
    ]
    assert any(
        r["title"] == "Aménager un espace de bureaux sain et productif"
        for r in all_resources
    ), plan

    # Suppression.
    deleted = client.delete(f"/api/admin/learning/{row['id']}",
                            headers=admin_headers)
    assert deleted.status_code == 200
    listed2 = client.get("/api/admin/learning?skill=Ergonomie",
                          headers=admin_headers).json()
    assert not any(r["id"] == row["id"] for r in listed2)


def test_learning_sync_preserves_admin_rows(client, admin_headers):
    """La synchronisation du démarrage ne touche pas les lignes « admin »."""
    created = client.post("/api/admin/learning", json={
        "skill": "Synchro Test",
        "title": "Formation qui doit survivre à la synchronisation",
        "provider": "Console",
        "type": "free",
        "url": "https://exemple.cm/survivre",
    }, headers=admin_headers)
    assert created.status_code == 201, created.text
    row_id = created.json()["id"]

    db = SessionLocal()
    try:
        sync_learning_resources(db)
        row = db.get(models.LearningResource, row_id)
        assert row is not None, "la ligne admin ne doit pas être supprimée"
        assert row.source == "admin"
        assert row.url == "https://exemple.cm/survivre"
    finally:
        db.close()

    # Nettoyage.
    client.delete(f"/api/admin/learning/{row_id}", headers=admin_headers)


def test_referential_learning_rows_can_be_corrected_and_hidden(
    client, admin_headers
):
    """Un lien cassé du référentiel peut être corrigé ou retiré.

    La correction transforme la ligne en version console (elle survit à
    la synchronisation). Le retrait masque la ligne : elle ne réapparaît
    pas au démarrage, mais reste rétablissable depuis la console.
    """
    listed = client.get("/api/admin/learning", headers=admin_headers).json()
    ref = next((r for r in listed if r["source"] == "referentiel"), None)
    if ref is None:
        return  # référentiel vide dans cet environnement

    original_title = ref["title"]
    updated = client.put(f"/api/admin/learning/{ref['id']}", json={
        "url": "https://exemple.cm/lien-corrige",
    }, headers=admin_headers)
    assert updated.status_code == 200, updated.text
    assert updated.json()["source"] == "admin"
    assert updated.json()["url"] == "https://exemple.cm/lien-corrige"

    db = SessionLocal()
    try:
        sync_learning_resources(db)
        row = db.get(models.LearningResource, ref["id"])
        assert row is not None
        assert row.source == "admin"
        assert row.url == "https://exemple.cm/lien-corrige"
    finally:
        db.close()

    removed = client.delete(f"/api/admin/learning/{ref['id']}",
                            headers=admin_headers)
    assert removed.status_code == 200, removed.text
    assert removed.json()["hidden"] is True

    db = SessionLocal()
    try:
        sync_learning_resources(db)
        row = db.get(models.LearningResource, ref["id"])
        assert row is not None, "la tombstone ne doit pas disparaître"
        assert row.hidden is True

        from app.services.learning import visible_resources
        catalog = visible_resources(db)
        assert all(
            item["title"] != original_title
            for items in catalog.values()
            for item in items
        ), "une formation masquée ne doit jamais être proposée"
    finally:
        db.close()

    restored = client.post(f"/api/admin/learning/{ref['id']}/restore",
                           headers=admin_headers)
    assert restored.status_code == 200, restored.text
    assert restored.json()["hidden"] is False
    assert restored.json()["title"] == original_title

    # Renommer une ligne du référentiel crée une tombstone masquée sur
    # l'ancienne clé : le référentiel ne peut pas ressusciter l'entrée
    # d'origine au démarrage suivant.
    renamed = client.put(f"/api/admin/learning/{ref['id']}", json={
        "title": f"{original_title} (corrigée)",
    }, headers=admin_headers)
    assert renamed.status_code == 200, renamed.text
    db = SessionLocal()
    try:
        tombstone = (
            db.query(models.LearningResource)
            .filter(
                models.LearningResource.skill == ref["skill"],
                models.LearningResource.title == original_title,
            )
            .first()
        )
        assert tombstone is not None
        assert tombstone.hidden is True
    finally:
        db.close()
