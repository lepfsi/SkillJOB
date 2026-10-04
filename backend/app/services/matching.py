"""Job Matching Engine + Job Fit Score explicable (§11-§12).

Principe de calcul (déterministe et explicable) :
- chaque compétence « core » vaut 10 points, chaque « preferred » vaut 5 ;
- le niveau de maîtrise module les points obtenus
  (avancé = 100 %, intermédiaire = 85 %, débutant = « partiel » = 50 %) ;
- le score est la part des points obtenus sur le total possible (0-100).

Le résultat détaille toujours : couvertes / partielles / manquantes,
points forts, explication en français et actions recommandées.
"""
from typing import Any, Optional

from app.services.skills_taxonomy import SkillsTaxonomy

CORE_POINTS = 10.0
PREFERRED_POINTS = 5.0
PROFICIENCY_FACTOR = {"avance": 1.0, "intermediaire": 0.85, "debutant": 0.5}

LEVEL_STRONG = 75
LEVEL_MEDIUM = 45

_LEVEL_LABELS_FR = {
    "avance": "niveau avancé",
    "intermediaire": "niveau intermédiaire",
    "debutant": "niveau débutant",
}


def _profile_index(
    profile_skills: list[dict[str, Any]], taxonomy: Optional[SkillsTaxonomy]
) -> dict[str, dict[str, Any]]:
    """Nom canonique -> compétence du profil."""
    index: dict[str, dict[str, Any]] = {}
    for entry in profile_skills:
        name = str(entry.get("skill", "")).strip()
        if not name:
            continue
        canonical = taxonomy.canonical(name) if taxonomy else name
        index[canonical] = entry
    return index


def compute_match(
    profile_skills: list[dict[str, Any]],
    required_skills: list[dict[str, Any]],
    taxonomy: Optional[SkillsTaxonomy] = None,
) -> dict[str, Any]:
    """Calcule le Job Fit Score explicable entre un profil et une offre."""
    index = _profile_index(profile_skills, taxonomy)

    covered: list[str] = []
    partial: list[str] = []
    missing: list[str] = []
    strengths: list[str] = []
    missing_core: list[str] = []
    partial_core: list[str] = []
    core_total = core_covered = 0
    pref_total = pref_covered = 0
    earned = total = 0.0

    if not required_skills:
        return {
            "score": 50,
            "level": "moyenne",
            "covered": [], "partial": [], "missing": [], "strengths": [],
            "explanation": (
                "L'offre ne liste pas de compétences techniques précises : "
                "le score est neutre. Lisez attentivement la description pour "
                "vérifier l'adéquation avec votre profil."
            ),
            "recommended_actions": [
                "Analyser la description de l'offre pour identifier les "
                "compétences réellement attendues."
            ],
        }

    for req in required_skills:
        raw_name = str(req.get("name", "")).strip()
        name = taxonomy.canonical(raw_name) if taxonomy else raw_name
        importance = req.get("importance", "core")
        points = CORE_POINTS if importance == "core" else PREFERRED_POINTS
        total += points
        if importance == "core":
            core_total += 1
        else:
            pref_total += 1

        user_skill = index.get(name)
        if user_skill is None:
            missing.append(name)
            if importance == "core":
                missing_core.append(name)
            continue

        proficiency = user_skill.get("proficiency", "debutant")
        if proficiency == "debutant":
            partial.append(name)
            earned += points * 0.5
            if importance == "core":
                partial_core.append(name)
        else:
            covered.append(name)
            earned += points * PROFICIENCY_FACTOR.get(proficiency, 0.85)
            if importance == "core":
                core_covered += 1
                label = f"{name} ({_LEVEL_LABELS_FR.get(proficiency, '')})".strip()
            else:
                label = name
            if importance == "core" or proficiency == "avance":
                strengths.append(label)

    score = round(100 * earned / total) if total else 0
    level = "forte" if score >= LEVEL_STRONG else (
        "moyenne" if score >= LEVEL_MEDIUM else "faible"
    )

    strengths = strengths[:6]
    explanation = _build_explanation(
        score, level, core_total, core_covered, len(partial_core),
        pref_total, pref_covered, strengths, missing_core,
    )
    actions = _build_actions(missing_core, partial_core, missing, score)
    return {
        "score": score,
        "level": level,
        "covered": covered,
        "partial": partial,
        "missing": missing,
        "strengths": strengths,
        "explanation": explanation,
        "recommended_actions": actions,
    }


def _build_explanation(
    score: int, level: str, core_total: int, core_covered: int,
    partial_core_count: int, pref_total: int, pref_covered: int,
    strengths: list[str], missing_core: list[str],
) -> str:
    """Justification textuelle du score, en français (§12)."""
    parts = [
        f"Score de correspondance : {score}/100 (correspondance {level}).",
        (
            f"Compétences essentielles : {core_covered}/{core_total} couvertes"
            + (f" dont {partial_core_count} partiellement" if partial_core_count else "")
            + "."
        ),
    ]
    if pref_total:
        parts.append(
            f"Compétences souhaitées : {pref_covered}/{pref_total} couvertes."
        )
    if strengths:
        parts.append("Points forts : " + ", ".join(strengths) + ".")
    if missing_core:
        parts.append("Écarts principaux : " + ", ".join(missing_core) + ".")
    conclusions = {
        "forte": "Votre profil est fortement compatible : vous pouvez candidater en valorisant vos points forts.",
        "moyenne": "Votre profil est partiellement compatible : une courte montée en compétences ciblée peut renforcer votre candidature.",
        "faible": "Votre profil est encore éloigné de cette offre : envisagez un parcours de formation ou une offre plus accessible.",
    }
    parts.append(conclusions[level])
    return " ".join(parts)


def _build_actions(
    missing_core: list[str], partial_core: list[str], missing: list[str],
    score: int,
) -> list[str]:
    """Actions concrètes et explicables, en français."""
    actions: list[str] = []
    for name in missing_core[:3]:
        actions.append(
            f"Développer la compétence « {name} » (formation courte, projet pratique, stage)."
        )
    for name in partial_core[:2]:
        actions.append(
            f"Consolider « {name} » (niveau débutant acquis) : viser le niveau intermédiaire par la pratique."
        )
    for name in [m for m in missing if m not in missing_core][:2]:
        actions.append(
            f"Ajouter « {name} » à votre plan d'apprentissage (compétence souhaitée par l'offre)."
        )
    if score >= LEVEL_STRONG:
        actions.append(
            "Adapter votre CV à cette offre en mettant en avant vos compétences couvertes, puis candidater."
        )
    return actions
