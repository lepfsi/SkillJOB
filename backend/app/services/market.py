"""Market Intelligence (§13) : statistiques DÉTERMINISTES sur les offres.

Toutes les tendances sont calculées à partir des offres de la base
(source + date traçables), jamais d'affirmations génériques.

« Marché cette semaine » : fenêtre calendaire réelle de 7 jours (les
indicateurs affichés proviennent exclusivement des offres publiées sur
cette période, comparées aux 7 jours précédents).
"""
from collections import Counter
from datetime import datetime, timedelta
from typing import Any


def _split_recent(jobs: list[Any]) -> tuple[list[Any], list[Any]]:
    """Partage les offres en deux moitiés (anciennes / récentes) par date."""
    ordered = sorted(jobs, key=lambda j: j.published_at)
    mid = max(len(ordered) // 2, 1)
    return ordered[:mid], ordered[mid:]


def _skill_counts(jobs: list[Any], weighted: bool = False) -> Counter:
    counts: Counter[str] = Counter()
    for job in jobs:
        for req in job.required_skills or []:
            name = req.get("name")
            if not name:
                continue
            weight = 2 if weighted and req.get("importance") == "core" else 1
            counts[name] += weight
    return counts


def skills_market(jobs: list[Any]) -> list[dict[str, Any]]:
    """GET /api/skills/market : demande et tendance par compétence."""
    old, recent = _split_recent(jobs)
    old_counts, recent_counts = _skill_counts(old), _skill_counts(recent)
    all_counts = _skill_counts(jobs)

    old_total = sum(old_counts.values()) or 1
    recent_total = sum(recent_counts.values()) or 1

    entries = []
    for name, count in all_counts.most_common():
        old_share = old_counts.get(name, 0) / old_total
        new_share = recent_counts.get(name, 0) / recent_total
        pct = round((new_share - old_share) / old_share * 100) if old_share else (
            100 if count else 0
        )
        trend = "up" if pct >= 10 else ("down" if pct <= -10 else "stable")
        entries.append(
            {"name": name, "demand_count": count, "trend": trend, "pct_change": pct}
        )
    return entries


def market_trends(jobs: list[Any]) -> dict[str, Any]:
    """GET /api/market/trends."""
    market = skills_market(jobs)
    top = [{"name": m["name"], "count": m["demand_count"]} for m in market[:10]]
    trending_up = [m["name"] for m in market if m["trend"] == "up"][:8]
    trending_down = [m["name"] for m in market if m["trend"] == "down"][:8]

    old, recent = _split_recent(jobs)
    old_counts, recent_counts = _skill_counts(old), _skill_counts(recent)
    emerging = [
        name for name in recent_counts
        if old_counts.get(name, 0) == 0 and recent_counts[name] > 0
    ]
    emerging = sorted(emerging, key=lambda n: recent_counts[n], reverse=True)[:5]

    sectors = Counter(j.sector for j in jobs)
    return {
        "top_skills": top,
        "trending_up": trending_up,
        "trending_down": trending_down,
        "sectors": [{"name": s, "offers": c} for s, c in sectors.most_common()],
        "emerging": emerging,
    }


# ------------------------------------------- indicateurs hebdo réels

def weekly_indicators(jobs: list[Any]) -> dict[str, Any]:
    """Fenêtre réelle des 7 derniers jours, comparée aux 7 précédents.

    Chaque nombre affiché est traçable : il provient d'offres datées et
    sourcées de la base (§13bis : pas d'affirmation générique).
    """
    if not jobs:
        return {
            "offers_in_period": 0, "previous_period_offers": 0,
            "period_start": None, "period_end": None, "period_label": "",
            "skills": [], "sectors": [],
        }
    reference = max(j.published_at for j in jobs)
    week_start = reference - timedelta(days=7)
    prev_start = reference - timedelta(days=14)

    this_week = [j for j in jobs if j.published_at > week_start]
    prev_week = [j for j in jobs if prev_start < j.published_at <= week_start]

    counts_this = _skill_counts(this_week, weighted=True)
    counts_prev = _skill_counts(prev_week, weighted=True)
    total_this = sum(counts_this.values()) or 1
    total_prev = sum(counts_prev.values()) or 1

    skills = []
    for name, count in counts_this.most_common(8):
        share_now = count / total_this
        share_prev = counts_prev.get(name, 0) / total_prev
        pct = round((share_now - share_prev) / share_prev * 100) if share_prev else (
            100 if counts_prev.get(name, 0) == 0 and count else 0
        )
        trend = "up" if pct >= 10 else ("down" if pct <= -10 else "stable")
        skills.append({"name": name, "count": count, "trend": trend, "pct_change": pct})

    sectors = Counter(j.sector for j in this_week)
    fmt = lambda d: d.strftime("%d/%m")  # noqa: E731
    return {
        "offers_in_period": len(this_week),
        "previous_period_offers": len(prev_week),
        "period_start": week_start.isoformat(timespec="seconds"),
        "period_end": reference.isoformat(timespec="seconds"),
        "period_label": f"{fmt(week_start)} au {fmt(reference)}",
        "skills": skills,
        "sectors": [{"name": s, "offers": c} for s, c in sectors.most_common(5)],
    }
