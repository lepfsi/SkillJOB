"""Accès au profil maître (Profile Engine, §7.1).

Conversion modèle <-> dict conforme au contrat, normalisation des
compétences via la taxonomie (alias -> canonique).
"""
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import Profile
from app.services.skills_taxonomy import load_taxonomy

LIST_FIELDS = ("education", "experiences", "certifications", "languages", "projects", "skills")
SCALAR_FIELDS = ("summary", "title", "location", "mobility", "availability")


def get_profile_row(db: Session, user_id: int) -> Optional[Profile]:
    return db.get(Profile, user_id)


def profile_to_dict(row: Optional[Profile], user_id: int = 0) -> Optional[dict]:
    if row is None:
        return None
    return {
        "user_id": row.user_id,
        "summary": row.summary or "",
        "title": row.title,
        "location": row.location,
        "mobility": row.mobility,
        "availability": row.availability,
        "education": row.education or [],
        "experiences": row.experiences or [],
        "certifications": row.certifications or [],
        "languages": row.languages or [],
        "projects": row.projects or [],
        "skills": row.skills or [],
        "preferences": row.preferences or {
            "sectors": [], "target_roles": [], "contract_types": [], "remote_ok": False,
        },
    }


def normalize_skills(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Canonise les noms de compétences et renseigne leur catégorie."""
    taxonomy = load_taxonomy()
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in skills:
        name = taxonomy.canonical(str(entry.get("skill", "")))
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append({
            "skill": name,
            "category": taxonomy.category(name),
            "proficiency": entry.get("proficiency", "debutant"),
            "source": entry.get("source", "declared"),
            "evidence_count": int(entry.get("evidence_count", 0) or 0),
        })
    return normalized


def _assign_ids(items: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    clean = []
    for i, item in enumerate(items, start=1):
        item = dict(item)
        if not item.get("id"):
            item["id"] = f"{prefix}{i}"
        clean.append(item)
    return clean


def save_profile(db: Session, user_id: int, data: dict[str, Any]) -> Profile:
    """Mise à jour partielle du profil maître (validation humaine, §47)."""
    row = get_profile_row(db, user_id)
    if row is None:
        row = Profile(user_id=user_id, summary="", preferences={})
        db.add(row)

    for field in SCALAR_FIELDS:
        if field in data and data[field] is not None:
            setattr(row, field, data[field])

    for field in LIST_FIELDS:
        if field in data and data[field] is not None:
            items = [dict(i) for i in data[field]]
            if field == "skills":
                items = normalize_skills(items)
            else:
                prefix = field[0]
                items = _assign_ids(items, prefix)
                if field == "experiences":
                    # Canonise les compétences rattachées aux expériences
                    taxonomy = load_taxonomy()
                    for item in items:
                        item["skills"] = [
                            taxonomy.canonical(s) for s in item.get("skills", [])
                        ]
            setattr(row, field, items)

    if data.get("preferences") is not None:
        base = {
            "sectors": [], "target_roles": [], "contract_types": [], "remote_ok": False,
        }
        base.update({k: v for k, v in data["preferences"].items() if v is not None})
        row.preferences = base

    db.commit()
    db.refresh(row)
    return row
