"""Learning & Upskilling Engine (§19) + progression vérifiable.

Logique de recommandation (refonte) :
- « À apprendre maintenant » suit les MÉTIERS recommandés du jeune
  (§9bis) : les ressources ciblent les compétences manquantes des
  métiers qui le correspondent le mieux, pas une liste générique ;
- « Perfectionner mon domaine » : ressources pour les compétences
  DÉJÀ acquises (son domaine de force), certifications en priorité ;
- « Ensuite » : autres écarts face aux offres actives ;
- progression vérifiable : preuves issues du profil par compétence.
Aucune ressource ou preuve n'est inventée (§47).
"""
import json
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from typing import Any, Optional

from app import config
from app.services.learning_tracking import (
    LINK_KINDS,
    LINK_KIND_LABELS,
    evidence_for,
    infer_link_kind,
    is_verifiable,
)
from app.services.matching import compute_match
from app.services.skills_taxonomy import SkillsTaxonomy

_ALLOWED_TYPES = {"course", "certification", "project", "free"}
LEVEL_LABELS = {
    "avance": "Avancé",
    "intermediaire": "Intermédiaire",
    "debutant": "Débutant",
}
STATUS_LABELS = {
    "verifiee": "Appuyée par des preuves",
    "a_confirmer": "À confirmer",
    "en_progression": "En progression",
}


