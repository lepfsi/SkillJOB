"""Configuration de l'application, pilotée par les variables d'environnement."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]          # backend/
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "skilljob.db"

# Dossier des fichiers déposés (photos de profil, pièces de vérification).
# Surchargé par UPLOAD_DIR : les tests et le smoke y pointent un bac à
# sable, jamais le dossier réel de l'utilisateur.
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR") or (BASE_DIR / "uploads"))

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")

# URL publique du frontend : sert aux liens profonds envoyés par e-mail
# (invitations à un entretien, etc.). En production, définir PUBLIC_BASE_URL.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5190")

JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "168"))  # 7 jours

# Assistant conversationnel : moteur hybride règles + LLM optionnel
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "rules")       # "rules" | "openai"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# Collecte autonome des sources RSS/JSON. Le planificateur tourne dans un
# thread daemon et interroge chaque source activée selon son intervalle.
SOURCE_SCHEDULER_ENABLED = os.getenv(
    "SOURCE_SCHEDULER_ENABLED", "1"
).strip().lower() not in {"0", "false", "no", "off"}
SOURCE_SCHEDULER_TICK_SECONDS = max(
    15, int(os.getenv("SOURCE_SCHEDULER_TICK_SECONDS", "60"))
)

# Digest et alertes planifiées : le thread démarre avec l'application.
# Les tests et le smoke le désactivent pour éviter tout envoi réel et
# toute course avec les données de test.
DIGEST_SCHEDULER_ENABLED = os.getenv(
    "DIGEST_SCHEDULER_ENABLED", "1"
).strip().lower() not in {"0", "false", "no", "off"}
