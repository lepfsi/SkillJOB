"""Configuration de l'application, pilotée par les variables d'environnement."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]          # backend/
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "skilljob.db"

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")

JWT_ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "168"))  # 7 jours

# Assistant conversationnel : moteur hybride règles + LLM optionnel
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "rules")       # "rules" | "openai"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
