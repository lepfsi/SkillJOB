"""V3 : Intelligence institutionnelle (§39) et Skill Graph (§41).

- Dashboard institutionnel : agrégats ANONYMISÉS pour les décideurs
  publics : offre/demande de compétences, écarts, secteurs, candidatures.
  Aucune donnée individuelle n'est exposée.
- Skill Graph : exploration du graphe compétences ↔ métiers ↔ offres ↔
  talents ↔ formations, pour détecter les trajectoires possibles même
  sans titre de poste exact (§41).
"""
from collections import Counter
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services import program_documents
from app.services.skills_taxonomy import load_taxonomy

router = APIRouter(prefix="/api/admin", tags=["v3-intelligence"],
                   dependencies=[Depends(security.require_admin)])


def _skill_demand(jobs: list, weighted: bool = True) -> Counter:
    counter: Counter[str] = Counter()
    for job in jobs:
        for req in job.required_skills or []:
            name = req.get("name")
            if not name:
                continue
            weight = 2 if weighted and req.get("importance") == "core" else 1
            counter[name] += weight
    return counter


def _skill_supply(profiles: list) -> Counter:
    counter: Counter[str] = Counter()
    for profile in profiles:
        for s in profile.skills or []:
            if s.get("skill"):
                counter[s["skill"]] += 1
    return counter


@router.get("/institutional-dashboard", response_model=dict)
def institutional_dashboard(db: Session = Depends(get_db)):
    """Indicateurs agrégés et anonymisés (§39, §61) : lecture du marché
    local pour la décision publique."""
    candidates = db.query(models.User).filter_by(role="candidate").all()
    recruiters = db.query(models.User).filter_by(role="recruiter").all()
    profiles = db.query(models.Profile).all()
    jobs = db.query(models.Job).all()
    applications = db.query(models.Application).all()

    demand = _skill_demand(jobs)
    supply = _skill_supply(profiles)

    # Écarts de compétences : demandées par les offres, rares chez les
    # jeunes. Ratio offre de talents / demande du marché.
    gaps = []
    for name, d in demand.most_common(40):
        s = supply.get(name, 0)
        if d >= 3:
            gaps.append({"skill": name, "demand": d, "supply": s,
                         "ratio": round(d / (s if s else 0.5), 1)})
    gaps.sort(key=lambda g: -g["ratio"])

    regions = Counter(
        u.region for u in candidates if u.region
    )
    sectors = Counter(j.sector for j in jobs if j.sector)
    status_counts = Counter(a.status for a in applications)
    profiles_with_skills = sum(
        1 for p in profiles if (p.skills or [])
    )

    return {
        "candidates": len(candidates),
        "recruiters": len(recruiters),
        "profiles": len(profiles),
        "profiles_with_skills": profiles_with_skills,
        "jobs": len(jobs),
        "applications": len(applications),
        "applications_by_status": [
            {"status": s, "count": c} for s, c in status_counts.most_common()
        ],
        "top_demand": [{"skill": n, "count": c} for n, c in demand.most_common(10)],
        "top_supply": [{"skill": n, "count": c} for n, c in supply.most_common(10)],
        "skill_gaps": gaps[:10],
        "regions": [{"region": r, "candidates": c} for r, c in regions.most_common()],
        "sectors": [{"sector": s, "offers": c} for s, c in sectors.most_common(10)],
    }


