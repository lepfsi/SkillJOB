"""Référentiel commun des domaines et spécialités professionnelles.

Le fichier ``data/domains.json`` est la source de vérité initiale. Il est
préchargé quand la table est vide, puis l'administration peut ajouter,
modifier ou désactiver des entrées sans être écrasée au redémarrage.

Les profils et les offres stockent des identifiants : la recherche reste
stable même si un libellé est corrigé.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import config, models


def slugify(value: str) -> str:
    """Slug lisible, sans accent ni tiret long."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "element"


def _load_referential() -> list[dict[str, Any]]:
    path = config.DATA_DIR / "domains.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _unique_slug(db: Session, base: str, model, domain_id: Optional[int] = None) -> str:
    slug = slugify(base)
    candidate = slug
    index = 2
    while True:
        query = db.query(model).filter(model.slug == candidate)
        if model is models.Specialty and domain_id is not None:
            query = query.filter(model.domain_id == domain_id)
        if query.first() is None:
            return candidate
        candidate = f"{slug}-{index}"
        index += 1


def seed_domains(db: Session) -> None:
    """Précharge le référentiel quand il est vide (idempotent)."""
    if db.query(models.Domain).count() > 0:
        return
    for entry in _load_referential():
        domain = models.Domain(
            slug=entry.get("slug") or slugify(entry["name"]),
            name=entry["name"],
            description=entry.get("description", ""),
            aliases=entry.get("aliases", []),
            sort_order=entry.get("sort_order", 0),
            active=True,
            source="referentiel",
        )
        db.add(domain)
        db.flush()
        for index, item in enumerate(entry.get("specialties", [])):
            db.add(models.Specialty(
                domain_id=domain.id,
                slug=item.get("slug") or slugify(item["name"]),
                name=item["name"],
                description=item.get("description", ""),
                aliases=item.get("aliases", []),
                sort_order=item.get("sort_order", index),
                active=True,
                source="referentiel",
            ))
    db.commit()


def sync_new_specialties(db: Session) -> int:
    """Synchronise le référentiel : ajoute les spécialités absentes et
    réaligne l'ordre de celles restées au référentiel.

    - Les entrées inconnues en base (par slug) sont CRÉÉES.
    - L'ordre (`sort_order`) des entrées `source = "referentiel"` suit le
      JSON : les nouvelles spécialités s'insèrent à leur place logique
      (« Autre spécialité » reste en dernier).
    - Les entrées MODIFIÉES par l'admin (`source = "admin"`) ne sont
      jamais ni renommées, ni réordonnées, ni désactivées.

    Non destructif : aucune suppression, aucun libellé écrasé.
    """
    added = 0
    reordered = 0
    for entry in _load_referential():
        domain_slug = entry.get("slug") or slugify(entry["name"])
        domain = (
            db.query(models.Domain).filter(models.Domain.slug == domain_slug).first()
        )
        if domain is None:
            continue
        rows = (
            db.query(models.Specialty)
            .filter(models.Specialty.domain_id == domain.id)
            .all()
        )
        by_slug = {s.slug: s for s in rows}
        for index, item in enumerate(entry.get("specialties", [])):
            slug = item.get("slug") or slugify(item["name"])
            target_order = item.get("sort_order", index)
            if slug in by_slug:
                row = by_slug[slug]
                # Ordre uniquement, et uniquement pour le référentiel :
                # jamais un libellé ni une entrée corrigée par l'admin.
                if row.source == "referentiel" and row.sort_order != target_order:
                    row.sort_order = target_order
                    reordered += 1
                continue
            db.add(models.Specialty(
                domain_id=domain.id,
                slug=slug,
                name=item["name"],
                description=item.get("description", ""),
                aliases=item.get("aliases", []),
                sort_order=target_order,
                active=True,
                source="referentiel",
            ))
            added += 1
    if added or reordered:
        db.commit()
    return added


