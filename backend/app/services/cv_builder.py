"""CV Intelligence : génération de documents ciblés SANS invention (§15-18).

Toutes les données utilisées proviennent exclusivement du profil validé par
l'utilisateur : le générateur réordonne et valorise, il n'invente jamais de
diplôme, d'expérience ou de compétence.

Trois modèles au choix :
- ``classique`` : hiérarchie lisible, compétences ciblées d'abord ;
- ``ats``       : compatible ATS (une colonne, intitulés standards,
                  aucune mise en forme exotique) ;
- ``moderne``   : en-tête resserré, résumé élargi, ton direct.
"""
from typing import Any, Literal, Optional

from app.services.matching import compute_match
from app.services.skills_taxonomy import SkillsTaxonomy

TemplateId = Literal["classique", "ats", "moderne"]

TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "classique",
        "name": "Classique",
        "description": (
            "Mise en page sobre aux normes internationales : compétences "
            "ciblées par l'offre en tête, expériences datées, sections nettes."
        ),
        "ats_friendly": True,
    },
    {
        "id": "ats",
        "name": "ATS (robots de recrutement)",
        "description": (
            "Optimisé pour les logiciels de tri automatique : une seule "
            "colonne, intitulés de sections standards (Experience, Education… "
            "compatibles), aucun élément graphique, mots-clés en clair."
        ),
        "ats_friendly": True,
    },
    {
        "id": "moderne",
        "name": "Moderne",
        "description": (
            "En-tête percutant, résumé élargi en accroche, lecture rapide "
            "pour les recrutements directs et les réseaux."
        ),
        "ats_friendly": False,
    },
]

# Genre : plus de « (se) » dans les documents ; la formulation
# s'accorde avec le genre enregistré à l'inscription (neutre sinon).
def _agree(user: Any, masculine: str, feminine: str, neutral: str) -> str:
    gender = getattr(user, "gender", None)
    if gender == "femme":
        return feminine
    if gender == "homme":
        return masculine
    return neutral


def list_templates() -> list[dict[str, Any]]:
    return TEMPLATES

TYPE_LABELS = {
    "formal": "Expérience professionnelle",
    "informal": "Expérience informelle",
    "freelance": "Mission freelance",
    "volunteer": "Bénévolat",
    "apprenticeship": "Stage / Apprentissage",
    "project": "Projet",
}
PROFICIENCY_LABELS = {
    "avance": "avancé",
    "intermediaire": "intermédiaire",
    "debutant": "débutant",
}


def _profile_skills(match: dict, skills: list[dict]) -> tuple[list, list]:
    """Compétences ordonnées : celles ciblées par l'offre d'abord."""
    wanted = set(match["covered"]) | set(match["partial"])
    targeted = [s for s in skills if s["skill"] in wanted]
    others = [s for s in skills if s["skill"] not in wanted]
    return targeted, others


def _experience_relevance(experience: dict, wanted: set[str]) -> int:
    return len(set(experience.get("skills") or []) & wanted)


