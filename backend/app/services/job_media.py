"""Photo d'illustration d'une offre d'emploi (facultative).

Déposée par le publieur, recruteur ou administration, au moment de la
publication. Elle reste FACULTATIVE : une offre sans photo s'affiche
normalement. Le fichier est conservé tel quel et servi aux candidats.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile

from app import config

# Bac à sable des dépôts : UPLOAD_DIR isolé pour les tests et le smoke,
# jamais le dossier réel de l'utilisateur.
JOBS_DIR = config.UPLOAD_DIR / "jobs"
_ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_BYTES = 5 * 1024 * 1024


def photo_url(job) -> str | None:
    """URL publique de la photo, ou None si l'offre n'en a pas."""
    if not job.photo_path:
        return None
    return f"/api/jobs/{job.id}/photo"


def save(job, file: UploadFile) -> str:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED:
        raise HTTPException(
            status_code=400,
            detail="Format accepté : JPG, PNG ou WebP",
        )
    payload = file.file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Fichier vide")
    if len(payload) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image trop volumineuse (5 Mo maximum)")
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    remove(job)  # une seule photo par offre : l'ancienne est remplacée
    stored = f"offre-{job.id}{ext}"
    (JOBS_DIR / stored).write_bytes(payload)
    job.photo_path = stored
    return stored


def remove(job) -> None:
    if not job.photo_path:
        return
    try:
        (JOBS_DIR / Path(job.photo_path).name).unlink(missing_ok=True)
    except OSError:  # pragma: no cover : fichier déjà absent
        pass
    job.photo_path = None


def path_for(job) -> Path:
    stored = Path(str(job.photo_path or "")).name
    target = JOBS_DIR / stored
    if not stored or not target.exists():
        raise HTTPException(status_code=404, detail="Photo introuvable")
    return target
