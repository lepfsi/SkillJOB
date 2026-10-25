"""Espace entrepreneuriat (§11bis) : données de référence et lecture du
profil entrepreneurial.

Deux engagements :
- le référentiel des compétences entrepreneuriales est un SOUS-ENSEMBLE
  de notre taxonomie de compétences : aucun nom inventé (§47) ;
- les institutions de financement et les exigences bancaires sont des
  données de référence documentées, jamais présentées comme garanties.
"""
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models
from app.services.skills_taxonomy import normalize

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

# Compétences entrepreneuriales attendues chez un porteur de projet :
# TOUS ces noms existent dans backend/data/skills_taxonomy.json : le
# référentiel ne contient donc aucune compétence inventée (§47).
ENTREPRENEUR_SKILL_GROUPS: list[dict[str, Any]] = [
    {
        "key": "pilotage",
        "label": "Pilotage et gestion",
        "skills": [
            "Entrepreneuriat",
            "Gestion de projet",
            "Gestion budgétaire",
            "Analyse financière",
            "Comptabilité générale",
            "Fiscalité",
        ],
    },
    {
        "key": "marche",
        "label": "Marché et clients",
        "skills": [
            "Études de marché",
            "Marketing digital",
            "Community management",
            "Publicité en ligne",
            "Rédaction web",
            "Relation client",
        ],
    },
    {
        "key": "organisation",
        "label": "Organisation et fiabilité",
        "skills": [
            "Sens de l'organisation",
            "Rigueur",
            "Gestion du temps",
            "Résolution de problèmes",
            "Autonomie",
            "Leadership",
            "Communication",
            "Travail en équipe",
        ],
    },
]

# Niveaux considérés comme « posés mais à consolider » (△).
_WEAK_LEVELS = {"debutant", "débutant", "notions", "faible"}


def list_resources(db: Session, kind: Optional[str] = None) -> list[dict]:
    """Ressources entrepreneuriat réelles (concours, accompagnement,
    financement, formation), éventuellement filtrées par type."""
    query = db.query(models.EntrepreneurResource)
    if kind:
        query = query.filter(models.EntrepreneurResource.kind == kind)
    items = query.order_by(models.EntrepreneurResource.id).all()
    return [
        {
            "id": r.id,
            "kind": r.kind,
            "kind_label": ENTREPRENEUR_KIND_LABELS.get(r.kind, r.kind),
            "title": r.title,
            "description": r.description,
            "organizer": r.organizer,
            "url": r.url,
            "sectors": r.sectors or [],
        }
        for r in items
    ]


def entrepreneur_profile(profile: Optional[dict], taxonomy=None) -> dict[str, Any]:
    """Lit le profil VALIDÉ et situe ses compétences entrepreneuriales
    par rapport au référentiel ci-dessus.

    Renvoie, par groupe : chaque compétence attendue avec son état
    (`covered` ✓, `partial` △, `missing` ○), puis les compétences du
    profil qui n'appartiennent pas au référentiel (le métier du porteur :
    c'est son premier capital, §48 « absence d'information ≠ absence de
    compétence »).
    """
    skills = list((profile or {}).get("skills") or [])
    # Nom canonique -> niveau déclaré, pour tout le profil.
    canonical_owned: dict[str, Optional[str]] = {}
    for entry in skills:
        name = (entry.get("skill") or entry.get("name") or "").strip()
        if not name:
            continue
        canonical = taxonomy.canonical(name) if taxonomy is not None else name
        canonical_owned.setdefault(canonical, entry.get("proficiency") or "")
    owned = {normalize(name): level for name, level in canonical_owned.items()}

    # Noms canoniques du référentiel (pour repérer ce qui est « hors
    # référentiel » : ce sont les compétences métier réelles du porteur).
    referential = {
        normalize(name)
        for group in ENTREPRENEUR_SKILL_GROUPS
        for name in group["skills"]
    }

    groups = []
    covered = partial = total = 0
    for group in ENTREPRENEUR_SKILL_GROUPS:
        items = []
        for name in group["skills"]:
            total += 1
            if normalize(name) not in owned:
                state, proficiency = "missing", None
            else:
                proficiency = owned[normalize(name)]
                state = "partial" if (proficiency or "").lower() in _WEAK_LEVELS else "covered"
            if state == "covered":
                covered += 1
            elif state == "partial":
                partial += 1
            items.append({
                "name": name,
                "state": state,
                "proficiency": proficiency or "",
            })
        groups.append({
            "key": group["key"],
            "label": group["label"],
            "items": items,
            "covered": sum(1 for i in items if i["state"] == "covered"),
            "partial": sum(1 for i in items if i["state"] == "partial"),
            "total": len(items),
        })

    coverage = round(100 * (covered + 0.5 * partial) / total) if total else 0
    trade = [
        {"name": name, "category": (taxonomy.category(name) if taxonomy is not None else "Autre")}
        for name in canonical_owned
        if normalize(name) not in referential
    ]
    return {
        "has_profile": profile is not None,
        "profile_title": (profile or {}).get("title"),
        "groups": groups,
        "covered_count": covered,
        "partial_count": partial,
        "missing_count": total - covered - partial,
        "total": total,
        "coverage": coverage,
        "trade_skills": trade[:10],
        "scored": total > 0,
    }
