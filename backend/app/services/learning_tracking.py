"""Suivi des formations et preuves (§19, §47).

Une formation suivie est un fait réel : le candidat a ouvert la formation
(page Learning), puis déclare son avancement. La preuve (certificat,
attestation, badge, portfolio) est **déclarée** avec sa référence : elle
reste vérifiable au lien fourni, et ne devient une preuve de profil
qu'après validation explicite du candidat.

Aucune preuve n'est inventée ni téléversée : on enregistre ce que le
candidat déclare, avec sa source, pour qu'un recruteur puisse vérifier.
"""
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

# --------------------------------------------------------------- vocabulaire

ENROLLMENT_STATUSES = ("commencee", "en_cours", "terminee")
STATUS_LABELS = {
    "commencee": "Commençée",
    "en_cours": "En cours",
    "terminee": "Terminée",
}
# Étapes franchies dans l'ordre (stepper de la page).
STATUS_STEPS = ("commencee", "en_cours", "terminee")

PROOF_KINDS = ("aucune", "certificat", "attestation", "badge", "portfolio", "autre")
PROOF_LABELS = {
    "aucune": "Aucune pièce",
    "certificat": "Certificat de fin de formation",
    "attestation": "Attestation de participation",
    "badge": "Badge numérique (Open Badge)",
    "portfolio": "Portfolio / réalisation vérifiable",
    "autre": "Autre pièce justificative",
}
# Pièces qui exigent une référence vérifiable (lien ou numéro).
PROOF_NEEDS_REFERENCE = ("certificat", "attestation", "badge")

LINK_KINDS = ("exact", "catalogue", "search", "local", "interne")
LINK_KIND_LABELS = {
    "exact": "Formation exacte",
    "catalogue": "Catalogue du fournisseur",
    "search": "Résultats de recherche",
    "local": "Centre ou organisme (sur place)",
    "interne": "Activité guidée (dans la plateforme)",
}

# Fournisseurs qui forment sur place (aucune page de formation en ligne).
_LOCAL_HINTS = (
    "centre de formation", "centres de formation", "centres professionnels",
    "centres agrees", "centres agréés", "minfop", "minjec", "mintransport",
    "ecole", "école", "institut de formation", "cabinet", "auto-école",
    "auto-ecole", "croix-rouge", "fne", "chambre", "ensam",
    "partenaire local", "local", "hôpital", "antenne",
)
# Pages de catalogue (racine d'un fournisseur ou liste de cours).
_CATALOGUE_PATHS = {
    "openclassrooms.com/fr/courses",
    "elearning.fao.org/",
    "skillshop.withgoogle.com/",
    "learndigital.withgoogle.com/",
    "alison.com/",
    "openwho.org/",
    "www.minfop.gov.cm/",
    "minfop.gov.cm/",
    "www.minjec.cm/",
    "minjec.cm/",
    "www.fun-mooc.fr/",
}


def infer_link_kind(url: Optional[str], provider: str = "") -> str:
    """Nature du lien, déduite de l'URL (filet de sécurité : la donnée
    annotée dans le référentiel fait foi)."""
    local = any(hint in (provider or "").lower() for hint in _LOCAL_HINTS)
    if not url:
        # Activité proposée dans la plateforme, ou organisme à contacter.
        return "local" if local else "interne"
    parsed = urlparse(url)
    netloc = parsed.netloc.lower().replace("www.", "")
    path = parsed.path or "/"
    if netloc.endswith("youtube.com") and path.startswith("/results"):
        return "search"
    if _looks_like_search(path):
        return "search"
    if f"{netloc}{path}" in _CATALOGUE_PATHS or f"www.{netloc}{path}" in _CATALOGUE_PATHS:
        return "catalogue"
    if local:
        return "local"
    if path in ("", "/"):
        return "catalogue"
    if netloc == "edx.org" and len([p for p in path.split("/") if p]) == 2 \
            and path.startswith("/learn/"):
        return "catalogue"
    return "exact"


def _looks_like_search(path: str) -> bool:
    lowered = path.lower()
    return any(token in lowered for token in ("/search", "recherche", "/results", "query="))


def is_verifiable(enrollment: Any) -> bool:
    """Vraie preuve : formation terminée ET pièce fournie."""
    if enrollment.status != "terminee":
        return False
    if enrollment.proof_kind == "aucune":
        return False
    reference = (enrollment.proof_reference or "").strip()
    note = (enrollment.proof_note or "").strip()
    if not reference and not note:
        return False
    if enrollment.proof_kind in PROOF_NEEDS_REFERENCE and not reference:
        return False
    return True


