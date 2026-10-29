import os
import sys
import tempfile
from pathlib import Path

# Base de données isolée pour les tests (avant tout import de l'app)
_tmpdir = Path(tempfile.mkdtemp(prefix="orientskill-test-"))
_tmpdb = _tmpdir / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdb.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret"
# Pas de collecte autonome pendant les tests : les sources de test ne
# doivent jamais lancer de requêtes réseau imprévues.
os.environ["SOURCE_SCHEDULER_ENABLED"] = "0"
# Le planificateur de digest/alertes ne doit jamais tourner pendant les
# tests : il enverrait des notifications et créerait des courses avec les
# données de test.
os.environ["DIGEST_SCHEDULER_ENABLED"] = "0"
# Dépôts (photos, pièces) ISOLÉS : jamais le dossier réel de l'utilisateur.
os.environ["UPLOAD_DIR"] = str(_tmpdir / "uploads")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def demo_headers(client):
    response = client.post("/api/auth/login", json={
        "email": "demo@orientskill.cm",
        "password": "demo1234",
    })
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    login = client.post("/api/auth/login", json={
        "email": "admin@orientskill.cm", "password": "admin1234",
    })
    assert login.status_code == 200, login.text
    token = login.json()["token"]
    return {"Authorization": f"Bearer {token}"}
