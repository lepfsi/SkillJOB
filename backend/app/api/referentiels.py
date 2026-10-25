"""Référentiels publics Cameroun, programmes institutionnels,
entrepreneuriat interactif (business plan, guidance) et notifications.

- GET /api/geo : arbre Région (10) → Département → Arrondissements.
- GET /api/institutional : programmes publics restructurés (concours,
  grandes écoles, ministères techniques, FNE, MINFOP, MINPME).
- GET /api/entrepreneurship + POST /api/entrepreneurship/business-plan :
  espace entrepreneuriat interactif (§11bis).
- GET /api/entrepreneurship/guidance : comment entreprendre dans SON
  domaine de compétence, calculé depuis le profil réel.
- GET /api/entrepreneurship/profile : compétences entrepreneuriales
  réellement présentes dans le profil, situées par rapport à un
  référentiel issu de NOTRE taxonomie (§11bis, §47).
"""
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import config, models, schemas, security
from app.database import get_db
from app.services import domains as domains_service
from app.services import entrepreneurship as entrepreneurship_service
from app.services import program_documents

router = APIRouter(prefix="/api", tags=["referentiels"])


@router.get("/geo")
def geo():
    """Découpage administratif du Cameroun (données de référence locales)."""
    path = config.DATA_DIR / "cameroon_geo.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@router.get("/domains", response_model=list[schemas.DomainOut])
def domains(db: Session = Depends(get_db)):
    """Référentiel commun : domaines actifs et leurs spécialités.

    Il alimente la recherche d'offres, les filtres recruteur et les
    préférences de profil. Les entrées désactivées par l'admin ne sont pas
    exposées publiquement.
    """
    return domains_service.domain_tree(db)


# --------------------------------------------- Programmes publics

INSTITUTION_LABELS = {
    "minfopra": "Ministère de la Fonction Publique et de la Réforme Administrative",
    "minesup": "Ministère de l'Enseignement Supérieur",
    "minefop": "Ministère de l'Emploi et de la Formation Professionnelle",
    "ong": "Organisations non gouvernementales",
    "mindef": "Ministère de la Défense",
    "dgsn": "Délégation Générale à la Sûreté Nationale",
    "appels_projets": "Appels à projets des ministères",
}

SUBCATEGORY_LABELS = {
    "concours_direct": "Concours directs",
    "concours_integration": "Concours d'intégration",
    "universites": "Universités d'État",
    "ecoles": "Écoles de formation par université",
    "avis_concours": "Avis de concours",
    "fne": "Fonds National de l'Emploi (FNE)",
    "bourse_formation": "Bourses de formation professionnelle",
    "ong_emplois": "Offres d'emploi des ONG",
    "ong_stages": "Programmes de stage des ONG",
    "armee": "Concours d'entrée dans l'armée",
    "gendarmerie": "Gendarmerie nationale",
    "bir": "Bataillon d'intervention rapide (BIR)",
    "garde_presidentielle": "Garde présidentielle",
    "emia": "École militaire interarmes (EMIA)",
    "armee_etrangere": "Armée étrangère",
    "police": "Concours d'entrée à la police nationale",
    "appels_minader": "Appels à projets · MINADER (agriculture)",
    "appels_minepat": "Appels à projets · MINEPAT (planification)",
    "appels_minjec": "Appels à projets · MINJEC (jeunesse)",
    "appels_mintoul": "Appels à projets · MINTOUL (tourisme)",
    "appels_minfof": "Appels à projets · MINFOF (forêts et faune)",
    "appels_mincom": "Appels à projets · MINCOM (communication)",
}


@router.get("/institutional")
def institutional(
    category: str | None = None,
    user: models.User = Depends(security.get_optional_user),
    db: Session = Depends(get_db),
):
    """Programmes publics camerounais, structurés par catégorie et
    sous-catégorie (voir data/institutional_offers.json)."""
    query = db.query(models.InstitutionalOffer)
    if category:
        query = query.filter(models.InstitutionalOffer.category == category)
    items = query.order_by(models.InstitutionalOffer.id).all()
    return [
        {
            "id": o.id,
            "category": o.category,
            "category_label": INSTITUTION_LABELS.get(o.category, o.category),
            "subcategory": o.subcategory or "",
            "subcategory_label": SUBCATEGORY_LABELS.get(o.subcategory or "", ""),
            "title": o.title,
            "description": o.description,
            "eligibility": o.eligibility,
            "url": o.url,
            "deadline": o.deadline,
            # Documents joints par l'administration (PDF) : la fiche les
            # affiche tels quels, avec un bouton de téléchargement.
            "documents": program_documents.normalize(o),
        }
        for o in items
    ]


