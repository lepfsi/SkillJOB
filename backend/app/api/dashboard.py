"""Dashboard orienté action (§27) + inbox calculée (§28) + briefing IA
variant (l'agent ne répète jamais la même phrase : formulations tirées
au sort, sujets réordonnés, contenu toujours factuel §47)."""
import random
from collections import Counter
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services import agent_prefs
from app.services.applications import CLOSED_STATUSES
from app.services.eventlog import _reference_now, build_inbox
from app.services import interviews as interview_service
from app.services.notifications import normalize_prefs
from app.services.market import weekly_indicators
from app.services.matching import LEVEL_STRONG, compute_match
from app.services.orientation import prioritized_skill_gaps
from app.services.profile_store import get_profile_row, profile_to_dict
from app.services.skills_taxonomy import load_taxonomy

router = APIRouter(prefix="/api", tags=["dashboard"])


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
    matches: dict[int, dict] = {}
    for job in jobs:
        if not profile:
            matches[job.id] = {}
            continue
        match = compute_match(skills, job.required_skills, taxonomy)
        matches[job.id] = match
        if match["score"] >= LEVEL_STRONG:
            strong_matches.append((job, match))

    # Écarts priorisés par les métiers qui correspondent au profil, puis par
    # les meilleures offres. Fini l'agrégation de toutes les offres, qui
    # faisait remonter « Excel » à un technicien réseau.
    careers = db.query(models.Career).all() if profile else []
    skill_gaps = (
        prioritized_skill_gaps(skills, jobs, careers, taxonomy, limit=5)
        if profile else []
    )
    skills_to_improve = [gap["skill"] for gap in skill_gaps]

    # Ressource exacte pour le premier écart : le tableau de bord et l'agent
    # peuvent ainsi ouvrir la fiche de formation précise, pas la page générique.
    learning_focus = None
    if skills_to_improve:
        from app.services.learning import resource_key

        resource = (
            db.query(models.LearningResource)
            .filter(
                models.LearningResource.skill == skills_to_improve[0],
                models.LearningResource.hidden.is_(False),
            )
            .order_by(models.LearningResource.id)
            .first()
        )
        if resource is not None:
            learning_focus = {
                "skill": resource.skill,
                "title": resource.title,
                "provider": resource.provider,
                "resource_key": resource_key(resource.skill, resource.title),
                "href": f"/learning/{resource_key(resource.skill, resource.title)}",
            }

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
    if next_action.get("type") == "learn" and learning_focus:
        next_action["href"] = learning_focus["href"]
    elif next_action.get("type") in ("adapt_cv", "apply", "prepare_interview") and next_action.get("job_id"):
        next_action["href"] = f"/jobs/{next_action['job_id']}"

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

    # Messages recruteur non lus : détail important que l'agent signale
    unread_messages = (
        db.query(models.Message)
        .filter(
            models.Message.recipient_id == user.id,
            models.Message.read == False,  # noqa: E712
        )
        .count()
    )

    label, briefing = _ai_briefing(
        user, profile, jobs, matches, strong_matches, applications,
        interviews, best_overall, completeness, new_opportunities,
        learning_focus=learning_focus, skills_to_improve=skills_to_improve,
        unread_messages=unread_messages,
    )

    # Mode autonome : l'agent prépare les documents pour les meilleures
    # correspondances qui n'en ont pas encore. Le candidat valide l'envoi.
    autonomous_prepared = None
    if (
        profile
        and getattr(user, "agent_mode", "") == "autonome"
        and strong_matches
    ):
        autonomous_prepared = _autonomous_prepare(
            db, user, profile, strong_matches, applications, taxonomy
        )

    return {
        "name": user.full_name,
        "verified": user.verification_status == "verified",
        "new_opportunities": new_opportunities,
        "strong_matches": len(strong_matches),
        "skills_to_improve": skills_to_improve,
        "skill_gaps": skill_gaps,
        "ongoing_applications": len(ongoing),
        "interviews_to_prepare": len(interviews),
        "market_trends": market_trends,
        "market_week": market_week,
        "next_action": next_action,
        "ai_briefing": briefing,
        "ai_label": label,
        "profile_completeness": completeness,
        "top_matches": top_matches,
        "learning_focus": learning_focus,
        "autonomous_prepared": autonomous_prepared,
    }


