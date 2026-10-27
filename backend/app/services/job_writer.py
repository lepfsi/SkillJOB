"""Rédaction assistée d'une offre d'emploi.

Le recruteur décrit son besoin en quelques phrases. Le service propose un
intitulé, une description et un profil recherché prêts à relire. Deux
modes, dans cet ordre :

1. LLM configuré par l'administrateur : reformulation sobre, strictement
   limitée aux faits fournis ;
2. repli local : structure la description et le profil à partir des
   éléments réellement reconnus par ``job_parser``.

Aucune proposition n'est enregistrée : le formulaire reste un brouillon
tant que le recruteur n'a pas appliqué les suggestions puis publié.
"""
import json
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services import job_parser, llm_client

_DASHES = {"\u2013": "-", "\u2014": "-", "\u2015": "-"}


def _clean(value: Any, limit: int) -> str:
    text = str(value or "").replace("\r\n", "\n").strip()
    for dash, replacement in _DASHES.items():
        text = text.replace(dash, replacement)
    return text[:limit].strip()


def _skill_names(base: dict, importance: str) -> list[str]:
    return [
        skill["name"]
        for skill in base.get("required_skills", [])
        if skill.get("importance") == importance
    ]


def _rules_draft(base: dict, text: str) -> dict[str, Any]:
    """Repli local : phrases construites uniquement sur les faits reconnus."""
    title = _clean(base.get("title"), 120)
    location = _clean(base.get("location"), 120)
    sector = _clean(base.get("sector"), 120)
    contract = _clean(base.get("contract_type"), 40) or "CDI"
    company = _clean(base.get("company"), 120)

    intro = ""
    if title:
        intro = f"Nous recherchons un(e) {title}"
        if company:
            intro += f" pour {company}"
        if location:
            intro += f" à {location}"
        intro += f". Contrat : {contract}."
        if sector:
            intro += f" Secteur : {sector}."
    description = text.strip()
    if intro:
        description = f"{intro}\n\n{description}" if description else intro
    elif not description:
        description = "Description à compléter par le recruteur."

    core = _skill_names(base, "core")
    preferred = _skill_names(base, "preferred")
    requirement_lines = ["Profil recherché :"]
    if core:
        requirement_lines.append(f"- Maîtrise de : {', '.join(core)}.")
    if preferred:
        requirement_lines.append(
            f"- Connaissance appréciée de : {', '.join(preferred)}."
        )
    if not core and not preferred:
        requirement_lines.append(
            "- Aucune compétence n'a été reconnue dans la description : "
            "complétez ce champ avant publication."
        )
    requirements = "\n".join(requirement_lines)

    return {
        "title": title,
        "description": _clean(description, 4000),
        "requirements": _clean(requirements, 2000),
        "location": location,
        "sector": sector,
        "contract_type": contract,
        "required_skills": base.get("required_skills", []),
    }


def _extract_json(raw: str) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(raw[start:end + 1])
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _grounded(value: str, text: str) -> bool:
    """Vrai si le titre proposé partage un mot significatif avec la source."""
    words = {
        word.lower()
        for word in re.findall(r"[A-Za-zÀ-ÿ]{4,}", value or "")
    }
    if not words:
        return False
    source = (text or "").lower()
    return any(word in source for word in words)


def _llm_draft(
    db: Session, base: dict, text: str
) -> Optional[dict[str, Any]]:
    """Proposition LLM, ou None si désactivé / invalide / hors sujet."""
    facts = {
        "intitulé détecté": base.get("title") or "",
        "entreprise détectée": base.get("company") or "",
        "lieu détecté": base.get("location") or "",
        "secteur détecté": base.get("sector") or "",
        "contrat détecté": base.get("contract_type") or "",
        "compétences reconnues": base.get("required_skills") or [],
    }
    messages = [
        {
            "role": "system",
            "content": (
                "Tu aides un recruteur camerounais à rédiger une offre "
                "d'emploi en français. Tu ne dois inventer AUCUNE information : "
                "pas de diplôme, d'expérience, de salaire, d'avantage, de "
                "taille d'équipe ni d'employeur absent du texte fourni. Tu "
                "peux seulement reformuler et structurer les faits présents. "
                "Si une information manque, ne la mentionne pas. Réponds "
                "uniquement par un objet JSON avec les clés title, "
                "description et requirements. N'utilise pas de tiret long."
            ),
        },
        {
            "role": "user",
            "content": (
                "Description libre du recruteur :\n"
                f"{text}\n\n"
                "Éléments déjà détectés (à ne pas contredire) :\n"
                f"{json.dumps(facts, ensure_ascii=False)}\n\n"
                "Rédige une description de 3 à 6 phrases et un profil "
                "recherché sous forme de puces. Reste factuel."
            ),
        },
    ]
    raw = llm_client.chat_completion(db, messages, max_tokens=900, timeout=20)
    data = _extract_json(raw or "")
    if not data:
        return None
    title = _clean(data.get("title"), 120)
    description = _clean(data.get("description"), 4000)
    requirements = _clean(data.get("requirements"), 2000)
    if not description and not requirements:
        return None
    # Un titre entièrement inventé est écarté : on garde celui du parseur.
    if title and base.get("title") and not _grounded(title, text):
        title = base.get("title")
    return {
        "title": title or _clean(base.get("title"), 120),
        "description": description,
        "requirements": requirements,
        "location": _clean(base.get("location"), 120),
        "sector": _clean(base.get("sector"), 120),
        "contract_type": _clean(base.get("contract_type"), 40) or "CDI",
        "required_skills": base.get("required_skills", []),
    }


def write_job_draft(db: Session, text: str) -> dict[str, Any]:
    """Retourne une proposition complète, jamais enregistrée."""
    text = (text or "").strip()
    if len(text) < 10:
        return {"error": "Décrivez l'offre en une phrase au moins (10 caractères)."}

    base = job_parser.parse_job_description(text)
    if base.get("error"):
        return base

    rules = _rules_draft(base, text)
    proposal = _llm_draft(db, base, text)
    mode = "llm"
    if proposal is None:
        proposal = rules
        mode = "rules"

    # Les champs vides du LLM sont complétés par le repli local, jamais
    # par une valeur inventée.
    for key in ("title", "description", "requirements", "location",
                "sector", "contract_type"):
        if not proposal.get(key):
            proposal[key] = rules.get(key, "")

    return {
        **proposal,
        "mode": mode,
        "warning": (
            "Proposition à relire : rien n'est enregistré tant que vous "
            "n'avez pas appliqué les suggestions puis publié l'offre. "
            "Chaque champ reste modifiable."
        ),
    }