def build_targeted_cv(
    profile: dict[str, Any],
    job: Any,
    user: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
    template: TemplateId = "classique",
) -> str:
    """Génère un CV markdown ciblé pour l'offre (réorganisation sans invention).

    Le modèle ``ats`` produit une structure mono-colonne à intitulés
    standards, lisible par les robots de tri de candidatures.
    """
    match = compute_match(profile.get("skills", []), job.required_skills, taxonomy)
    wanted = set(match["covered"]) | set(match["partial"]) | {
        r.get("name") for r in job.required_skills
    }
    ats = template == "ats"

    lines: list[str] = []
    lines.append(f"# {user.full_name}")
    headline = profile.get("title") or f"Candidature : {job.title}"
    location = profile.get("location") or "Cameroun"
    lines.append(f"**{headline}** · {location}")
    if getattr(user, "email", None):
        lines.append(f"Contact : {user.email}")
    if profile.get("availability"):
        lines.append(f"Disponibilité : {profile['availability']}")
    if getattr(user, "verification_status", None) == "verified":
        lines.append("Profil vérifié OrientSkill AI")
    lines.append("")

    # Résumé : uniquement des éléments factuels du profil validé
    summary = profile.get("summary")
    if not summary and match["covered"]:
        summary = (
            f"Profil orienté « {job.title} » ; compétences pertinentes déjà "
            f"acquises : {', '.join(match['covered'][:5])}."
        )
    if summary:
        section = "Professional Summary" if ats else "Résumé"
        if ats:
            # ATS : paragraphe continu, pas de mise en forme
            lines += [section, summary.replace("\n", " "), ""]
        else:
            lines += [f"## {section}", summary, ""]

    # Compétences : sélection et ordre pilotés par l'offre
    targeted, others = _profile_skills(match, profile.get("skills", []))
    if targeted:
        section = "Core Skills" if ats else f"Compétences clés pour le poste de {job.title}"
        prefix = f"## {section}" if not ats else section
        lines.append(prefix)
        for s in targeted:
            prof = PROFICIENCY_LABELS.get(s.get("proficiency", ""), "")
            if ats:
                lines.append(f"{s['skill']} ({prof})")
            else:
                lines.append(f"- **{s['skill']}** ({prof})")
        lines.append("")
    if others:
        section = "Additional Skills" if ats else "Autres compétences"
        lines.append(f"## {section}" if not ats else section)
        for s in others:
            prof = PROFICIENCY_LABELS.get(s.get("proficiency", ""), "")
            lines.append(f"- {s['skill']} ({prof})" if not ats else f"{s['skill']} ({prof})")
        lines.append("")

    # Expériences : tri par pertinence vis-à-vis de l'offre (§16)
    experiences = sorted(
        profile.get("experiences", []),
        key=lambda e: _experience_relevance(e, wanted),
        reverse=True,
    )
    if experiences:
        section = "Professional Experience" if ats else "Expérience"
        lines.append(f"## {section}" if not ats else section)
        for e in experiences:
            period = " – ".join(filter(None, [e.get("start_date"), e.get("end_date") or "présent"]))
            label = TYPE_LABELS.get(e.get("type", "formal"), "Expérience")
            if ats:
                lines.append(f"{e.get('title', '')} — {e.get('organization', '')}".rstrip(" —"))
                lines.append(period)
                if e.get("description"):
                    lines.append(e["description"])
            else:
                header = f"### {e.get('title', '')} · {e.get('organization', '')}".rstrip(" ·")
                lines.append(header)
                lines.append(f"*{label} · {period}*")
                if e.get("description"):
                    lines.append(e["description"])
            if e.get("skills"):
                lines.append("Compétences mobilisées : " + ", ".join(e["skills"]))
            lines.append("")

    # Projets
    projects = sorted(
        profile.get("projects", []),
        key=lambda p: _experience_relevance(p, wanted),
        reverse=True,
    )
    if projects:
        lines.append("## Projets")
        for p in projects:
            lines.append(f"### {p.get('name', '')}")
            if p.get("description"):
                lines.append(p["description"])
            if p.get("skills"):
                lines.append("Compétences mobilisées : " + ", ".join(p["skills"]))
            lines.append("")

    if profile.get("education"):
        section = "Education" if ats else "Formation"
        lines.append(f"## {section}" if not ats else section)
        for ed in profile["education"]:
            period = " – ".join(
                str(y) for y in [ed.get("start_year"), ed.get("end_year")] if y
            )
            entry = f"- {ed.get('degree', '')}"
            if ed.get("institution"):
                entry += f" · {ed['institution']}"
            if ed.get("field"):
                entry += f" ({ed['field']})"
            if period:
                entry += f" · {period}"
            lines.append(entry)
        lines.append("")

    if profile.get("certifications"):
        section = "Certifications" if ats else "Certifications"
        lines.append(f"## {section}" if not ats else section)
        for c in profile["certifications"]:
            entry = f"- {c.get('name', '')}"
            if c.get("issuer"):
                entry += f" · {c['issuer']}"
            if c.get("year"):
                entry += f" ({c['year']})"
            lines.append(entry)
        lines.append("")

    if profile.get("languages"):
        section = "Languages" if ats else "Langues"
        lines.append(f"## {section}" if not ats else section)
        lines.append(
            ", ".join(
                f"{l['language']} ({l['level']})" if l.get("level") else l["language"]
                for l in profile["languages"]
            )
        )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_letter_paragraphs(
    profile: dict[str, Any],
    job: Any,
    user: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
) -> dict[str, Any]:
    """Structure de lettre (partagée par le rendu markdown et le PDF) :
    salutation, paragraphes factuels, formule de politesse. Aucune invention."""
    from datetime import date

    match = compute_match(profile.get("skills", []), job.required_skills, taxonomy)
    strengths = match["covered"][:3] or [s["skill"] for s in profile.get("skills", [])[:3]]
    headline = profile.get("title") or job.title

    paragraphs = [
        (
            f"Votre offre de « {job.title} » à {job.location} a retenu toute mon "
            f"attention. En tant que {headline}, je souhaite mettre mes compétences "
            "au service de votre équipe."
        ),
    ]
    if strengths:
        para = (
            "Mon profil correspond directement à vos besoins : "
            + ", ".join(strengths) + "."
        )
        relevant = [
            e for e in profile.get("experiences", [])
            if set(e.get("skills") or []) & set(match["covered"])
        ]
        if relevant:
            e = relevant[0]
            para += (
                f" J'ai notamment développé ces compétences lors de mon expérience "
                f"« {e.get('title', '')}» ({e.get('organization', '')})."
            )
        paragraphs.append(para)
    if match["partial"]:
        paragraphs.append(
            "Je poursuis activement ma montée en compétences sur "
            + ", ".join(match["partial"][:2])
            + " pour couvrir l'intégralité de vos attentes."
        )

    return {
        "salutation": "Madame, Monsieur,",
        "paragraphs": paragraphs,
        "closing": [
            _agree(user,
                   "Je serais heureux d'échanger avec vous sur ma candidature.",
                   "Je serais heureuse d'échanger avec vous sur ma candidature.",
                   "Ce serait un plaisir d'échanger avec vous sur ma candidature."),
            "Dans l'attente de votre retour, je vous prie d'agréer, Madame, "
            "Monsieur, l'expression de ma considération distinguée.",
        ],
        "signature": str(user.full_name),
        "date_text": date.today().strftime("%d/%m/%Y"),
    }


