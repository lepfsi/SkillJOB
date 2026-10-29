"""Photo de profil de l'entreprise (logo du compte recruteur).

Le fichier est facultatif : une entreprise sans logo conserve un rendu
propre à base d'initiales. Le logo est public, car il identifie l'entreprise
sur les offres et dans la messagerie.
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app import config
from app.services import uploads

COMPANY_LOGOS_DIR = config.UPLOAD_DIR / "company_logos"
_ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_BYTES = 5 * 1024 * 1024


def logo_url(company) -> str | None:
    """URL publique du logo, ou None si l'entreprise n'en a pas."""
    if not company or not company.logo_path:
        return None
    version = Path(str(company.logo_path)).name
    return f"/api/public/companies/{company.id}/logo?v={version}"


def save(company, file: UploadFile) -> str:
    """Enregistre le logo en remplaçant l'ancien fichier."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED:
        raise HTTPException(
            status_code=400,
            detail="Format accepté : JPG, PNG ou WebP",
        )
    payload = file.file.read(_MAX_BYTES + 1)
    if not payload:
        raise HTTPException(status_code=400, detail="Fichier vide")
    if len(payload) > _MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Image trop volumineuse (5 Mo maximum)",
        )
    COMPANY_LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    remove(company)
    stored = f"entreprise_{company.id}_{uuid4().hex[:10]}{ext}"
    (COMPANY_LOGOS_DIR / stored).write_bytes(payload)
    company.logo_path = uploads.store(COMPANY_LOGOS_DIR / stored)
    return company.logo_path


def remove(company) -> None:
    """Supprime le logo et remet le champ à zéro."""
    if not company or not company.logo_path:
        return
    try:
        uploads.resolve(company.logo_path).unlink(missing_ok=True)
    except OSError:  # pragma: no cover : fichier déjà absent ou protégé
        pass
    company.logo_path = None


def path_for(company) -> Path:
    """Chemin réel du logo, avec 404 si le fichier a disparu."""
    if not company or not company.logo_path:
        raise HTTPException(status_code=404, detail="Logo introuvable")
    target = uploads.resolve(company.logo_path)
    if not target.exists():
        raise HTTPException(status_code=404, detail="Logo introuvable")
    return target