def _slug(value: str) -> str:
    """Identifiant lisible et stable pour une ressource (lien profond)."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "ressource"


def resource_key(skill: str, title: str) -> str:
    """Clé publique d'une ressource : compétence + intitulé.

    Elle ne dépend ni de l'ordre du fichier ni de l'identifiant SQLite :
    un lien partagé reste valable après une synchronisation du référentiel.
    """
    return f"{_slug(skill)[:42]}--{_slug(title)[:72]}"


def _normalize_resource(resource: dict[str, Any], skill: str = "") -> dict[str, Any]:
    """Ressource prête à l'affichage : la nature du lien (formation
    exacte, catalogue, recherche, organisme local) est explicite."""
    item = dict(resource)
    url = item.get("url")
    link_kind = item.get("link_kind")
    if link_kind not in LINK_KINDS:
        link_kind = infer_link_kind(url, item.get("provider", ""))
    item["link_kind"] = link_kind
    item["link_kind_label"] = LINK_KIND_LABELS.get(link_kind, "Lien")
    item["key"] = resource_key(skill or item.get("skill", ""), item.get("title", ""))
    return item


@lru_cache(maxsize=1)
def load_resources() -> dict[str, list[dict[str, Any]]]:
    path = config.DATA_DIR / "learning_resources.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return {
        skill: [
            _normalize_resource(r, skill)
            for r in resources
            if r.get("type") in _ALLOWED_TYPES
        ]
        for skill, resources in raw.items()
    }


def _diversify(resources: list[dict], limit: int = 3) -> list[dict]:
    """Évite les doublons de TYPE et de FOURNISSEUR : un cours, une
    certification, un projet, et pas trois fois le même organisme. Les
    liens vers la formation exacte passent devant les catalogues."""
    if not resources:
        return []
    ordered = sorted(
        resources,
        key=lambda r: (
            0 if r.get("link_kind") == "exact"
            else 1 if r.get("link_kind") == "catalogue"
            else 2
        ),
    )
    out: list[dict] = []
    types: set[str] = set()
    providers: set[str] = set()

    def provider_of(item: dict) -> str:
        return (item.get("provider") or "").lower()

    for r in ordered:  # 1) un type et un fournisseur différents à chaque fois
        if r.get("type", "free") in types or provider_of(r) in providers:
            continue
        types.add(r.get("type", "free"))
        providers.add(provider_of(r))
        out.append(r)
        if len(out) >= limit:
            return out
    for r in ordered:  # 2) même type accepté, fournisseur toujours différent
        if r in out or provider_of(r) in providers:
            continue
        providers.add(provider_of(r))
        out.append(r)
        if len(out) >= limit:
            return out
    for r in ordered:  # 3) on complète si le référentiel est pauvre
        if r in out:
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out[:limit]


def _build_evidences(
    profile: dict[str, Any],
    skill_name: str,
    enrollments: Optional[list[Any]] = None,
) -> list[dict[str, str]]:
    """Preuves vérifiables rattachées à la compétence : profil validé
    (expériences, projets, certifications) + formations suivies dont la
    preuve a été fournie (§19)."""
    evidences: list[dict[str, str]] = []
    for e in profile.get("experiences", []):
        if skill_name in (e.get("skills") or []):
            label = e.get("title") or "Expérience"
            if e.get("organization"):
                label += f" · {e['organization']}"
            evidences.append({"kind": "experience", "label": label})
    for p in profile.get("projects", []):
        if skill_name in (p.get("skills") or []):
            evidences.append({"kind": "project", "label": p.get("name") or "Projet"})
    for c in profile.get("certifications", []):
        name = c.get("name", "")
        if skill_name.lower() in name.lower():
            issuer = f" · {c['issuer']}" if c.get("issuer") else ""
            evidences.append({"kind": "certification", "label": f"{name}{issuer}"})
    for enrollment in enrollments or []:
        if enrollment.skill == skill_name and is_verifiable(enrollment):
            evidences.append(evidence_for(enrollment))
    return evidences[:4]


def _next_step(skill_name: str, evidences: list[dict]) -> str:
    has_certif = any(e["kind"] == "certification" for e in evidences)
    if not evidences:
        return (
            f"Ajoutez au profil une expérience, un projet ou une certification "
            f"où vous utilisez « {skill_name} » : une compétence déclarée sans "
            "preuve pèse moins dans le matching."
        )
    if not has_certif:
        return (
            f"Une certification reconnue sur « {skill_name} » transformerait "
            "cette compétence en preuve forte pour les recruteurs."
        )
    return (
        f"« {skill_name} » est bien documentée : maintenez-la à jour avec vos "
        "réalisations les plus récentes."
    )


def build_progress(
    profile: dict[str, Any],
    jobs: list[Any],
    taxonomy: Optional[SkillsTaxonomy] = None,
    enrollments: Optional[list[Any]] = None,
) -> list[dict[str, Any]]:
    """Progression vérifiable par compétence du profil."""
    demand: Counter[str] = Counter()
    for job in jobs:
        for r in job.required_skills:
            name = taxonomy.canonical(r["name"]) if taxonomy else r["name"]
            demand[name] += 1

    out: list[dict[str, Any]] = []
    for s in profile.get("skills", []):
        name = s["skill"]
        evidences = _build_evidences(profile, name, enrollments)
        proficiency = s.get("proficiency", "debutant")
        if evidences:
            status = "verifiee"
        elif s.get("source") == "evidence":
            status = "verifiee"
        elif s.get("evidence_count", 0) > 0:
            status = "en_progression"
        else:
            status = "a_confirmer"
        out.append({
            "skill": name,
            "level": LEVEL_LABELS.get(proficiency, "Débutant"),
            "status": status,
            "status_label": STATUS_LABELS[status],
            "demand": demand.get(name, 0),
            "evidences": evidences,
            "next_step": _next_step(name, evidences),
        })
    out.sort(key=lambda p: (-p["demand"], p["status"] != "verifiee"))
    return out


def admin_resources(db) -> dict[str, list[dict[str, Any]]]:
    """Formations AJOUTÉES dans la console d'administration.

    Elles vivent en base (source « admin ») : la synchronisation du
    référentiel JSON ne les touche jamais. Renvoyées au même format que
    ``load_resources`` pour fusionner proprement.
    """
    from app import models

    rows = (
        db.query(models.LearningResource)
        .filter(
            models.LearningResource.source == "admin",
            models.LearningResource.hidden.is_(False),
        )
        .all()
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.type not in _ALLOWED_TYPES:
            continue
        out.setdefault(row.skill, []).append(_normalize_resource({
            "skill": row.skill,
            "title": row.title,
            "provider": row.provider or "",
            "type": row.type,
            "url": row.url,
        }, row.skill))
    return out


def visible_resources(db) -> dict[str, list[dict[str, Any]]]:
    """Catalogue réel proposé aux candidats, lu en base.

    Contrairement à ``load_resources`` (qui lit le référentiel JSON),
    cette fonction respecte les retouches de la console : une ligne
    masquée n'est jamais proposée, une ligne corrigée garde son nouveau
    lien. Le JSON sert uniquement de référentiel initial.
    """
    from app import models

    rows = (
        db.query(models.LearningResource)
        .filter(models.LearningResource.hidden.is_(False))
        .order_by(models.LearningResource.skill, models.LearningResource.title)
        .all()
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.type not in _ALLOWED_TYPES:
            continue
        out.setdefault(row.skill, []).append(_normalize_resource({
            "skill": row.skill,
            "title": row.title,
            "provider": row.provider or "",
            "type": row.type,
            "url": row.url,
        }, row.skill))
    return out


def learning_plan(
    profile: dict[str, Any],
    jobs: list[Any],
    taxonomy: Optional[SkillsTaxonomy] = None,
    careers: Optional[list[Any]] = None,
    enrollments: Optional[list[Any]] = None,
    admin_resources: Optional[dict[str, list[dict[str, Any]]]] = None,
    resources_map: Optional[dict[str, list[dict[str, Any]]]] = None,
) -> dict[str, Any]:
    """Plan d'apprentissage PERSONNALISÉ :
    - maintenant : écarts des métiers recommandés (le domaine visé) ;
    - perfectionner : ressources sur ses acquis (son domaine actuel) ;
    - ensuite : autres écarts face aux offres actives ;
    - progression : vérifiable (preuves, formations suivies comprises)."""
    if resources_map is None:
        resources_map = load_resources()
        if admin_resources:
            merged = dict(resources_map)
            for skill, items in admin_resources.items():
                merged[skill] = resources_map.get(skill, []) + items
            resources_map = merged
    profile_skills = profile.get("skills", []) if profile else []

    # ----------------------------------------------------------
    # 1) « À apprendre maintenant » : suit les métiers recommandés.
    # ----------------------------------------------------------
    learn_now: list[dict[str, Any]] = []
    seen_skills: set[str] = set()
    if profile and careers:
        from app.services.orientation import match_career

        scored = [(c, match_career(profile_skills, c, taxonomy)) for c in careers]
        scored.sort(key=lambda t: t[1]["score"], reverse=True)
        for career, m in scored[:3]:
            missing_here = [s for s in m["missing"][:2] if s not in seen_skills]
            if not missing_here:
                continue
            for name in missing_here:
                seen_skills.add(name)
                learn_now.append({
                    "skill": name,
                    "reason": (
                        f"Compétence manquante pour viser « {career.title} » "
                        f"(métier recommandé, score {m['score']}/100) : "
                        "la combler vous y rend immédiatement plus crédible."
                    ),
                    "resources": _diversify(resources_map.get(name, [])),
                })
                if len(learn_now) >= 3:
                    break
            if len(learn_now) >= 3:
                break

    # ----------------------------------------------------------
    # 2) « Perfectionner mon domaine » : les acquis du jeune.
    # ----------------------------------------------------------
    improve: list[dict[str, Any]] = []
    if profile_skills:
        ranked = sorted(
            profile_skills,
            key=lambda s: (s.get("evidence_count", 0), s.get("proficiency") == "avance"),
            reverse=True,
        )[:5]
        for s in ranked:
            resources = _diversify(resources_map.get(s["skill"], []), limit=2)
            if not resources:
                continue
            improve.append({
                "skill": s["skill"],
                "reason": (
                    f"Vous maîtrisez déjà « {s['skill']} » : une certification "
                    "ou un projet reconnu transforme cette force en avantage "
                    "décisif face aux autres candidats."
                ),
                "resources": resources,
            })

    # ----------------------------------------------------------
    # 3) « Ensuite » : autres écarts face aux offres actives.
    # ----------------------------------------------------------
    gap_weight: Counter[str] = Counter()
    gap_offers: Counter[str] = Counter()
    for job in jobs:
        match = compute_match(profile_skills, job.required_skills, taxonomy)
        for name in match["missing"]:
            if name in seen_skills:
                continue
            weight = (
                2
                if any(
                    r.get("importance") == "core" and
                    (taxonomy.canonical(r["name"]) if taxonomy else r["name"]) == name
                    for r in job.required_skills
                )
                else 1
            )
            gap_weight[name] += weight
            gap_offers[name] += 1

    learn_next = []
    for name, _ in gap_weight.most_common(8):
        if len(learn_next) >= 4:
            break
        count = gap_offers[name]
        learn_next.append({
            "skill": name,
            "reason": f"Compétence demandée par {count} offre(s) active(s).",
            "resources": _diversify(resources_map.get(name, [])),
        })

    progress = build_progress(profile, jobs, taxonomy, enrollments) if profile else []

    return {
        "learn_now": learn_now,
        "improve": improve,
        "learn_next": learn_next,
        "progress": progress,
    }
