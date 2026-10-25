"""Documents joints aux programmes publics (PDF officiels).

Les administrations publient leurs avis et communiqués en PDF : la
plateforme les héberge tels quels, déposés par l'administration depuis la
console de contenus publics. Rien n'est inventé ni généré : le fichier est
conservé à l'identique et diffusé à la demande, avec son libellé.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app import config

DOCS_DIR = config.BASE_DIR / "uploads" / "programs"
_MAX_BYTES = 15 * 1024 * 1024


def _safe_name(name: str) -> str:
    keep = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-")
    return keep or "document.pdf"


def normalize(offer) -> list[dict]:
    """Documents d'une fiche, prêts pour l'API (URL de téléchargement)."""
    docs: list[dict] = []
    for doc in offer.documents or []:
        if not isinstance(doc, dict) or not doc.get("file") or not doc.get("key"):
            continue
        docs.append({
            "key": doc["key"],
            "label": doc.get("label") or doc.get("filename") or doc["file"],
            "url": f"/api/institutional/{offer.id}/documents/{doc['key']}",
            "filename": doc.get("filename") or "document.pdf",
        })
    return docs


def save(offer, file: UploadFile, label: str = "") -> dict:
    """Enregistre un PDF déposé par l'administration."""
    original = (file.filename or "document.pdf").strip()
    if Path(original).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Format accepté : PDF uniquement")
    payload = file.file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Fichier vide")
    if len(payload) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="PDF trop volumineux (15 Mo maximum)")
    key = uuid.uuid4().hex[:10]
    stored = f"programme-{offer.id}-{key}.pdf"
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    (DOCS_DIR / stored).write_bytes(payload)
    entry = {
        "key": key,
        "label": (label or Path(original).stem).strip()[:160],
        "file": stored,
        "filename": _safe_name(original),
    }
    offer.documents = [*(offer.documents or []), entry]
    return entry


def remove(offer, key: str) -> bool:
    """Retire un document joint et efface le fichier hébergé."""
    docs = list(offer.documents or [])
    entry = next(
        (d for d in docs if isinstance(d, dict) and d.get("key") == key),
        None,
    )
    if entry is None:
        return False
    try:
        (DOCS_DIR / Path(str(entry.get("file", ""))).name).unlink(missing_ok=True)
    except OSError:  # pragma: no cover : fichier déjà absent
        pass
    offer.documents = [d for d in docs if d is not entry]
    return True


def find(offer, key: str) -> dict | None:
    for doc in offer.documents or []:
        if isinstance(doc, dict) and doc.get("key") == key:
            return doc
    return None


def path_for(entry: dict) -> Path:
    stored = Path(str(entry.get("file", ""))).name
    target = DOCS_DIR / stored
    if not stored or not target.exists():
        raise HTTPException(status_code=404, detail="Document introuvable")
    return target