def _autonomous_prepare(db, user, profile, strong_matches, applications, taxonomy):
    """Mode autonome : l'agent prépare un CV ciblé pour la meilleure
    correspondance qui n'en a pas encore, et marque la candidature
    « prête ». Le candidat garde la décision d'envoi (§47).

    Retourne un résumé de ce qui a été préparé, ou None si rien à faire.
    """
    from app.services import cv_builder
    from app.services.applications import STATUS_LABELS

    applied_ids = {a.job_id for a in applications}
    # Meilleures correspondances d'abord, sans CV ciblé existant.
    ranked = sorted(strong_matches, key=lambda t: t[1]["score"], reverse=True)
    for job, match in ranked[:3]:  # au plus 3 par visite, pas de avalanche
        existing_cv = (
            db.query(models.Document)
            .filter(
                models.Document.user_id == user.id,
                models.Document.job_id == job.id,
                models.Document.kind == "cv",
            )
            .first()
        )
        if existing_cv is not None:
            continue
        try:
            content = cv_builder.build_targeted_cv(
                profile, job, user, taxonomy, template="classique"
            )
        except Exception:
            return None
        document = models.Document(
            user_id=user.id,
            job_id=job.id,
            kind="cv",
            title=f"CV ciblé · {job.title} · {job.company}",
            content_markdown=content,
            source_profile=profile,
            template="classique",
        )
        db.add(document)
        # Application : créée si absente, passée en « cv_prepare ».
        app = next((a for a in applications if a.job_id == job.id), None)
        from datetime import datetime, timezone as _tz
        now_iso = datetime.now(_tz.utc).replace(tzinfo=None).isoformat(timespec="seconds")
        if app is None:
            app = models.Application(
                user_id=user.id,
                job_id=job.id,
                status="cv_prepare",
                timeline=[
                    {"at": now_iso, "event": STATUS_LABELS["identifiee"]},
                    {"at": now_iso, "event": "CV préparé automatiquement par l'agent (mode autonome)"},
                ],
            )
            db.add(app)
        elif app.status == "identifiee":
            app.status = "cv_prepare"
            timeline = list(app.timeline or [])
            timeline.append({
                "at": now_iso,
                "event": "CV préparé automatiquement par l'agent (mode autonome)",
            })
            app.timeline = timeline
        db.commit()
        return {
            "job_id": job.id,
            "job_title": job.title,
            "company": job.company,
            "score": match["score"],
            "message": (
                f"J'ai préparé votre CV ciblé pour « {job.title} » chez "
                f"{job.company} (correspondance {match['score']}/100). "
                "Relisez-le puis soumettez votre candidature quand vous êtes prêt."
            ),
        }
    return None


AGENT_MODES = agent_prefs.AGENT_MODES


