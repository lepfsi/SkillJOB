"""Inbox (§28) : événements CALCULÉS à la demande (non persistés).

Sources d'événements : nouvelles offres compatibles, matches forts,
candidatures suivies, tendances de marché, recommandations d'apprentissage.
"""
from datetime import datetime
from typing import Any, Optional

from app.models import utcnow
from app.services.matching import LEVEL_STRONG, compute_match


def _as_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _reference_now(jobs: list[Any]) -> datetime:
    """Horloge déterministe : date de publication la plus récente."""
    return max((_as_dt(j.published_at) for j in jobs), default=utcnow())


def build_inbox(
    profile: Optional[dict],
    jobs: list[Any],
    applications: list[Any],
    taxonomy=None,
) -> list[dict[str, Any]]:
    now = _reference_now(jobs)
    events: list[dict[str, Any]] = []

    # Nouvelles offres récentes (fenêtre de 21 jours avant l'offre la plus fraîche)
    for job in sorted(jobs, key=lambda j: j.published_at, reverse=True):
        if (now - job.published_at).days <= 21:
            events.append({
                "at": job.published_at,
                "kind": "new_job",
                "message": f"Nouvelle offre : « {job.title} » chez {job.company} ({job.location}).",
                "job_id": job.id,
            })

    # Matches forts et candidatures
    if profile:
        profile_skills = profile.get("skills", [])
        for job in jobs:
            match = compute_match(profile_skills, job.required_skills, taxonomy)
            if match["score"] >= LEVEL_STRONG:
                events.append({
                    "at": job.published_at,
                    "kind": "strong_match",
                    "message": (
                        f"Correspondance forte ({match['score']}/100) avec "
                        f"« {job.title} » chez {job.company} : pensez à candidater."
                    ),
                    "job_id": job.id,
                })
        missing: list[str] = []
        for job in jobs[:10]:
            for name in compute_match(profile_skills, job.required_skills, taxonomy)["missing"]:
                if name not in missing:
                    missing.append(name)
        if missing:
            events.append({
                "at": now,
                "kind": "learning",
                "message": (
                    f"Compétence à développer en priorité : « {missing[0]} » "
                    f"(voir la page Apprentissage)."
                ),
                "job_id": None,
            })

    STATUS_LABELS = {
        "identifiee": "identifiée", "cv_prepare": "CV préparé",
        "envoyee": "envoyée", "en_attente": "en attente de réponse",
        "entretien": "entretien à préparer", "offre": "offre reçue",
        "acceptee": "acceptée", "refusee": "refusée",
    }
    for app in applications:
        latest = app.timeline[-1] if app.timeline else None
        job_title = app.job.title if app.job else f"offre #{app.job_id}"
        events.append({
            "at": _as_dt(latest["at"]) if latest else app.created_at,
            "kind": "application",
            "message": (
                f"Candidature « {job_title} » : "
                f"{STATUS_LABELS.get(app.status, app.status)}."
            ),
            "job_id": app.job_id,
        })

    events += market_trend_events(jobs)

    events.sort(key=lambda e: e["at"], reverse=True)
    for i, event in enumerate(events[:20], start=1):
        event["id"] = i
    return events[:20]


def market_trend_events(jobs: list[Any]) -> list[dict[str, Any]]:
    """Événements de tendance, calculés depuis les offres traçables."""
    from app.services.market import skills_market

    now = _reference_now(jobs)
    events = []
    for entry in skills_market(jobs):
        if entry["trend"] == "up":
            events.append({
                "at": now,
                "kind": "trend",
                "message": (
                    f"Tendance : la demande en « {entry['name']} » progresse "
                    f"de {entry['pct_change']} % sur les offres récentes."
                ),
                "job_id": None,
            })
    return events[:3]
