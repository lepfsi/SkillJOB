"""Routage des candidatures reçues sur la boîte interne.

Une offre porte une référence stable (OS-0042) que le candidat place dans
l'objet de son e-mail. À défaut, les mots-clés déclarés sur l'offre puis
le titre et l'entreprise servent à retrouver la destination. Le routage
reste volontairement prudent : en cas d'ambiguïté, le message est marqué
« non routé » plutôt que transmis à la mauvaise entreprise.
"""
import re
import unicodedata
from typing import Optional

from sqlalchemy.orm import Session

from app.services import settings_store

REFERENCE_RE = re.compile(r"\bOS[-\s]?0*(\d{1,7})\b", re.IGNORECASE)


def reference_for(job) -> str:
    """Référence publique stable, lisible et unique par offre."""
    if getattr(job, "id", None) is None:
        return ""
    return f"OS-{int(job.id):04d}"


def normalize(value: str) -> str:
    """Minuscules sans accents, pour comparer des libellés libres."""
    decomposed = unicodedata.normalize("NFKD", value or "")
    return "".join(
        char for char in decomposed if not unicodedata.combining(char)
    ).lower()


def inbound_address(db: Session) -> str:
    """Adresse interne affichée sur le visuel public."""
    conf = settings_store.get_raw_group(db, "inbound")
    return str(conf.get("address") or "").strip()


def public_poster_path(job) -> str:
    if getattr(job, "id", None) is None:
        return ""
    return f"/api/public/jobs/{job.id}/poster.svg"


def match_job(db: Session, subject: str, body: str) -> tuple[Optional[object], str]:
    """Retourne (offre, mode de routage) sans jamais deviner au hasard.

    Priorité :
    1. référence OS-XXXX présente dans l'objet ou le corps ;
    2. mots-clés de routage déclarés sur l'offre ;
    3. titre complet puis nom de l'entreprise dans l'objet.

    Un score exige un gagnant unique. Les offres sans identifiant ou déjà
    expirées ne sont pas exclues : le publieur reste seul juge.
    """
    from app import models

    haystack = normalize(f"{subject or ''}\n{body or ''}")
    match = REFERENCE_RE.search(f"{subject or ''}\n{body or ''}")
    if match:
        job = db.get(models.Job, int(match.group(1)))
        if job is not None:
            return job, "reference"

    jobs = db.query(models.Job).all()
    best = []
    best_score = 0
    for job in jobs:
        score = 0
        for keyword in job.apply_keywords or []:
            token = normalize(str(keyword)).strip()
            if len(token) >= 3 and token in haystack:
                score += 4
        title = normalize(job.title)
        if len(title) >= 4 and title in haystack:
            score += 3
        company = normalize(job.company)
        if len(company) >= 4 and company in haystack:
            score += 2
        if score > best_score:
            best_score = score
            best = [job]
        elif score == best_score and score > 0:
            best.append(job)

    if best_score >= 2 and len(best) == 1:
        mode = "keywords" if best_score >= 4 else "titre"
        return best[0], mode
    return None, ""