def build_cover_letter(
    profile: dict[str, Any],
    job: Any,
    user: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
) -> str:
    """Lettre de motivation markdown, factuelle et contextualisée (§17)."""
    structure = build_letter_paragraphs(profile, job, user, taxonomy)

    lines = [
        f"# Lettre de motivation · {job.title} chez {job.company}",
        "",
        f"**{user.full_name}** · {profile.get('location') or 'Cameroun'}",
        (f"Contact : {user.email}" if getattr(user, "email", None) else ""),
        "",
        structure["salutation"],
        "",
    ]
    for para in structure["paragraphs"]:
        lines.append(para)
        lines.append("")
    lines += structure["closing"]
    lines += ["", f"**{structure['signature']}**"]
    return "\n".join(l for l in lines if l is not None).strip() + "\n"


def build_interview_prep(
    profile: dict[str, Any],
    job: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
) -> dict[str, Any]:
    """Préparation d'entretien dérivée des écarts et forces réels (§18)."""
    match = compute_match(profile.get("skills", []), job.required_skills, taxonomy)
    headline = profile.get("title") or job.title

    likely = [
        "Pouvez-vous vous présenter et décrire votre parcours en quelques minutes ?",
        f"Pourquoi souhaitez-vous rejoindre {job.company} sur ce poste de « {job.title} » ?",
    ]
    for name in match["covered"][:2]:
        exp = next(
            (e for e in profile.get("experiences", []) if name in (e.get("skills") or [])),
            None,
        )
        where = f" lors de votre expérience chez {exp['organization']}" if exp and exp.get("organization") else ""
        likely.append(f"Pouvez-vous illustrer votre pratique de « {name} »{where} ?")
    for name in match["missing"][:1]:
        likely.append(
            f"Le poste demande « {name} » : comment comptez-vous monter "
            f"rapidement en compétence ?"
        )

    technical = [
        f"Décrivez un cas concret d'utilisation de « {r['name']} »."
        for r in job.required_skills if r.get("importance", "core") == "core"
    ][:5]
    behavioral = [
        "Racontez une situation où vous avez résolu un problème difficile.",
        "Comment travaillez-vous en équipe sous pression ?",
        "Décrivez une expérience dont vous êtes fier, même informelle.",
    ]

    strengths = match["covered"][:3]
    experiences = profile.get("experiences", [])
    pitch = (
        f"Bonjour, je suis {profile.get('title') or 'un professionnel en début de carrière'}. "
    )
    if experiences:
        pitch += (
            f"J'ai cumulé des expériences sur le terrain, notamment "
            f"« {experiences[0].get('title', '')} » ({experiences[0].get('organization', 'expérience de terrain')}). "
        )
    if strengths:
        pitch += f"Mes points forts pour ce poste : {', '.join(strengths)}. "
    pitch += (
        f"Votre offre correspond exactement à la direction que je veux donner "
        f"à mon parcours de {headline}."
    )

    tips = [
        "Révisez chaque compétence listée dans l'offre et préparez un exemple concret.",
        "Admettez honnêtement les compétences manquantes et présentez votre plan d'apprentissage.",
    ]
    if match["missing"]:
        tips.append(
            "Préparez une réponse claire sur : " + ", ".join(match["missing"][:3]) + "."
        )
    tips.append("Apportez des réalisations concrètes (projets, missions, photos, résultats).")

    return {
        "likely_questions": likely,
        "technical": technical,
        "behavioral": behavioral,
        "pitch": pitch.strip(),
        "prep_tips": tips,
    }