@router.get("/skill-graph", response_model=dict)
def skill_graph(
    skill: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """Explore le Skill Graph (§41). Sans paramètre : les compétences
    structurantes en point d'entrée. Avec `skill` : le nœud et ses
    relations (métiers, offres, talents, formations, compétences liées)."""
    taxonomy = load_taxonomy()
    careers = db.query(models.Career).all()
    jobs = db.query(models.Job).all()
    profiles = db.query(models.Profile).all()
    resources = (
        db.query(models.LearningResource)
        .filter(models.LearningResource.hidden.is_(False))
        .all()
    )

    if not skill:
        demand = _skill_demand(jobs)
        supply = _skill_supply(profiles)
        hubs = []
        for name, d in demand.most_common(25):
            hubs.append({
                "skill": name,
                "category": taxonomy.category(name),
                "demand": d,
                "supply": supply.get(name, 0),
            })
        return {"entry_points": hubs}

    skill = taxonomy.canonical(skill)
    node = {"skill": skill, "category": taxonomy.category(skill)}

    # Métiers exigeant la compétence
    related_careers = []
    for career in careers:
        names = [r.get("name") for r in career.required_skills or []]
        if skill in names:
            related_careers.append({"id": career.id, "title": career.title,
                                    "family": career.family})

    # Offres exigeant la compétence
    matching_jobs = [j for j in jobs if any(
        r.get("name") == skill for r in j.required_skills or [])]
    related_jobs = [
        {"id": j.id, "title": j.title, "company": j.company, "location": j.location}
        for j in matching_jobs[:5]
    ]

    # Talents disposant de la compétence (anonymisé : compte par niveau)
    proficiency: Counter[str] = Counter()
    talents_total = 0
    for profile in profiles:
        entry = next((s for s in profile.skills or [] if s.get("skill") == skill), None)
        if entry:
            talents_total += 1
            proficiency[entry.get("proficiency", "debutant")] += 1

    # Compétences liées : co-occurrence dans métiers et offres (trajectoires)
    co: Counter[str] = Counter()
    for career in careers:
        names = [r.get("name") for r in career.required_skills or []]
        if skill in names:
            for n in names:
                if n != skill:
                    co[n] += 2
    for job in jobs:
        names = [r.get("name") for r in job.required_skills or []]
        if skill in names:
            for n in names:
                if n != skill:
                    co[n] += 1
    related_skills = [{"skill": n, "weight": c} for n, c in co.most_common(8)]

    learning = [
        {"title": r.title, "provider": r.provider, "type": r.type}
        for r in resources if r.skill == skill
    ][:5]

    return {
        "node": node,
        "careers": related_careers,
        "jobs_count": len(matching_jobs),
        "jobs": related_jobs,
        "talents_count": talents_total,
        "talents_by_level": [{"level": l, "count": c} for l, c in proficiency.most_common()],
        "related_skills": related_skills,
        "learning": learning,
    }


# ------------------------------ Contenus publics (gestion admin)

@router.get("/public-content/institutional", response_model=list[dict])
def list_institutional_content(db: Session = Depends(get_db)):
    return [
        {"id": o.id, "category": o.category, "subcategory": o.subcategory,
         "title": o.title, "description": o.description,
         "eligibility": o.eligibility, "url": o.url, "deadline": o.deadline,
         "source": o.source or "referentiel",
         "documents": program_documents.normalize(o)}
        for o in db.query(models.InstitutionalOffer).order_by(models.InstitutionalOffer.id).all()
    ]


@router.post("/public-content/institutional", status_code=201, response_model=dict)
def create_institutional_content(
    payload: schemas.InstitutionalCreateIn, db: Session = Depends(get_db)
):
    # Une fiche créée dans la console appartient à l'administration :
    # la synchronisation du référentiel ne la touchera jamais.
    item = models.InstitutionalOffer(source="admin", **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "ok": True}


@router.put("/public-content/institutional/{item_id}", response_model=dict)
def update_institutional_content(
    item_id: int, payload: schemas.InstitutionalCreateIn, db: Session = Depends(get_db)
):
    item = db.get(models.InstitutionalOffer, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Programme introuvable")
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    # Fiche reprise en main : elle cesse d'être écrasée par le référentiel.
    item.source = "admin"
    db.commit()
    return {"ok": True}


@router.delete("/public-content/institutional/{item_id}")
def delete_institutional_content(item_id: int, db: Session = Depends(get_db)):
    item = db.get(models.InstitutionalOffer, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Programme introuvable")
    # Les PDF joints partent avec la fiche (fichiers hébergés effacés).
    for doc in list(item.documents or []):
        if isinstance(doc, dict) and doc.get("key"):
            program_documents.remove(item, doc["key"])
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/public-content/institutional/{item_id}/documents", response_model=dict)
def attach_institutional_document(
    item_id: int,
    file: UploadFile = File(...),
    label: str = Form(""),
    db: Session = Depends(get_db),
):
    """Joint un PDF officiel à un programme public (facultatif).

    Le fichier est hébergé tel quel : il n'est ni modifié ni résumé par la
    plateforme. Son libellé sert de nom de téléchargement.
    """
    item = db.get(models.InstitutionalOffer, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Programme introuvable")
    entry = program_documents.save(item, file, label)
    db.commit()
    db.refresh(item)
    return {"ok": True, "documents": program_documents.normalize(item), "key": entry["key"]}


@router.delete("/public-content/institutional/{item_id}/documents/{key}")
def detach_institutional_document(
    item_id: int, key: str, db: Session = Depends(get_db)
):
    item = db.get(models.InstitutionalOffer, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Programme introuvable")
    if not program_documents.remove(item, key):
        raise HTTPException(status_code=404, detail="Document introuvable")
    db.commit()
    return {"ok": True}


# --------------------------- Universités MINESUP (édition admin)

def _slugify(value: str) -> str:
    import unicodedata

    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    slug = "".join(c if c.isalnum() else "-" for c in text)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "universite"


def _unique_university_slug(
    db: Session, wanted: str, exclude_id: int | None = None
) -> str:
    base = _slugify(wanted)
    slug = base
    suffix = 2
    while True:
        query = db.query(models.MinesupUniversity).filter(
            models.MinesupUniversity.slug == slug
        )
        if exclude_id is not None:
            query = query.filter(models.MinesupUniversity.id != exclude_id)
        if query.first() is None:
            return slug
        slug = f"{base}-{suffix}"
        suffix += 1


def _minesup_admin_payload(db: Session) -> list[dict]:
    universities = (
        db.query(models.MinesupUniversity)
        .order_by(models.MinesupUniversity.sort_order, models.MinesupUniversity.name)
        .all()
    )
    schools = (
        db.query(models.MinesupSchool)
        .order_by(models.MinesupSchool.sort_order, models.MinesupSchool.name)
        .all()
    )
    grouped: dict[int, list[dict]] = {}
    for school in schools:
        grouped.setdefault(school.university_id, []).append({
            "id": school.id,
            "name": school.name,
            "short_name": school.short_name,
            "kind": school.kind,
            "admission": school.admission,
            "eligibility": school.eligibility,
            "url": school.url,
            "deadline": school.deadline,
            "sort_order": school.sort_order,
            "source": school.source or "referentiel",
        })
    return [
        {
            "id": u.id,
            "slug": u.slug,
            "name": u.name,
            "short_name": u.short_name,
            "city": u.city,
            "region": u.region,
            "description": u.description,
            "website": u.website,
            "source_url": u.source_url,
            "sort_order": u.sort_order,
            "source": u.source or "referentiel",
            "schools": grouped.get(u.id, []),
        }
        for u in universities
    ]


@router.get("/public-content/minesup", response_model=list[dict])
def list_minesup_catalogue(db: Session = Depends(get_db)):
    return _minesup_admin_payload(db)


@router.post("/public-content/minesup/universities", status_code=201, response_model=dict)
def create_minesup_university(
    payload: schemas.MinesupUniversityIn, db: Session = Depends(get_db)
):
    data = payload.model_dump()
    data["slug"] = _unique_university_slug(db, data.get("slug") or data["name"])
    item = models.MinesupUniversity(source="admin", **data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "ok": True}


@router.put("/public-content/minesup/universities/{university_id}", response_model=dict)
def update_minesup_university(
    university_id: int,
    payload: schemas.MinesupUniversityIn,
    db: Session = Depends(get_db),
):
    item = db.get(models.MinesupUniversity, university_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Université introuvable")
    data = payload.model_dump()
    data["slug"] = _unique_university_slug(
        db, data.get("slug") or data["name"], exclude_id=item.id
    )
    for field, value in data.items():
        setattr(item, field, value)
    item.source = "admin"
    db.commit()
    return {"ok": True}


@router.delete("/public-content/minesup/universities/{university_id}")
def delete_minesup_university(
    university_id: int, db: Session = Depends(get_db)
):
    item = db.get(models.MinesupUniversity, university_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Université introuvable")
    db.query(models.MinesupSchool).filter(
        models.MinesupSchool.university_id == item.id
    ).delete()
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post(
    "/public-content/minesup/universities/{university_id}/schools",
    status_code=201,
    response_model=dict,
)
def create_minesup_school(
    university_id: int,
    payload: schemas.MinesupSchoolIn,
    db: Session = Depends(get_db),
):
    university = db.get(models.MinesupUniversity, university_id)
    if university is None:
        raise HTTPException(status_code=404, detail="Université introuvable")
    item = models.MinesupSchool(
        university_id=university.id, source="admin", **payload.model_dump()
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "ok": True}


@router.put("/public-content/minesup/schools/{school_id}", response_model=dict)
def update_minesup_school(
    school_id: int,
    payload: schemas.MinesupSchoolIn,
    db: Session = Depends(get_db),
):
    item = db.get(models.MinesupSchool, school_id)
    if item is None:
        raise HTTPException(status_code=404, detail="École introuvable")
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    item.source = "admin"
    db.commit()
    return {"ok": True}


@router.delete("/public-content/minesup/schools/{school_id}")
def delete_minesup_school(school_id: int, db: Session = Depends(get_db)):
    item = db.get(models.MinesupSchool, school_id)
    if item is None:
        raise HTTPException(status_code=404, detail="École introuvable")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/public-content/entrepreneurship", response_model=list[dict])
def list_entrepreneur_content(db: Session = Depends(get_db)):
    return [
        {"id": r.id, "kind": r.kind, "title": r.title,
         "description": r.description, "organizer": r.organizer,
         "url": r.url, "sectors": r.sectors}
        for r in db.query(models.EntrepreneurResource).order_by(models.EntrepreneurResource.id).all()
    ]


@router.post("/public-content/entrepreneurship", status_code=201, response_model=dict)
def create_entrepreneur_content(
    payload: schemas.EntrepreneurCreateIn, db: Session = Depends(get_db)
):
    item = models.EntrepreneurResource(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "ok": True}


@router.put("/public-content/entrepreneurship/{item_id}", response_model=dict)
def update_entrepreneur_content(
    item_id: int, payload: schemas.EntrepreneurCreateIn, db: Session = Depends(get_db)
):
    item = db.get(models.EntrepreneurResource, item_id)
    if item is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ressource introuvable")
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    db.commit()
    return {"ok": True}


@router.delete("/public-content/entrepreneurship/{item_id}")
def delete_entrepreneur_content(item_id: int, db: Session = Depends(get_db)):
    item = db.get(models.EntrepreneurResource, item_id)
    if item is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ressource introuvable")
    db.delete(item)
    db.commit()
    return {"ok": True}