@router.get("/agent/mode", response_model=schemas.AgentModeOut)
def get_agent_mode(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    mode = getattr(user, "agent_mode", None) or "preparation"
    if mode not in {item["id"] for item in AGENT_MODES}:
        mode = "preparation"
    return {"mode": mode, "modes": AGENT_MODES}


@router.put("/agent/mode", response_model=schemas.AgentModeOut)
def set_agent_mode(
    payload: schemas.AgentModeIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Enregistre le mode de travail de l'agent.

    Aucun mode n'envoie de candidature automatiquement : le candidat valide
    toujours les contenus et les envois. Le mode autonome exige une
    validation par document.
    """
    if user.role != "candidate":
        raise HTTPException(
            status_code=403,
            detail="Les réglages de l'agent carrière sont réservés aux candidats.",
        )
    if not agent_prefs.mode_allowed(user, payload.mode):
        raise HTTPException(
            status_code=422,
            detail="Le mode autonome exige une validation par document.",
        )
    user.agent_mode = payload.mode
    db.commit()
    return {"mode": payload.mode, "modes": AGENT_MODES}


def _agent_channels(user: models.User) -> list[str]:
    prefs = normalize_prefs(
        getattr(user, "notification_prefs", None) or {},
        getattr(user, "role", "candidate"),
    )
    channels = ["In-app"]
    if prefs["email_enabled"] and prefs["email"]:
        channels.append("E-mail")
    if prefs["telegram_enabled"] and prefs["telegram_username"]:
        channels.append("Telegram")
    if prefs["whatsapp_enabled"] and prefs["whatsapp_number"]:
        channels.append("WhatsApp")
    return channels


def _agent_preferences_payload(user: models.User) -> dict:
    prefs = agent_prefs.normalize_agent_prefs(
        getattr(user, "agent_prefs", None)
    )
    return {
        "mode": getattr(user, "agent_mode", None) or "preparation",
        "prefs": prefs,
        **agent_prefs.catalog(),
        "channels": _agent_channels(user),
        "channels_href": "/parametres-compte#notifications",
    }


@router.get("/agent/preferences", response_model=schemas.AgentPreferencesOut)
def get_agent_preferences(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Réglages complets de l'agent : mode + préférences persistées."""
    if user.role != "candidate":
        raise HTTPException(
            status_code=403,
            detail="Les réglages de l'agent carrière sont réservés aux candidats.",
        )
    return _agent_preferences_payload(user)


@router.put("/agent/preferences", response_model=schemas.AgentPreferencesOut)
def set_agent_preferences(
    payload: schemas.AgentPreferencesIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Enregistre les réglages de l'agent, sans jamais autoriser l'envoi auto."""
    if user.role != "candidate":
        raise HTTPException(
            status_code=403,
            detail="Les réglages de l'agent carrière sont réservés aux candidats.",
        )
    data = payload.model_dump(exclude_unset=True)
    mode = data.pop("mode", None)
    try:
        prefs = agent_prefs.update_agent_prefs(user.agent_prefs, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if mode is not None:
        if mode == "autonome" and prefs["validation"] == "toujours":
            raise HTTPException(
                status_code=422,
                detail="Le mode autonome exige une validation par document.",
            )
        user.agent_mode = mode
    user.agent_prefs = prefs
    db.commit()
    return _agent_preferences_payload(user)


_BRIEFING_LABELS = [
    "Ce que j'ai repéré pour toi aujourd'hui",
    "Ton assistant a travaillé pour toi",
    "Le point du jour",
    "Ce que je vois dans tes données",
    "Trois choses à savoir",
]

# Sourires de l'agent : utilisés avec parcimonie (l'agent n'est pas
# qu'une machine à recommandations, il détend l'atmosphère de temps en
# temps). Toujours courts, sobres, en français.
_AGENT_SMILES = [
    "Blague du jour : pourquoi les développeurs confondent Halloween et Noël ? Parce que OCT 31 égale DEC 25.",
    "Fun fact : la plupart des recruteurs lisent un CV en moins de temps qu'il faut pour chauffer un café. La tienne vaut mieux que ça.",
    "Petit conseil d'ami entre nous : relire sa lettre à voix haute évite d'écrire trois fois « je suis motivé ». Vécu de la part de bien des candidats.",
    "Mon alimentation préférée reste le data crunching : ça donne du grain à moudre.",
    "On dit que le meilleur CV est celui qu'on n'envoie pas à 23h59... quoique, un délai est un délai.",
]


def _ai_briefing(
    user, profile, jobs, matches, strong_matches, applications,
    interviews, best_overall, completeness, new_opportunities,
    learning_focus=None, skills_to_improve=None, unread_messages=0,
):
    """Briefing personnalisé, FACTUEL mais vivant : plusieurs
    formulations par sujet, tutoiement (persona Ori), humour léger de
    temps en temps. Retourne (libellé, texte). Chaque affirmation vient
    des données réelles (§47)."""
    if profile is None:
        return (
            random.choice(_BRIEFING_LABELS[:2]),
            random.choice([
                "Bienvenue ! Je n'ai encore rien à analyser : importe ton CV "
                "ou réponds au questionnaire, et je me charge du reste : "
                "compétences, métiers visés et correspondances.",
                "Salut ! Je n'ai encore aucune donnée sur toi. Importe ton "
                "CV, je m'occupe du reste.",
            ]),
        )

    first = (user.full_name or "").split(" ")[0]
    priority: list[str] = []   # toujours en tête : urgences et messages
    observations: list[str] = []

    # ---- Sujet : délai urgent (priorité absolue)
    now = _reference_now(jobs)
    urgent = []
    for job, match in strong_matches:
        if job.deadline and 0 <= (job.deadline - now).days <= 3:
            applied = any(a.job_id == job.id for a in applications)
            if not applied:
                urgent.append(job)
    if urgent:
        job = urgent[0]
        days = (job.deadline - now).days
        day_word = "aujourd'hui" if days == 0 else f"dans {days} jour" + ("s" if days > 1 else "")
        priority.append(random.choice([
            f"attention : la candidature pour « {job.title} » chez "
            f"{job.company} se termine {day_word}. Tout est prêt de mon "
            "côté, il ne reste qu'à envoyer.",
            f"« {job.title} » chez {job.company} ferme {day_word}. Ton "
            "dossier est prêt, on l'envoie ?",
        ]))

    # ---- Sujet : message non lu d'un recruteur (détail important)
    if unread_messages > 0:
        mot = "message" if unread_messages == 1 else "messages"
        priority.append(random.choice([
            f"tu as {unread_messages} {mot} non lu"
            + ("s" if unread_messages > 1 else "")
            + " dans ta messagerie : un recruteur attend une réponse.",
            f"petit détail qui compte : {unread_messages} "
            + mot
            + " de recruteur"
            + ("s" if unread_messages > 1 else "")
            + " attend"
            + ("ent" if unread_messages > 1 else "")
            + " ta réponse. Le silence fait rarement avancer un dossier.",
        ]))

    # ---- Sujet : meilleure correspondance
    if strong_matches and not urgent:
        job, match = max(strong_matches, key=lambda t: t[1]["score"])
        if len(strong_matches) == 1:
            observations.append(random.choice([
                f"j'ai comparé ton profil aux {len(jobs)} offres actives : "
                f"une te correspond fortement, « {job.title} » chez "
                f"{job.company} ({match['score']}/100).",
                f"une piste se détache : « {job.title} » chez {job.company}, "
                f"correspondance {match['score']}/100, la meilleure du moment.",
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
    elif best_overall and not urgent:
        job, match = best_overall
        observations.append(random.choice([
            f"la piste la plus proche est « {job.title} » chez {job.company} "
            f"({match['score']}/100), encore perfectible.",
            f"rien de parfait pour l'instant, mais « {job.title} » chez "
            f"{job.company} reste ta meilleure option ({match['score']}/100).",
        ]))

    # ---- Sujet : entretien (prioritaire, on le met souvent en tête)
    if interviews:
        n = len(interviews)
        mot = "entretien" if n == 1 else "entretiens"
        observations.append(random.choice([
            f"tu as {n} {mot} à préparer, je peux générer les questions "
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
                f"{n} candidature" + ("s" if n > 1 else "") + " en cours, "
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

    # ---- Sujet : formation à suivre (si un écart a une ressource réelle)
    if learning_focus and skills_to_improve:
        skill = learning_focus.get("skill") or skills_to_improve[0]
        title = learning_focus.get("title") or ""
        provider = learning_focus.get("provider") or ""
        if title:
            source = f" ({title}, {provider})" if provider else f" ({title})"
            observations.append(random.choice([
                f"pour être compétitif au vu des dernières tendances, suit "
                f"une formation en « {skill} »{source}.",
                f"le marché demande « {skill} » : j'ai trouvé une formation "
                f"réelle{source}, à toi de voir.",
            ]))
        else:
            observations.append(random.choice([
                f"pour être compétitif, renforce « {skill} », demandée par "
                "les offres du moment.",
            ]))

    # ---- Sujet : profil vérifié (les recruteurs filtrent dessus)
    if getattr(user, "verification_status", "none") != "verified" \
            and profile.get("skills") and random.random() < 0.5:
        observations.append(random.choice([
            "détail qui pèse : un profil vérifié passe mieux les filtres "
            "des recruteurs. Dépose ta pièce depuis les Paramètres.",
            "fais vérifier ton profil : c'est cinq minutes et ça rassure "
            "les recruteurs qui ne te connaissent pas encore.",
        ]))

    # ---- Sujet : CV partagé aux recruteurs (visibilité)
    if profile.get("skills"):
        if getattr(user, "cv_visible_to_recruiters", False):
            observations.append(random.choice([
                "ton CV généraliste est visible des recruteurs : reste "
                "attentif à ta messagerie, certains contactent directement.",
                "bonne nouvelle, ton CV est partagé : les recruteurs "
                "peuvent te découvrir même sans candidature de ta part.",
            ]))
        elif random.random() < 0.5:
            observations.append(random.choice([
                "ton CV n'est pas encore partagé aux recruteurs : active "
                "le partage depuis tes documents pour être contacté.",
                "si tu veux qu'on vienne à toi, partage ton CV généraliste "
                "avec les recruteurs : c'est toi qui choisis lequel.",
            ]))

    # ---- Sujet : infos à ajouter au profil (conseil de visibilité)
    profile_tips: list[str] = []
    if completeness and completeness["missing"]:
        for item in completeness["missing"][:3]:
            profile_tips.append(item.lower())
    if not profile.get("photo_path") and profile.get("skills"):
        profile_tips.append("une photo professionnelle")
    if not profile.get("languages"):
        profile_tips.append("tes langues et niveaux")

    # ---- Compose : urgences en tête, puis sujets tirés au sort,
    # conseil final, et un sourire de temps en temps (l'agent n'est pas
    # qu'une machine à recommandations).
    random.shuffle(observations)
    room = 2 if priority else 3
    lead = priority + observations[:room]

    tip = ""
    if profile_tips:
        tip = random.choice([
            "Ça renforcerait ta visibilité : ajoute " + profile_tips[0] + ".",
            "Info à ajouter à ton profil pour te rendre plus visible : "
            + profile_tips[0] + ".",
        ])

    smile = ""
    if lead and random.random() < 0.25:
        smile = " " + random.choice(_AGENT_SMILES)

    greeting = random.choice([
        f"{first}, ",
        f"Salut {first} ! ",
        f"Tiens {first}, ",
        "",
    ])
    text = greeting + " ".join(lead)
    if tip:
        text = (text + " " + tip).strip()
    if smile:
        text = (text + smile).strip()
    return random.choice(_BRIEFING_LABELS), _polish_sentences(text)


def _polish_sentences(text: str) -> str:
    """Typographie : chaque phrase démarre par une majuscule (les
    observations sont assemblées dynamiquement)."""
    import re as _re

    def upper_first(match):
        return match.group(1) + match.group(2).upper()

    return _re.sub(r"([.!?] )([a-zà-ÿ])", upper_first, text[:1].upper() + text[1:])


def _next_action(user, profile, jobs, matches, applications, interviews) -> dict:
    """Prochaine action prioritaire, ancrée sur les données réelles.

    Le mode choisi change réellement l'ordre des priorités : conseil,
    préparation de document, ou examen des offres.
    """
    mode = getattr(user, "agent_mode", "preparation") or "preparation"
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

    def learning_action() -> dict | None:
        if not profile:
            return None
        gaps: Counter[str] = Counter()
        for job in jobs:
            for name in matches.get(job.id, {}).get("missing", []):
                gaps[name] += 1
        if not gaps:
            return None
        top_skill = gaps.most_common(1)[0][0]
        return {
            "label": f"Développer la compétence « {top_skill} » demandée par le marché",
            "type": "learn",
            "skill": top_skill,
        }

    # Accompagnement : le conseil et la compétence passent avant l'action.
    if mode == "accompagnement":
        advice = learning_action()
        if advice:
            return advice

    # Veille : l'offre à examiner passe avant la préparation du CV.
    if mode == "veille" and best and best[0].id not in applied_ids:
        return {
            "label": f"Candidater à « {best[0].title} » chez {best[0].company}",
            "type": "apply",
            "job_id": best[0].id,
        }

    if best and best[1]["score"] >= LEVEL_STRONG and best[0].id not in applied_ids:
        return {
            "label": f"Adapter votre CV pour « {best[0].title} » chez {best[0].company}",
            "type": "adapt_cv",
            "job_id": best[0].id,
        }

    if mode != "accompagnement":
        advice = learning_action()
        if advice:
            return advice

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


def _naive_utc(value):
    """Horodatage comparable : les événements calculés restent naïfs."""
    if getattr(value, "tzinfo", None) is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _notification_events(db: Session, user: models.User) -> list[dict]:
    """Événements de la rubrique Notifications, avec état lu/non lu.

    Le contenu reste calculé à la demande : aucune copie en base, donc
    aucun risque de doublon. Seul l'horodatage de consultation est stocké
    sur le compte.
    """
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    jobs = db.query(models.Job).all()
    applications = (
        db.query(models.Application)
        .filter(models.Application.user_id == user.id)
        .all()
    )
    prefs = agent_prefs.normalize_agent_prefs(getattr(user, "agent_prefs", None))
    events = build_inbox(
        profile, jobs, applications, load_taxonomy(),
        since=getattr(user, "created_at", None),
        agent_actions=prefs["actions"],
    )

    # Signalements du candidat TRAITÉS par l'administration : la réponse
    # vit dans les notifications, pas sur la fiche de l'offre.
    from app.schemas import REPORT_REASONS

    reports = (
        db.query(models.JobReport)
        .filter(
            models.JobReport.user_id == user.id,
            models.JobReport.status.in_(["traite", "rejete"]),
        )
        .order_by(models.JobReport.updated_at.desc())
        .limit(10)
        .all()
    )
    for report in reports:
        job = db.get(models.Job, report.job_id)
        title = job.title if job else f"offre #{report.job_id}"
        motif = REPORT_REASONS.get(report.reason, report.reason)
        if report.status == "rejete":
            message = (
                f"Signalement rejeté pour « {title} » ({motif})"
                + (
                    f" · Réponse de l'administration : {report.admin_note}"
                    if report.admin_note else ""
                )
            )
        else:
            message = (
                f"Signalement traité pour « {title} » ({motif})"
                + (
                    f" · Décision : {report.admin_note}"
                    if report.admin_note else ""
                )
            )
        events.append({
            "at": report.updated_at,
            "kind": "report",
            "message": message,
            "job_id": report.job_id,
        })

    # Décisions de recours : visibles dans les notifications (le compte
    # reste intact, la décision est tracée).
    appeals = (
        db.query(models.BanAppeal)
        .filter(
            models.BanAppeal.user_id == user.id,
            models.BanAppeal.status.in_(["accepted", "rejected"]),
            models.BanAppeal.reviewed_at.isnot(None),
        )
        .order_by(models.BanAppeal.reviewed_at.desc())
        .limit(5)
        .all()
    )
    for appeal in appeals:
        if appeal.status == "accepted":
            message = (
                "Votre recours a été accepté : la suspension de votre compte "
                "est levée, vos données sont intactes."
            )
        else:
            message = "Votre recours a été refusé."
        if appeal.admin_note:
            message += f" Message de l'administration : {appeal.admin_note}"
        events.append({
            "at": appeal.reviewed_at,
            "kind": "appeal",
            "message": message,
            "job_id": None,
        })

    # Invitations à un entretien encore en attente de réponse.
    invites = (
        db.query(models.InterviewInvite)
        .filter(
            models.InterviewInvite.candidate_id == user.id,
            models.InterviewInvite.status == "pending",
            models.InterviewInvite.recruiter_responded_at.is_(None),
        )
        .order_by(models.InterviewInvite.created_at.desc())
        .limit(10)
        .all()
    )
    for invite in invites:
        job = db.get(models.Job, invite.job_id)
        title = job.title if job else f"offre #{invite.job_id}"
        company = f" chez {job.company}" if job and job.company else ""
        events.append({
            "at": invite.created_at,
            "kind": "interview",
            "message": (
                f"Invitation à un entretien pour « {title} »{company} : "
                f"{interview_service.slot_label(invite.slot_at)}. "
                "Répondez depuis la rubrique Entretiens."
            ),
            "job_id": invite.job_id,
        })

    # Décisions du recruteur sur une demande d'autre créneau : le candidat
    # les retrouve dans ses notifications, sans passer par la messagerie.
    decisions = (
        db.query(models.InterviewInvite)
        .filter(
            models.InterviewInvite.candidate_id == user.id,
            models.InterviewInvite.recruiter_responded_at.isnot(None),
        )
        .order_by(models.InterviewInvite.recruiter_responded_at.desc())
        .limit(10)
        .all()
    )
    for invite in decisions:
        job = db.get(models.Job, invite.job_id)
        title = job.title if job else f"offre #{invite.job_id}"
        company = f" chez {job.company}" if job and job.company else ""
        slot = interview_service.slot_label(invite.slot_at)
        if invite.status == "accepted":
            message = (
                f"Le recruteur a accepté votre créneau pour « {title} »"
                f"{company} : {slot}. L'entretien est confirmé."
            )
        elif invite.status == "refused":
            message = (
                f"Le recruteur a mis fin au processus d'entretien pour "
                f"« {title} »{company}."
            )
        else:
            message = (
                f"Le recruteur vous propose un nouveau créneau pour "
                f"« {title} »{company} : {slot}. Répondez depuis la rubrique "
                "Entretiens."
            )
        events.append({
            "at": invite.recruiter_responded_at,
            "kind": "interview",
            "message": message,
            "job_id": invite.job_id,
        })

    # Décision sur la vérification du profil : succès ou refus motivé.
    verification_decided_at = getattr(user, "verification_decided_at", None)
    verification_status = getattr(user, "verification_status", "none")
    if verification_decided_at and verification_status in ("verified", "rejected"):
        note = (getattr(user, "verification_note", "") or "").strip()
        if verification_status == "verified":
            message = "Votre profil a été vérifié."
            if note:
                message += f" Note de l'administration : {note}"
        else:
            message = "Votre demande de vérification a été refusée."
            if note:
                message += f" Motif : {note}"
        events.append({
            "at": verification_decided_at,
            "kind": "verification",
            "message": message,
            "job_id": None,
        })

    # Les sources persistées (signalements, recours, invitations,
    # vérification) sont elles aussi filtrées : un compte neuf ne doit pas
    # hériter d'événements antérieurs à sa création.
    created_at = getattr(user, "created_at", None)
    if created_at is not None:
        created_naive = _naive_utc(created_at)
        events = [
            event for event in events
            if _naive_utc(event["at"]) >= created_naive
        ]

    seen_at = getattr(user, "notifications_seen_at", None)
    events.sort(key=lambda e: _naive_utc(e["at"]), reverse=True)
    for i, event in enumerate(events[:20], start=1):
        event["id"] = i
        event["unread"] = bool(
            seen_at is None or _naive_utc(event["at"]) > seen_at
        )
    return events[:20]


@router.get("/notifications", response_model=list[schemas.InboxEvent])
def notifications(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Rubrique Notifications, distincte de la messagerie interne."""
    return _notification_events(db, user)


@router.get(
    "/notifications/unread-count",
    response_model=schemas.NotificationSummary,
)
def notifications_unread_count(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    events = _notification_events(db, user)
    return {
        "count": sum(1 for event in events if event.get("unread")),
        "seen_at": getattr(user, "notifications_seen_at", None),
    }


@router.post(
    "/notifications/seen",
    response_model=schemas.NotificationSummary,
)
def mark_notifications_seen(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Marque comme lues les notifications affichées à cet instant."""
    user.notifications_seen_at = models.utcnow()
    db.commit()
    return {"count": 0, "seen_at": user.notifications_seen_at}


# Ancienne URL conservée pour les clients déjà ouverts : la rubrique
# s'appelle désormais Notifications, pas Inbox.
@router.get("/inbox", response_model=list[schemas.InboxEvent], include_in_schema=False)
def inbox_alias(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    return _notification_events(db, user)