@router.get("/institutional/minesup")
def minesup_catalogue(db: Session = Depends(get_db)):
    """Explorateur MINESUP : universités d'État puis grandes écoles.

    La hiérarchie est portée par la base, pas reconstruite à partir d'un
    texte libre. Chaque école expose sa voie d'admission, son éligibilité,
    son calendrier annoncé et son lien officiel.
    """
    universities = (
        db.query(models.MinesupUniversity)
        .order_by(models.MinesupUniversity.sort_order, models.MinesupUniversity.name)
        .all()
    )
    schools_by_university: dict[int, list[models.MinesupSchool]] = {}
    if universities:
        schools = (
            db.query(models.MinesupSchool)
            .order_by(models.MinesupSchool.sort_order, models.MinesupSchool.name)
            .all()
        )
        for school in schools:
            schools_by_university.setdefault(school.university_id, []).append(school)

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
            "schools": [
                {
                    "id": s.id,
                    "name": s.name,
                    "short_name": s.short_name,
                    "kind": s.kind,
                    "admission": s.admission,
                    "eligibility": s.eligibility,
                    "url": s.url,
                    "deadline": s.deadline,
                }
                for s in schools_by_university.get(u.id, [])
            ],
        }
        for u in universities
    ]


@router.get("/institutional/{item_id}/documents/{key}")
def institutional_document(item_id: int, key: str, db: Session = Depends(get_db)):
    """Téléchargement d'un PDF joint à un programme public."""
    offer = db.get(models.InstitutionalOffer, item_id)
    if offer is None:
        raise HTTPException(status_code=404, detail="Programme introuvable")
    entry = program_documents.find(offer, key)
    if entry is None:
        raise HTTPException(status_code=404, detail="Document introuvable")
    return FileResponse(
        program_documents.path_for(entry),
        media_type="application/pdf",
        filename=entry.get("filename") or "document.pdf",
    )


@router.get("/entrepreneurship")
def entrepreneurship(
    kind: str | None = None,
    user: models.User = Depends(security.get_optional_user),
    db: Session = Depends(get_db),
):
    """Espace entrepreneuriat (§11bis) : ressources, institutions de
    financement public/parapublic, exigences bancaires."""
    return {
        "resources": entrepreneurship_service.list_resources(db, kind),
        "bank_prep": entrepreneurship_service.BANK_PREP,
        "financing_institutions": entrepreneurship_service.FINANCING_INSTITUTIONS,
    }


@router.get("/entrepreneurship/profile")
def entrepreneur_profile(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """« Mon profil entrepreneurial » : compétences entrepreneuriales
    réellement présentes dans le profil validé, situées par rapport au
    référentiel (issu de notre taxonomie), et compétences métier du
    porteur qui ne figurent pas dans ce référentiel."""
    from app.services.profile_store import get_profile_row, profile_to_dict
    from app.services.skills_taxonomy import load_taxonomy

    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    return entrepreneurship_service.entrepreneur_profile(profile, load_taxonomy())


@router.get("/entrepreneurship/guidance")
def entrepreneur_guidance(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """« Comment entreprendre dans MON domaine » : pistes calculées
    depuis le profil validé du jeune."""
    from app.services.business_plan import guidance_for
    from app.services.profile_store import get_profile_row, profile_to_dict
    from app.services.skills_taxonomy import load_taxonomy

    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    return guidance_for(profile, load_taxonomy())


@router.post("/entrepreneurship/business-plan", response_model=schemas.DocumentOut)
def generate_business_plan(
    payload: schemas.BusinessPlanIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Construit un business plan à partir du formulaire du porteur et
    de son profil validé. Enregistré comme document exportable.
    Aucune donnée inventée (§47)."""
    from app.services.business_plan import build_business_plan
    from app.services.profile_store import get_profile_row, profile_to_dict
    from app.services.skills_taxonomy import load_taxonomy

    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    content = build_business_plan(
        user, profile, payload.model_dump(), load_taxonomy()
    )
    document = models.Document(
        user_id=user.id,
        job_id=None,
        kind="business_plan",
        title=f"Business plan · {payload.activity[:60] if payload.activity else 'Projet'}",
        content_markdown=content,
        template="classique",
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document
