"""Hachage de mot de passe (PBKDF2-HMAC-SHA256, hashlib) et jetons JWT (PyJWT)."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import config, models
from app.database import get_db

_PBKDF2_ITERATIONS = 60_000


def hash_password(password: str) -> str:
    """Retourne `salt$hash` (hexadécimal), PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, expected = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(digest.hex(), expected)


def create_token(user_id: int, minutes: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    expires = timedelta(minutes=minutes) if minutes else timedelta(hours=config.TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + expires,
    }
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, config.SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None


_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> models.User:
    """Authentification obligatoire : 401 si le jeton est absent ou invalide."""
    user = _resolve_user(db, creds)
    if user is None:
        raise HTTPException(status_code=401, detail="Non authentifié ou jeton invalide")
    return user


def get_optional_user(
    db: Session = Depends(get_db),
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[models.User]:
    """Authentification optionnelle : None si pas de jeton valide (endpoints publics)."""
    return _resolve_user(db, creds)


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    """Accès réservé au rôle ``admin`` (403 sinon)."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs")
    return user


def _resolve_user(
    db: Session, creds: Optional[HTTPAuthorizationCredentials]
) -> Optional[models.User]:
    if creds is None:
        return None
    user_id = decode_token(creds.credentials)
    if user_id is None:
        return None
    return db.get(models.User, user_id)
