"""Orientation Intelligence Engine (§9 / §9bis).

Rapproche le profil de chaque métier de la base et produit :
- un score de compatibilité (même logique explicable que le matching) ;
- une accessibilité : immediate | with_upskilling | long_term ;
- des actions recommandées concrètes.
"""
from typing import Any, Optional

from app.services.matching import LEVEL_MEDIUM, LEVEL_STRONG, compute_match
from app.services.skills_taxonomy import SkillsTaxonomy

_FUTURE_MAP = {
    "immediate": "ce métier est accessible immédiatement avec votre profil actuel.",
    "with_upskilling": "ce métier est accessible après une montée en compétences ciblée.",
    "long_term": "ce métier demande un parcours de formation plus long.",
}


def match_career(
    profile_skills: list[dict[str, Any]],
    career: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
) -> dict[str, Any]:
    """Calcule la compatibilité profil <-> métier."""
    required = list(getattr(career, "required_skills", None) or career["required_skills"])
    match = compute_match(profile_skills, required, taxonomy)

    core_missing = [
        r.get("name", "")
        for r in required
        if r.get("importance", "core") == "core" and (
            taxonomy.canonical(r["name"]) if taxonomy else r["name"]
        ) in match["missing"]
    ]

    if match["score"] >= LEVEL_STRONG and not core_missing:
        accessibility = "immediate"
    elif match["score"] >= LEVEL_MEDIUM:
        accessibility = "with_upskilling"
    else:
        accessibility = "long_term"

    actions: list[str] = []
    if core_missing:
        actions.append(
            "Prioriser l'apprentissage de : " + ", ".join(core_missing[:3]) + "."
        )
    if match["partial"]:
        actions.append(
            "Renforcer : " + ", ".join(match["partial"][:3])
            + " (du niveau débutant vers intermédiaire)."
        )
    if accessibility == "immediate":
        actions.append(
            "Rechercher des offres de « "
            + str(getattr(career, "title", "") or career["title"])
            + " » et adapter votre CV en conséquence."
        )
    elif accessibility == "with_upskilling":
        actions.append(
            "Suivre une courte formation ou un projet pratique couvrant "
            "les écarts identifiés, puis candidater."
        )
    else:
        actions.append(
            "Envisager une formation qualifiante ou un stage d'entrée dans "
            "cette famille de métiers."
        )

    return {
        "score": match["score"],
        "covered": match["covered"] + match["partial"],
        "missing": match["missing"],
        "accessibility": accessibility,
        "recommended_actions": actions[:4],
        "explanation": match["explanation"] + " "
        + "Globalement, " + _FUTURE_MAP[accessibility],
    }
