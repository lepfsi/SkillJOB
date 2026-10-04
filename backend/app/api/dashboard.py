"""Dashboard orienté action (§27) + inbox calculée (§28) + briefing IA
variant (l'agent ne répète jamais la même phrase : formulations tirées
au sort, sujets réordonnés — contenu toujours factuel §47)."""
import random
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services.eventlog import _reference_now, build_inbox
from app.services.market import weekly_indicators
from app.services.matching import LEVEL_STRONG, compute_match
from app.services.profile_store import get_profile_row, profile_to_dict
from app.services.skills_taxonomy import load_taxonomy

router = APIRouter(prefix="/api", tags=["dashboard"])

CLOSED_STATUSES = {"acceptee", "refusee"}


@router.get("/dashboard", response_model=schemas.DashboardOut)
def dashboard(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    taxonomy = load_taxonomy()
    jobs = db.query(models.Job).all()
    applications = (
        db.query(models.Application)
        .filter(models.Application.user_id == user.id)
        .all()
    )
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    skills = profile.get("skills", []) if profile else []

    now = _reference_now(jobs)
    new_opportunities = sum(1 for j in jobs if (now - j.published_at).days <= 14)

    strong_matches: list[tuple[models.Job, dict]] = []
    gap_counter: Counter[str] = Counter()
    matches: dict[int, dict] = {}
    for job in jobs:
        if not profile:
            matches[job.id] = {}
            continue
        match = compute_match(skills, job.required_skills, taxonomy)
        matches[job.id] = match
        if match["score"] >= LEVEL_STRONG:
            strong_matches.append((job, match))
        for name in match.get("missing", []):
            core_names = {
                r["name"] for r in job.required_skills if r.get("importance") == "core"
            }
            if name in core_names:
                gap_counter[name] += 1
    skills_to_improve = [name for name, _ in gap_counter.most_common(5)]

    ongoing = [a for a in applications if a.status not in CLOSED_STATUSES]
    interviews = [a for a in applications if a.status == "entretien"]

    # Marché cette semaine : fenêtre réelle de 7 jours (indicateurs
    # traçables, §13bis), comparée aux 7 jours précédents.
    week = weekly_indicators(jobs)
    market_trends = week["skills"][:5]
    market_week = {
        "offers_in_period": week["offers_in_period"],
        "previous_period_offers": week["previous_period_offers"],
        "period_start": week["period_start"],
        "period_end": week["period_end"],
        "period_label": week["period_label"],
        "sectors": week["sectors"],
    }

    # Meilleure piste globale (pour le briefing et le top match)
    best_overall = None
    for job in jobs:
        match = matches.get(job.id)
        if not match:
            continue
        if best_overall is None or match["score"] > best_overall[1]["score"]:
            best_overall = (job, match)

    next_action = _next_action(user, profile, jobs, matches, applications, interviews)

    # Complétude du profil : chaque case vérifiable, chaque case actionnable
    completeness = None
    if profile:
        checks = [
            ("photo", "Ajouter une photo de profil", bool(user.photo_path)),
            ("identity", "Un titre professionnel clair", bool(profile.get("title"))),
            ("summary", "Un résumé de votre parcours", bool(profile.get("summary"))),
            ("experiences", "Vos expériences (même informelles)",
             len(profile.get("experiences", [])) > 0),
            ("education", "Votre formation ou vos recyclages",
             len(profile.get("education", [])) > 0),
            ("skills", "Au moins 3 compétences", len(profile.get("skills", [])) >= 3),
            ("languages", "Vos langues", len(profile.get("languages", [])) > 0),
            ("preferences", "Vos objectifs professionnels",
             bool((profile.get("preferences") or {}).get("target_roles"))),
            ("verified", "Faire vérifier votre identité",
             user.verification_status == "verified"),
        ]
        done = [k for k, _l, ok in checks if ok]
        completeness = {
            "score": round(len(done) / len(checks) * 100),
            "checked": [
                {"key": k, "label": label, "done": ok} for k, label, ok in checks
            ],
            "missing": [label for _k, label, ok in checks if not ok],
        }

    # Top match : la meilleure piste du moment, concrète et cliquable
    top_matches = []
    if strong_matches:
        top_matches = [
            {
                "id": job.id, "title": job.title, "company": job.company,
                "location": job.location, "contract_type": job.contract_type,
                "score": match["score"],
            }
            for job, match in sorted(strong_matches, key=lambda t: -t[1]["score"])[:2]
        ]
    elif best_overall:
        job, match = best_overall
        top_matches = [{
            "id": job.id, "title": job.title, "company": job.company,
            "location": job.location, "contract_type": job.contract_type,
            "score": match["score"],
        }]

    label, briefing = _ai_briefing(
        user, profile, jobs, matches, strong_matches, applications,
        interviews, best_overall, completeness, new_opportunities,
    )

    return {
        "name": user.full_name,
        "new_opportunities": new_opportunities,
        "strong_matches": len(strong_matches),
        "skills_to_improve": skills_to_improve,
        "ongoing_applications": len(ongoing),
        "interviews_to_prepare": len(interviews),
        "market_trends": market_trends,
        "market_week": market_week,
        "next_action": next_action,
        "ai_briefing": briefing,
        "ai_label": label,
        "profile_completeness": completeness,
        "top_matches": top_matches,
    }


_BRIEFING_LABELS = [
    "Ce que j'ai repéré pour toi aujourd'hui",
    "Ton assistant a travaillé pour toi",
    "Le point du jour",
    "Ce que je vois dans tes données",
    "Trois choses à savoir",
]


def _ai_briefing(
    user, profile, jobs, matches, strong_matches, applications,
    interviews, best_overall, completeness, new_opportunities,
):
    """Briefing personnalisé, FACTUEL mais vivant : plusieurs
    formulations par sujet, ordre tiré au sort, tutoiement (persona
    Ori). Retourne (libellé, texte). Chaque affirmation vient des
    données réelles (§47)."""
    if profile is None:
        return (
            random.choice(_BRIEFING_LABELS[:2]),
            random.choice([
                "Bienvenue ! Je n'ai encore rien à analyser : importe ton CV "
                "ou réponds au questionnaire, et je me charge du reste — "
                "compétences, métiers visés et correspondances.",
                "Salut ! Je n'ai encore aucune donnée sur toi. Importe ton "
                "CV, je m'occupe du reste.",
            ]),
        )

    first = (user.full_name or "").split(" ")[0]
    observations: list[str] = []

    # ---- Sujet : meilleure correspondance
    if strong_matches:
        job, match = max(strong_matches, key=lambda t: t[1]["score"])
        if len(strong_matches) == 1:
            observations.append(random.choice([
                f"j'ai comparé ton profil aux {len(jobs)} offres actives : "
                f"une te correspond fortement, « {job.title} » chez "
                f"{job.company} ({match['score']}/100).",
                f"une piste se détache : « {job.title} » chez {job.company}, "
                f"correspondance {match['score']}/100 — la meilleure du moment.",
            ]))
        else:
            n = len(strong_matches)
            observations.append(random.choice([
                f"j'ai comparé ton profil aux {len(jobs)} offres actives : "
                f"{n} te correspondent fortement. La meilleure : "
                f"« {job.title} » chez {job.company} ({match['score']}/100).",
                f"bonne nouvelle : {n} offres te correspondent bien, dont "
                f"« {job.title} » chez {job.company} ({match['score']}/100).",
            ]))
    elif best_overall:
        job, match = best_overall
        observations.append(random.choice([
            f"la piste la plus proche est « {job.title} » chez {job.company} "
            f"({match['score']}/100) — encore perfectible.",
            f"rien de parfait pour l'instant, mais « {job.title} » chez "
            f"{job.company} reste ta meilleure option ({match['score']}/100).",
        ]))

    # ---- Sujet : entretien (prioritaire, on le met souvent en tête)
    if interviews:
        n = len(interviews)
        mot = "entretien" if n == 1 else "entretiens"
        observations.append(random.choice([
            f"tu as {n} {mot} à préparer — je peux générer les questions "
            "probables et ton pitch.",
            f"il te reste {n} {mot} à préparer : on le simule ensemble ?",
            f"pense à ton {mot} à venir : je peux te préparer une simulation "
            "complète.",
        ]))
    elif applications:
        ongoing = [a for a in applications if a.status not in ("acceptee", "refusee")]
        if ongoing:
            n = len(ongoing)
            observations.append(random.choice([
                f"{n} candidature" + ("s" if n > 1 else "") + " en cours — "
                "pense aux relances au-delà de dix jours sans réponse.",
                f"côté candidatures, {n} dossier"
                + ("s" if n > 1 else "") + " en attente : une relance peut "
                "débloquer la situation.",
            ]))

    # ---- Sujet : marché (parfois mentionné)
    if new_opportunities > 0 and random.random() < 0.6:
        n = new_opportunities
        observations.append(random.choice([
            f"{n} nouvelle" + ("s" if n > 1 else "") + " offre"
            + ("s" if n > 1 else "") + " sondée" + ("s" if n > 1 else "")
            + " cette semaine.",
        ]))

    # ---- Compose : ouverture + 2 sujets tirés au sort + conseil final
    random.shuffle(observations)
    lead = observations[:2]

    tip = ""
    if completeness and completeness["missing"]:
        tip = random.choice([
            "Pour renforcer ton profil : " + completeness["missing"][0].lower() + ".",
            "Petit chantier possible : " + completeness["missing"][0].lower() + ".",
        ])

    greeting = random.choice([
        f"{first}, ",
        f"Salut {first} ! ",
        f"Tiens {first}, ",
        "",
    ])
    text = greeting + " ".join(lead)
    if tip:
        text = (text + " " + tip).strip()
    return random.choice(_BRIEFING_LABELS), _polish_sentences(text)


def _polish_sentences(text: str) -> str:
    """Typographie : chaque phrase démarre par une majuscule (les
    observations sont assemblées dynamiquement)."""
    import re as _re

    def upper_first(match):
        return match.group(1) + match.group(2).upper()

    return _re.sub(r"([.!?] )([a-zà-ÿ])", upper_first, text[:1].upper() + text[1:])


def _next_action(user, profile, jobs, matches, applications, interviews) -> dict:
    """Prochaine action prioritaire, ancrée sur les données réelles."""
    if interviews:
        return {
            "label": f"Préparer l'entretien pour « {interviews[0].job.title} »",
            "type": "prepare_interview",
            "job_id": interviews[0].job_id,
        }
    applied_ids = {a.job_id for a in applications}
    best = None
    for job in jobs:
        match = matches.get(job.id)
        if not match:
            continue
        if best is None or match["score"] > best[1]["score"]:
            best = (job, match)
    if best and best[1]["score"] >= LEVEL_STRONG and best[0].id not in applied_ids:
        return {
            "label": f"Adapter votre CV pour « {best[0].title} » chez {best[0].company}",
            "type": "adapt_cv",
            "job_id": best[0].id,
        }
    if profile:
        gaps: Counter[str] = Counter()
        for job in jobs:
            for name in matches.get(job.id, {}).get("missing", []):
                gaps[name] += 1
        if gaps:
            top_skill = gaps.most_common(1)[0][0]
            return {
                "label": f"Développer la compétence « {top_skill} » demandée par le marché",
                "type": "learn",
                "skill": top_skill,
            }
    if best and best[0].id not in applied_ids:
        return {
            "label": f"Candidater à « {best[0].title} » chez {best[0].company}",
            "type": "apply",
            "job_id": best[0].id,
        }
    return {
        "label": "Complétez votre profil pour débloquer les recommandations",
        "type": "learn",
        "skill": None,
    }


@router.get("/inbox", response_model=list[schemas.InboxEvent])
def inbox(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    jobs = db.query(models.Job).all()
    applications = (
        db.query(models.Application)
        .filter(models.Application.user_id == user.id)
        .all()
    )
    return build_inbox(profile, jobs, applications, load_taxonomy())