def _normalized(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def match_domain(db: Session, label: str) -> Optional[models.Domain]:
    """Retrouve un domaine par nom, slug, alias ou inclusion raisonnable."""
    needle = _normalized(label)
    if not needle:
        return None
    domains = db.query(models.Domain).all()
    for domain in domains:
        candidates = [domain.name, domain.slug, *(domain.aliases or [])]
        if any(_normalized(c) == needle for c in candidates):
            return domain
    for domain in domains:
        candidates = [domain.name, *(domain.aliases or [])]
        if any(needle in _normalized(c) or _normalized(c) in needle for c in candidates if c):
            return domain
    return None


def match_specialty(
    db: Session, domain_id: int, label: str
) -> Optional[models.Specialty]:
    needle = _normalized(label)
    if not needle:
        return None
    rows = db.query(models.Specialty).filter(models.Specialty.domain_id == domain_id).all()
    for row in rows:
        candidates = [row.name, row.slug, *(row.aliases or [])]
        if any(_normalized(c) == needle for c in candidates):
            return row
    for row in rows:
        candidates = [row.name, *(row.aliases or [])]
        if any(needle in _normalized(c) or _normalized(c) in needle for c in candidates if c):
            return row
    return None


def backfill_job_domains(db: Session) -> None:
    """Qualifie les offres historiques à partir de leur secteur et intitulé.

    On ne devine jamais une spécialité : elle n'est renseignée que si son
    nom ou un alias apparaît explicitement dans l'intitulé ou les exigences.
    """
    changed = False
    for job in db.query(models.Job).filter(models.Job.domain_id.is_(None)).all():
        domain = match_domain(db, job.sector or "")
        if domain is None:
            continue
        job.domain_id = domain.id
        haystack = " ".join(filter(None, [job.title, job.description, job.requirements]))
        specialty = match_specialty(db, domain.id, haystack)
        if specialty is not None:
            job.specialty_id = specialty.id
        changed = True
    if changed:
        db.commit()


def domain_tree(
    db: Session, include_inactive: bool = False
) -> list[dict[str, Any]]:
    """Arbre domaine > spécialités, ordonné pour les menus publics."""
    query = db.query(models.Domain)
    if not include_inactive:
        query = query.filter(models.Domain.active.is_(True))
    domains = query.order_by(models.Domain.sort_order, models.Domain.name).all()
    ids = [d.id for d in domains]
    specialties_by_domain: dict[int, list[models.Specialty]] = {}
    if ids:
        query = db.query(models.Specialty).filter(models.Specialty.domain_id.in_(ids))
        if not include_inactive:
            query = query.filter(models.Specialty.active.is_(True))
        for row in query.order_by(models.Specialty.sort_order, models.Specialty.name).all():
            specialties_by_domain.setdefault(row.domain_id, []).append(row)
    return [
        {
            "id": domain.id,
            "slug": domain.slug,
            "name": domain.name,
            "description": domain.description,
            "aliases": domain.aliases or [],
            "sort_order": domain.sort_order,
            "active": domain.active,
            "specialties": [
                {
                    "id": specialty.id,
                    "slug": specialty.slug,
                    "name": specialty.name,
                    "description": specialty.description,
                    "aliases": specialty.aliases or [],
                    "sort_order": specialty.sort_order,
                    "active": specialty.active,
                }
                for specialty in specialties_by_domain.get(domain.id, [])
            ],
        }
        for domain in domains
    ]


def resolve_names(
    db: Session, domain_id: Optional[int], specialty_ids: Optional[list[int]]
) -> tuple[Optional[str], list[str]]:
    """Libellés d'affichage pour un couple domaine / spécialités."""
    if not domain_id:
        return None, []
    domain = db.get(models.Domain, domain_id)
    if domain is None:
        return None, []
    names: list[str] = []
    for specialty_id in specialty_ids or []:
        specialty = db.get(models.Specialty, specialty_id)
        if specialty is not None and specialty.domain_id == domain.id:
            names.append(specialty.name)
    return domain.name, names


def create_domain(db: Session, payload) -> models.Domain:
    data = payload.model_dump()
    slug = data.get("slug") or _unique_slug(db, data["name"], models.Domain)
    if db.query(models.Domain).filter(models.Domain.slug == slug).first():
        slug = _unique_slug(db, slug, models.Domain)
    row = models.Domain(
        slug=slug,
        name=data["name"].strip(),
        description=data.get("description", ""),
        aliases=[a for a in (data.get("aliases") or []) if a],
        sort_order=data.get("sort_order", 0),
        active=data.get("active", True),
        source="admin",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_domain(db: Session, row: models.Domain, payload) -> models.Domain:
    data = payload.model_dump()
    row.name = data["name"].strip()
    row.description = data.get("description", "")
    row.aliases = [a for a in (data.get("aliases") or []) if a]
    row.sort_order = data.get("sort_order", row.sort_order)
    row.active = data.get("active", row.active)
    if data.get("slug") and data["slug"] != row.slug:
        row.slug = _unique_slug(db, data["slug"], models.Domain)
    row.source = "admin"
    db.commit()
    db.refresh(row)
    return row


def create_specialty(db: Session, domain: models.Domain, payload) -> models.Specialty:
    data = payload.model_dump()
    slug = data.get("slug") or _unique_slug(
        db, data["name"], models.Specialty, domain.id
    )
    row = models.Specialty(
        domain_id=domain.id,
        slug=slug,
        name=data["name"].strip(),
        description=data.get("description", ""),
        aliases=[a for a in (data.get("aliases") or []) if a],
        sort_order=data.get("sort_order", 0),
        active=data.get("active", True),
        source="admin",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_specialty(
    db: Session, domain: models.Domain, row: models.Specialty, payload
) -> models.Specialty:
    data = payload.model_dump()
    row.name = data["name"].strip()
    row.description = data.get("description", "")
    row.aliases = [a for a in (data.get("aliases") or []) if a]
    row.sort_order = data.get("sort_order", row.sort_order)
    row.active = data.get("active", row.active)
    if data.get("slug") and data["slug"] != row.slug:
        row.slug = _unique_slug(db, data["slug"], models.Specialty, domain.id)
    row.source = "admin"
    db.commit()
    db.refresh(row)
    return row
