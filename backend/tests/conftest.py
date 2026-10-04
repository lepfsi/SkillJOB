import os
import sys
import tempfile
from pathlib import Path

# Base de données isolée pour les tests (avant tout import de l'app)
_tmpdb = Path(tempfile.mkdtemp(prefix="orientskill-test-")) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdb.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret"

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