def is_reference_url(reference: str) -> bool:
    return reference.strip().lower().startswith(("http://", "https://"))


def _iso_date(value: Optional[datetime]) -> str:
    return value.date().isoformat() if value else ""


def evidence_for(enrollment: Any) -> dict[str, str]:
    """Preuve de progression rattachée à la compétence travaillée."""
    label = f"Formation « {enrollment.title} »"
    if enrollment.provider:
        label += f" · {enrollment.provider}"
    if enrollment.proof_kind in ("certificat", "badge", "attestation"):
        kind = "certification"
        label += f" · {PROOF_LABELS[enrollment.proof_kind].lower()}"
    elif enrollment.proof_kind == "portfolio":
        kind = "project"
        label += " · réalisation vérifiable"
    else:
        kind = "education"
        label += " · suivi déclaré (sans pièce)"
    return {"kind": kind, "label": label}


def to_dict(enrollment: Any) -> dict[str, Any]:
    """Représentation API d'une formation suivie (contrat §19)."""
    return {
        "id": enrollment.id,
        "skill": enrollment.skill,
        "title": enrollment.title,
        "provider": enrollment.provider or "",
        "url": enrollment.url,
        "kind": enrollment.kind,
        "link_kind": enrollment.link_kind or "exact",
        "link_kind_label": LINK_KIND_LABELS.get(
            enrollment.link_kind or "exact", "Lien"
        ),
        "status": enrollment.status,
        "status_label": STATUS_LABELS.get(enrollment.status, enrollment.status),
        "started_at": enrollment.started_at,
        "completed_at": enrollment.completed_at,
        "proof_kind": enrollment.proof_kind or "aucune",
        "proof_label": PROOF_LABELS.get(enrollment.proof_kind, "Pièce"),
        "proof_reference": enrollment.proof_reference or "",
        "proof_note": enrollment.proof_note or "",
        "verifiable": is_verifiable(enrollment),
        "added_to_profile": bool(enrollment.added_to_profile),
    }


# ------------------------------------------------------------------- profil

def _experience_item(enrollment: Any) -> dict[str, Any]:
    pieces = [
        f"Formation suivie"
        + (f" auprès de {enrollment.provider}" if enrollment.provider else "")
        + f", terminée le {_iso_date(enrollment.completed_at)}."
    ]
    if enrollment.proof_kind != "aucune":
        proof = PROOF_LABELS.get(enrollment.proof_kind, "Pièce")
        reference = (enrollment.proof_reference or "").strip()
        pieces.append(f"{proof} fourni" + (f" : {reference}" if reference else "") + ".")
    if enrollment.proof_note.strip():
        pieces.append(enrollment.proof_note.strip())
    return {
        "title": f"Formation « {enrollment.title} »",
        "organization": enrollment.provider or "Formation en ligne",
        "type": "apprenticeship",
        "description": " ".join(pieces),
        "start_date": _iso_date(enrollment.started_at),
        "end_date": _iso_date(enrollment.completed_at),
        "skills": [enrollment.skill],
    }


def _certification_item(enrollment: Any) -> Optional[dict[str, Any]]:
    if enrollment.proof_kind not in ("certificat", "badge", "attestation"):
        return None
    reference = (enrollment.proof_reference or "").strip()
    item: dict[str, Any] = {
        "name": f"{enrollment.title}",
        "issuer": enrollment.provider or "",
        "year": (enrollment.completed_at or enrollment.started_at).year,
        "skills": [enrollment.skill],
    }
    if is_reference_url(reference):
        item["url"] = reference
    return item


def profile_payload(enrollment: Any, profile: dict[str, Any]) -> dict[str, Any]:
    """Données à enregistrer dans le profil maître (validation humaine).

    Ajoute l'expérience « Formation suivie », la certification quand une
    pièce le justifie, et marque la compétence comme appuyée par des
    preuves. Les doublons (même formation) ne sont pas réinsérés.
    """
    experiences = [dict(e) for e in profile.get("experiences", [])]
    experience = _experience_item(enrollment)
    if not any(e.get("title") == experience["title"] for e in experiences):
        experiences.append(experience)

    certifications = [dict(c) for c in profile.get("certifications", [])]
    certification = _certification_item(enrollment)
    if certification and not any(
        c.get("name") == certification["name"] for c in certifications
    ):
        certifications.append(certification)

    skills = []
    for s in profile.get("skills", []):
        item = dict(s)
        if item.get("skill") == enrollment.skill:
            item["source"] = "evidence"
            item["evidence_count"] = int(item.get("evidence_count", 0) or 0) + 1
        skills.append(item)

    return {
        "experiences": experiences,
        "certifications": certifications,
        "skills": skills,
    }
