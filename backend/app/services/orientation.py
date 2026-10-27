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
        # Score explicable (§12) : mêmes clés que le matching d'offres,
        # plus l'horizon d'accès propre à l'orientation.
        "score": match["score"],
        "level": match["level"],
        "covered": match["covered"],
        "partial": match["partial"],
        "missing": match["missing"],
        "strengths": match["strengths"],
        "accessibility": accessibility,
        "recommended_actions": actions[:4],
        "explanation": match["explanation"] + " "
        + "Globalement, " + _FUTURE_MAP[accessibility],
    }


def prioritized_skill_gaps(
    profile_skills: list[dict[str, Any]],
    jobs: list[Any],
    careers: list[Any],
    taxonomy: Optional[SkillsTaxonomy] = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Écarts prioritaires orientés métiers, avec raison et source.

    On part des métiers qui correspondent le mieux au profil, puis des
    meilleures offres. Chaque écart est explicable : le candidat sait
    pourquoi cette compétence remonte et de quelle source elle vient.
    """
    if not profile_skills or limit <= 0:
        return []

    gaps: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_gap(
        name: str,
        reason: str,
        source: str,
        source_label: str,
        score: int,
    ) -> bool:
        if not name or name in seen:
            return False
        seen.add(name)
        gaps.append({
            "skill": name,
            "reason": reason,
            "source": source,
            "source_label": source_label,
            "score": score,
        })
        return len(gaps) >= limit

    def core_names(required_skills: list[dict[str, Any]]) -> set[str]:
        names = set()
        for item in required_skills:
            if item.get("importance", "core") != "core":
                continue
            raw = str(item.get("name", "")).strip()
            names.add(taxonomy.canonical(raw) if taxonomy else raw)
        return names

    scored_careers = [
        (career, match_career(profile_skills, career, taxonomy))
        for career in careers
    ]
    scored_careers.sort(key=lambda pair: pair[1]["score"], reverse=True)
    for career, match in scored_careers[:3]:
        if match["score"] < LEVEL_MEDIUM:
            continue
        title = str(getattr(career, "title", "") or "")
        core = core_names(list(getattr(career, "required_skills", None) or []))
        for name in match["missing"]:
            importance = "clé" if name in core else "complémentaire"
            if add_gap(
                name,
                f"Compétence {importance} manquante pour viser « {title} » "
                f"(métier recommandé, score {match['score']}/100).",
                "career",
                title,
                match["score"],
            ):
                return gaps

    scored_jobs = [
        (job, compute_match(profile_skills, job.required_skills, taxonomy))
        for job in jobs
    ]
    scored_jobs.sort(key=lambda pair: pair[1]["score"], reverse=True)
    for job, match in scored_jobs[:5]:
        if match["score"] < LEVEL_MEDIUM:
            continue
        title = str(getattr(job, "title", "") or "")
        company = str(getattr(job, "company", "") or "")
        label = f"{title} · {company}" if company else title
        core = core_names(list(getattr(job, "required_skills", None) or []))
        for name in match["missing"]:
            importance = "clé" if name in core else "complémentaire"
            if add_gap(
                name,
                f"Compétence {importance} demandée par « {title} »"
                + (f" chez {company}" if company else "")
                + f" (correspondance {match['score']}/100).",
                "job",
                label,
                match["score"],
            ):
                return gaps

    return gaps
