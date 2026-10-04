"""Référentiels publics Cameroun, programmes institutionnels,
entrepreneuriat interactif (business plan, guidance) et notifications.

- GET /api/geo : arbre Région (10) → Département → Arrondissements.
- GET /api/institutional : programmes publics restructurés (concours,
  grandes écoles, ministères techniques, FNE, MINFOP, MINPME).
- GET /api/entrepreneurship + POST /api/entrepreneurship/business-plan :
  espace entrepreneuriat interactif (§11bis).
- GET /api/entrepreneurship/guidance : comment entreprendre dans SON
  domaine de compétence, calculé depuis le profil réel.
"""
import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import config, models, schemas, security
from app.database import get_db

router = APIRouter(prefix="/api", tags=["referentiels"])


@router.get("/geo")
def geo():
    """Découpage administratif du Cameroun (données de référence locales)."""
    path = config.DATA_DIR / "cameroon_geo.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------- Programmes publics

INSTITUTION_LABELS = {
    "fne": "Fonds National de l'Emploi",
    "minfop": "Ministère de la Formation Professionnelle",
    "minpme": "Ministère des Petites et Moyennes Entreprises",
    "concours": "Concours et examens",
}

SUBCATEGORY_LABELS = {
    "fonction_publique": "Concours de la fonction publique",
    "grandes_ecoles": "Concours des grandes écoles (MINESUP)",
    "sante": "Personnel de la santé",
    "forets_faune": "Eaux, forêts et faune",
    "armees": "Armées et sécurité",
    "bourses": "Bourses de formation",
    "offres_emploi": "Offres d'emploi et stages",
    "accompagnement_pme": "Accompagnement des PME",
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
        }
        for o in items
    ]


ENTREPRENEUR_KIND_LABELS = {
    "concours": "Concours et appels à projets",
    "accompagnement": "Accompagnement et incubation",
    "financement": "Financement",
    "formation": "Formation entrepreneuriale",
}

# Exigences bancaires types (répertoire de préparation, documenté et
# actualisable ; jamais présenté comme garanti).
BANK_PREP = [
    {
        "step": "Business plan complet",
        "detail": "Description de l'activité, étude de marché locale, "
                  "prévisionnel sur 3 ans, plan de trésorerie mensuel.",
    },
    {
        "step": "Statut juridique à jour",
        "detail": "Registre de commerce (RCCM), N° de contribuable, "
                  "statuts notariés ou agréés pour les sociétés.",
    },
    {
        "step": "Apport personnel",
        "detail": "Les banques exigent généralement 15 à 30 % d'apport "
                  "démontrant votre engagement dans le projet.",
    },
    {
        "step": "Garanties",
        "detail": "Nantissement de matériel, caution solidaire, hypothèque "
                  "ou garantie de programme public (fonds de garantie).",
    },
    {
        "step": "Comptabilité tenue",
        "detail": "Livres comptables, relevés bancaires de l'activité, "
                  "factures fournisseurs et clients sur les derniers mois.",
    },
    {
        "step": "Expérience du porteur",
        "detail": "CV ou références montrant votre maîtrise du métier : "
                  "votre profil OrientSkill documente vos compétences "
                  "et expériences, y compris informelles.",
    },
]

# Institutions de financement et d'accompagnement (publics et parapublics).
FINANCING_INSTITUTIONS = [
    {
        "name": "Fonds National de l'Emploi (FNE)",
        "type": "Public",
        "finances": "Auto-emploi, contrats préprofessionnels, appui aux microprojets des jeunes.",
        "conditions": "Étude de faisabilité du projet, inscription FNE, apport personnel symbolique.",
        "url": "https://www.emploi.cm",
    },
    {
        "name": "Programme économique spécial jeunes (PEA-Jeunes, MINPME)",
        "type": "Public",
        "finances": "Financement partiel des jeunes entreprises en création.",
        "conditions": "Projet économique viable, groupe ou individu formalisé, formation à la gestion.",
        "url": "https://www.minpme.gov.cm",
    },
    {
        "name": "Banques commerciales (BICEC, SCB Crédit Agricole, SGB, Afriland First Bank…)",
        "type": "Banque",
        "finances": "Crédits d'investissement et d'exploitation des PME.",
        "conditions": "Business plan, garanties (souvent 100 %), comptabilité tenue, apport personnel.",
        "url": None,
    },
    {
        "name": "Institutions de microfinance (IMF agréées)",
        "type": "Microfinance",
        "finances": "Microcrédits rapides aux très petites entreprises sans garanties classiques.",
        "conditions": "Épargne préalable ou caution solidaire, projet simple et réaliste.",
        "url": None,
    },
    {
        "name": "Fonds de garantie publics et partenariaux",
        "type": "Garantie",
        "finances": "Garantie des prêts bancaires accordés aux jeunes promoteurs (le fonds se porte caution partielle).",
        "conditions": "Dossier instruit par la banque partenaire, adhésion au dispositif.",
        "url": None,
    },
    {
        "name": "CDC (Caisse de Dépôts et Consignations) et structures parapubliques",
        "type": "Parapublic",
        "finances": "Participations et financements structurés de projets à impact.",
        "conditions": "Projets structurés avec étude complète, montage juridique.",
        "url": None,
    },
]


@router.get("/entrepreneurship")
def entrepreneurship(
    kind: str | None = None,
    user: models.User = Depends(security.get_optional_user),
    db: Session = Depends(get_db),
):
    """Espace entrepreneuriat (§11bis) : ressources, institutions de
    financement public/parapublic, exigences bancaires."""
    query = db.query(models.EntrepreneurResource)
    if kind:
        query = query.filter(models.EntrepreneurResource.kind == kind)
    items = query.order_by(models.EntrepreneurResource.id).all()
    return {
        "resources": [
            {
                "id": r.id,
                "kind": r.kind,
                "kind_label": ENTREPRENEUR_KIND_LABELS.get(r.kind, r.kind),
                "title": r.title,
                "description": r.description,
                "organizer": r.organizer,
                "url": r.url,
                "sectors": r.sectors,
            }
            for r in items
        ],
        "bank_prep": BANK_PREP,
        "financing_institutions": FINANCING_INSTITUTIONS,
    }


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
