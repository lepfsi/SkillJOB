"""CV Intelligence : génération de documents ciblés SANS invention (§15-18).

Toutes les données utilisées proviennent exclusivement du profil validé par
l'utilisateur : le générateur réordonne et valorise, il n'invente jamais de
diplôme, d'expérience ou de compétence.

Six modèles de CV au choix :
- ``classique``     : hiérarchie lisible, compétences ciblées d'abord ;
- ``ats``           : compatible ATS (une colonne, intitulés standards,
                      aucune mise en forme exotique) ;
- ``moderne``       : en-tête resserré, résumé élargi, ton direct ;
- ``deux_colonnes`` : bandeau latéral (identité, compétences, langues)
                      + colonne principale (parcours) ;
- ``elegant``       : serif, liserés fins, pour les secteurs traditionnels
                      (administrations, banques, éducation) ;
- ``compact``       : tout tenir sur une page, marges resserrées.

Trois modèles de lettre : ``classique`` (conventions épistolaires),
``moderne`` (en-tête accentué) et ``email`` (candidature par courriel).

Le contenu reste le même d'un modèle à l'autre : un modèle est une MISE EN
PAGE du profil validé, jamais une autre histoire.
"""
from typing import Any, Literal, Optional

from app.services.matching import compute_match
from app.services.skills_taxonomy import SkillsTaxonomy

TemplateId = Literal["classique", "ats", "moderne", "deux_colonnes", "elegant", "compact"]

TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "classique",
        "name": "Classique",
        "description": (
            "Mise en page sobre aux normes internationales : compétences "
            "ciblées par l'offre en tête, expériences datées, sections nettes."
        ),
        "ats_friendly": True,
        "columns": 1,
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
        "columns": 1,
    },
    {
        "id": "moderne",
        "name": "Moderne",
        "description": (
            "En-tête percutant, résumé élargi en accroche, lecture rapide "
            "pour les recrutements directs et les réseaux."
        ),
        "ats_friendly": False,
        "columns": 1,
    },
    {
        "id": "deux_colonnes",
        "name": "Deux colonnes",
        "description": (
            "Bandeau latéral coloré : identité, contact, compétences et "
            "langues à gauche ; parcours et formation à droite. Repère du "
            "regard, idéal quand les compétences parlent d'abord."
        ),
        "ats_friendly": False,
        "columns": 2,
    },
    {
        "id": "elegant",
        "name": "Élégant",
        "description": (
            "Typographie serif et liserés fins, pour les milieux attachés "
            "aux conventions : administrations, banques, établissements "
            "d'enseignement."
        ),
        "ats_friendly": True,
        "columns": 1,
    },
    {
        "id": "compact",
        "name": "Compact (1 page)",
        "description": (
            "Tout tenir sur une page : marges resserrées, sections denses. "
            "Pensé pour les débuts de parcours et les sélections rapides."
        ),
        "ats_friendly": True,
        "columns": 1,
    },
]

# Modèles de lettre de motivation (mêmes faits, autre mise en page).
LETTER_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "classique",
        "name": "Classique",
        "description": (
            "Conventions épistolaires complètes : en-tête expéditeur/"
            "destinataire, objet, formule de politesse. Pour les dossiers "
            "papier et les administrations."
        ),
    },
    {
        "id": "moderne",
        "name": "Moderne",
        "description": (
            "En-tête aux couleurs de votre CV, objet mis en avant, ton "
            "direct. Cohérent avec le CV « Moderne » ou « Deux colonnes »."
        ),
    },
    {
        "id": "email",
        "name": "Courriel",
        "description": (
            "Format e-mail prêt à coller : objet net, corps resserré, "
            "signature avec coordonnées. Pour les candidatures en ligne."
        ),
    },
]

# Couleurs d'accent au choix : personnalisation sans inventer de contenu.
# « hex » = accent VIF (celui qui se voit sur les règles et filets du PDF,
# cf. cv_pdf.TONE) : c'est aussi ce que l'interface affiche dans les pastilles.
# Un accent personnalisé au format #RRGGBB est accepté en plus du catalogue.
ACCENTS: dict[str, dict[str, str]] = {
    "vert": {"label": "Vert", "hex": "#2FB37A"},
    "bleu": {"label": "Bleu", "hex": "#3AA6E0"},
    "orange": {"label": "Orange", "hex": "#F0932B"},
    "bordeaux": {"label": "Bordeaux", "hex": "#C2475D"},
    "ardoise": {"label": "Ardoise", "hex": "#7FA3B5"},
    "violet": {"label": "Violet", "hex": "#7C5CE0"},
    "turquoise": {"label": "Turquoise", "hex": "#22B8B0"},
    "rouge": {"label": "Rouge", "hex": "#D9534F"},
    "rose": {"label": "Rose", "hex": "#D66A9A"},
    "indigo": {"label": "Indigo", "hex": "#4C5FD5"},
    "ambre": {"label": "Ambre", "hex": "#D9A21B"},
    "menthe": {"label": "Menthe", "hex": "#3FBF8F"},
    "brun": {"label": "Brun", "hex": "#8B5E3C"},
}

# Accent par défaut quand le candidat n'en choisit pas. Le modèle ATS
# garde sa charte bleu nuit / turquoise tant qu'aucune couleur n'est
# demandée, mais honore une couleur explicitement choisie.
DEFAULT_ACCENTS: dict[str, Optional[str]] = {
    "classique": "vert",
    "ats": None,
    "moderne": "orange",
    "deux_colonnes": "vert",
    "elegant": "bordeaux",
    "compact": "bleu",
}

# Mois en clair pour les dates des CV (mêmes intitulés que le gabarit ATS).
MONTHS_FR = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]


def is_custom_accent(value: Optional[str]) -> bool:
    """Vrai si la valeur est une couleur hexadécimale #RRGGBB."""
    if not value or len(value) != 7 or not value.startswith("#"):
        return False
    try:
        int(value[1:], 16)
    except ValueError:
        return False
    return True


def is_valid_accent(value: Optional[str]) -> bool:
    return value in ACCENTS or is_custom_accent(value)


def format_period(start: Optional[str], end: Optional[str],
                  current: str = "présent", join: str = " - ") -> str:
    """Période de dates en clair : « Août 2024 - Mai 2026 ».

    Les valeurs ``AAAA-MM`` sont converties avec le mois en toutes lettres
    (comme le gabarit ATS) ; les autres formats sont conservés tels quels.
    """
    def one(value: Optional[str]) -> str:
        value = (value or "").strip()
        if len(value) >= 7 and value[4] == "-" and value[:4].isdigit() and value[5:7].isdigit():
            month = int(value[5:7])
            if 1 <= month <= 12:
                return f"{MONTHS_FR[month - 1]} {value[:4]}"
        return value

    parts = [one(start)]
    parts.append(one(end) if end else current)
    return join.join(p for p in parts if p)


def domain_line(profile: dict[str, Any]) -> str:
    """Ligne de domaines du profil : domaine choisi et spécialités réelles.

    Seules les valeurs du référentiel sont reprises (aucune invention). Le
    libellé « Autres » est remplacé par le texte saisi par le candidat.
    """
    prefs = profile.get("preferences") or {}
    parts: list[str] = []
    domain = prefs.get("domain_name") or ""
    if domain == "Autres" and prefs.get("domain_other"):
        domain = prefs["domain_other"]
    if domain:
        parts.append(domain)
    for name in prefs.get("specialty_names") or []:
        if name and name != "Autres" and name not in parts:
            parts.append(name)
    return " · ".join(parts[:4])

# Accent par défaut quand le candidat n'en choisit pas.
DEFAULT_ACCENTS: dict[str, Optional[str]] = {
    "classique": "vert",
    "ats": None,
    "moderne": "orange",
    "deux_colonnes": "vert",
    "elegant": "bordeaux",
    "compact": "bleu",
}

TEMPLATE_LABELS: dict[str, str] = {
    "classique": "",
    "ats": "ATS · ",
    "moderne": "moderne · ",
    "deux_colonnes": "deux colonnes · ",
    "elegant": "élégant · ",
    "compact": "compact · ",
}

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


def list_letter_templates() -> list[dict[str, Any]]:
    return LETTER_TEMPLATES

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
    domains = domain_line(profile)
    if ats and domains:
        lines.append(f"Domaines : {domains}")
    lines.append("")

    # Résumé : uniquement des éléments factuels du profil validé
    summary = profile.get("summary")
    if not summary and match["covered"]:
        summary = (
            f"Profil orienté « {job.title} » ; compétences pertinentes déjà "
            f"acquises : {', '.join(match['covered'][:5])}."
        )
    if summary:
        section = "Profil" if ats else "Résumé"
        if ats:
            # ATS : paragraphe continu, pas de mise en forme
            lines += [section, summary.replace("\n", " "), ""]
        else:
            lines += [f"## {section}", summary, ""]

    # Compétences : sélection et ordre pilotés par l'offre
    targeted, others = _profile_skills(match, profile.get("skills", []))
    if targeted:
        section = f"Compétences clés pour le poste de {job.title}"
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
        section = "Autres compétences"
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
        section = "Expérience professionnelle" if ats else "Expérience"
        lines.append(f"## {section}" if not ats else section)
        for e in experiences:
            period = format_period(e.get("start_date"), e.get("end_date"))
            label = TYPE_LABELS.get(e.get("type", "formal"), "Expérience")
            if ats:
                lines.append(f"{e.get('title', '')} - {e.get('organization', '')}".rstrip(" -"))
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
        lines.append("## Projets" if not ats else "Projets")
        for p in projects:
            lines.append(f"### {p.get('name', '')}" if not ats else p.get("name", ""))
            if p.get("description"):
                lines.append(p["description"])
            if p.get("skills"):
                lines.append("Compétences mobilisées : " + ", ".join(p["skills"]))
            lines.append("")

    # Certifications avant Formation, comme le gabarit ATS de référence.
    if profile.get("certifications"):
        section = "Certifications"
        lines.append(f"## {section}" if not ats else section)
        for c in profile["certifications"]:
            entry = f"- {c.get('name', '')}" if not ats else c.get("name", "")
            if ats:
                if c.get("issuer"):
                    entry += f" - {c['issuer']}"
                if c.get("year"):
                    entry += f" ({c['year']})"
            else:
                if c.get("issuer"):
                    entry += f" · {c['issuer']}"
                if c.get("year"):
                    entry += f" ({c['year']})"
            lines.append(entry)
        lines.append("")

    if profile.get("education"):
        section = "Formation"
        lines.append(f"## {section}" if not ats else section)
        for ed in profile["education"]:
            period = " - ".join(
                str(y) for y in [ed.get("start_year"), ed.get("end_year")] if y
            )
            entry = f"- {ed.get('degree', '')}" if not ats else ed.get("degree", "")
            if ats:
                if ed.get("institution"):
                    entry += f" - {ed['institution']}"
                if ed.get("field"):
                    entry += f" ({ed['field']})"
                if period:
                    entry += f" ({period})"
            else:
                if ed.get("institution"):
                    entry += f" · {ed['institution']}"
                if ed.get("field"):
                    entry += f" ({ed['field']})"
                if period:
                    entry += f" · {period}"
            lines.append(entry)
        lines.append("")

    if profile.get("languages"):
        section = "Langues" if not ats else "Langues"
        lines.append(f"## {section}" if not ats else section)
        lines.append(
            ", ".join(
                f"{l['language']} ({l['level']})" if l.get("level") else l["language"]
                for l in profile["languages"]
            )
        )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_general_cv(
    profile: dict[str, Any],
    user: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
    template: str = "classique",
) -> str:
    """CV GÉNÉRALISTE (aucune offre ciblée) : le profil complet, honnête.

    Même règle que le CV ciblé (§47) : réorganisation du profil validé,
    zéro invention. Les compétences sont triées par preuves puis par
    niveau, les expériences de la plus récente à la plus ancienne.
    """
    ats = template == "ats"
    lines: list[str] = []
    lines.append(f"# {user.full_name}")
    lines.append(f"**{profile.get('title') or 'Profil professionnel'}** · "
                 f"{profile.get('location') or 'Cameroun'}")
    if getattr(user, "email", None):
        lines.append(f"Contact : {user.email}")
    if profile.get("availability"):
        lines.append(f"Disponibilité : {profile['availability']}")
    if getattr(user, "verification_status", None) == "verified":
        lines.append("Profil vérifié OrientSkill AI")
    domains = domain_line(profile)
    if ats and domains:
        lines.append(f"Domaines : {domains}")
    lines.append("")

    summary = profile.get("summary")
    if not summary:
        skills = sorted(
            profile.get("skills", []),
            key=lambda s: (-s.get("evidence_count", 0), s["skill"]),
        )
        if skills:
            summary = (
                "Compétences principales : "
                + ", ".join(s["skill"] for s in skills[:6]) + "."
            )
    if summary:
        section = "Profil" if ats else "Résumé"
        lines += [section, summary.replace("\n", " "), ""] if ats else [f"## {section}", summary, ""]

    skills = sorted(
        profile.get("skills", []),
        key=lambda s: (-s.get("evidence_count", 0), s["skill"]),
    )
    if skills:
        section = "Compétences"
        lines.append(section if ats else f"## {section}")
        for s in skills:
            prof = PROFICIENCY_LABELS.get(s.get("proficiency", ""), "")
            lines.append(f"{s['skill']} ({prof})" if ats else f"- **{s['skill']}** ({prof})")
        lines.append("")

    experiences = sorted(
        profile.get("experiences", []),
        key=lambda e: (e.get("end_date") or "9999-12", e.get("start_date") or ""),
        reverse=True,
    )
    if experiences:
        section = "Expérience professionnelle" if ats else "Expérience"
        lines.append(section if ats else f"## {section}")
        for e in experiences:
            period = format_period(e.get("start_date"), e.get("end_date"))
            label = TYPE_LABELS.get(e.get("type", "formal"), "Expérience")
            if ats:
                lines.append(f"{e.get('title', '')} - {e.get('organization', '')}".rstrip(" -"))
                lines.append(period)
                if e.get("description"):
                    lines.append(e["description"])
            else:
                lines.append(f"### {e.get('title', '')} · {e.get('organization', '')}".rstrip(" ·"))
                lines.append(f"*{label} · {period}*")
                if e.get("description"):
                    lines.append(e["description"])
            if e.get("skills"):
                lines.append("Compétences mobilisées : " + ", ".join(e["skills"]))
            lines.append("")

    for key, ats_name, fr_name in (
        ("projects", "Projets", "Projets"),
        ("certifications", "Certifications", "Certifications"),
        ("education", "Formation", "Formation"),
    ):
        items = profile.get(key) or []
        if not items:
            continue
        section = ats_name if ats else fr_name
        lines.append(section if ats else f"## {section}")
        if key == "projects":
            for p in items:
                lines.append(f"### {p.get('name', '')}" if not ats else p.get("name", ""))
                if p.get("description"):
                    lines.append(p["description"])
                if p.get("skills"):
                    lines.append("Compétences mobilisées : " + ", ".join(p["skills"]))
                lines.append("")
        elif key == "education":
            for ed in items:
                period = (" - ".join(str(y) for y in [ed.get("start_year"), ed.get("end_year")] if y)
                          if ats else " à ".join(str(y) for y in [ed.get("start_year"), ed.get("end_year")] if y))
                if ats:
                    entry = ed.get("degree", "")
                    if ed.get("institution"):
                        entry += f" - {ed['institution']}"
                    if ed.get("field"):
                        entry += f" ({ed['field']})"
                    if period:
                        entry += f" ({period})"
                else:
                    entry = f"- {ed.get('degree', '')}"
                    if ed.get("institution"):
                        entry += f" · {ed['institution']}"
                    if ed.get("field"):
                        entry += f" ({ed['field']})"
                    if period:
                        entry += f" · {period}"
                lines.append(entry)
            lines.append("")
        else:
            for c in items:
                if ats:
                    entry = c.get("name", "")
                    if c.get("issuer"):
                        entry += f" - {c['issuer']}"
                    if c.get("year"):
                        entry += f" ({c['year']})"
                else:
                    entry = f"- {c.get('name', '')}"
                    if c.get("issuer"):
                        entry += f" · {c['issuer']}"
                    if c.get("year"):
                        entry += f" ({c['year']})"
                lines.append(entry)
            lines.append("")

    if profile.get("languages"):
        section = "Langues"
        lines.append(section if ats else f"## {section}")
        lines.append(", ".join(
            f"{l['language']} ({l['level']})" if l.get("level") else l["language"]
            for l in profile["languages"]
        ))
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_letter_paragraphs(
    profile: dict[str, Any],
    job: Optional[Any],
    user: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
) -> dict[str, Any]:
    """Structure de lettre (partagée par le rendu markdown et le PDF) :
    salutation, paragraphes factuels, formule de politesse. Aucune invention.

    ``job=None`` produit une LETTRE GÉNÉRALISTE : le destinataire reste à
    compléter ([Nom de l'entreprise], [Ville]) et le contenu se limite aux
    faits du profil validé.
    """
    from datetime import date

    skills = sorted(
        profile.get("skills", []),
        key=lambda s: (-s.get("evidence_count", 0), s["skill"]),
    )
    headline = profile.get("title") or (job.title if job is not None else "professionnel")

    if job is not None:
        match = compute_match(profile.get("skills", []), job.required_skills, taxonomy)
        strengths = match["covered"][:3] or [s["skill"] for s in skills[:3]]
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
    else:
        paragraphs = [
            (
                "Je vous adresse ma candidature spontanée : "
                f"{headline}, je souhaite mettre mes compétences au service "
                "de votre organisation."
            ),
        ]
        summary = profile.get("summary")
        if summary:
            paragraphs.append(summary)
        elif skills:
            para = (
                "Mon profil s'appuie sur des compétences documentées : "
                + ", ".join(s["skill"] for s in skills[:4]) + "."
            )
            experiences = profile.get("experiences", [])
            if experiences:
                e = experiences[0]
                para += (
                    f" Je les ai notamment mises en pratique lors de mon expérience "
                    f"« {e.get('title', '')} » ({e.get('organization', '')})."
                )
            paragraphs.append(para)
        facts = []
        if profile.get("availability"):
            avail = str(profile["availability"]).strip()
            if avail.lower().startswith("imm"):
                facts.append("Je suis disponible immédiatement.")
            else:
                facts.append(f"Ma disponibilité : {avail.lower()}.")
        if profile.get("location"):
            facts.append(f"Je réside à {profile['location']}.")
        if facts:
            paragraphs.append(" ".join(facts))

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
    job: Optional[Any],
    user: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
    template: str = "classique",
) -> str:
    """Lettre de motivation markdown, factuelle et contextualisée (§17).

    Le modèle change la mise en page, jamais les faits : ``email`` est
    prêt à coller dans un courriel, ``moderne`` aligne l'en-tête sur le
    CV du même nom, ``classique`` suit les conventions épistolaires.

    ``job=None`` produit une LETTRE GÉNÉRALISTE dont le destinataire est
    à compléter ([Nom de l'entreprise], [Ville]).
    """
    structure = build_letter_paragraphs(profile, job, user, taxonomy)

    if job is not None:
        objet = f"candidature au poste de « {job.title} » ({job.company})"
        heading = f"Lettre de motivation · {job.title} chez {job.company}"
        recipient = None
    else:
        objet = (f"candidature spontanée : "
                 f"{profile.get('title') or 'profil professionnel'}")
        heading = "Lettre de motivation · candidature spontanée"
        recipient = "**Destinataire : [Nom de l'entreprise] · [Ville]**"

    if template == "email":
        lines = [
            f"**Objet : {objet}**",
            "",
        ]
        if recipient:
            lines += [recipient, ""]
        lines += [structure["salutation"], ""]
        for para in structure["paragraphs"]:
            lines.append(para)
            lines.append("")
        lines += structure["closing"]
        lines += ["", "--", f"**{user.full_name}**"]
        headline = profile.get("title")
        if headline:
            lines.append(f"{headline} · {profile.get('location') or 'Cameroun'}")
        if getattr(user, "email", None):
            lines.append(str(user.email))
        return "\n".join(lines).strip() + "\n"

    if template == "moderne":
        lines = [
            f"# {user.full_name}",
            "",
        ]
        headline = profile.get("title") or (job.title if job is not None else "")
        if headline:
            lines.append(f"**{headline}** · {profile.get('location') or 'Cameroun'}")
        if getattr(user, "email", None):
            lines.append(str(user.email))
        lines += [
            "",
            f"**Objet : {objet}**",
            "",
        ]
        if recipient:
            lines += [recipient, ""]
        lines += [structure["salutation"], ""]
        for para in structure["paragraphs"]:
            lines.append(para)
            lines.append("")
        lines += structure["closing"]
        lines += ["", f"**{structure['signature']}**"]
        return "\n".join(lines).strip() + "\n"

    lines = [
        f"# {heading}",
        "",
        f"**{user.full_name}** · {profile.get('location') or 'Cameroun'}",
        (f"Contact : {user.email}" if getattr(user, "email", None) else ""),
        "",
    ]
    if recipient:
        lines += [recipient, ""]
    lines += [
        structure["salutation"],
        "",
    ]
    for para in structure["paragraphs"]:
        lines.append(para)
        lines.append("")
    lines += structure["closing"]
    lines += ["", f"**{structure['signature']}**"]
    return "\n".join(l for l in lines if l is not None).strip() + "\n"


def build_general_letter(
    profile: dict[str, Any],
    user: Any,
    taxonomy: Optional[SkillsTaxonomy] = None,
    template: str = "classique",
) -> str:
    """Lettre GÉNÉRALISTE (sans offre ciblée) : mêmes faits que le profil
    validé, destinataire à compléter par le candidat (§47 respecté)."""
    return build_cover_letter(profile, None, user, taxonomy, template=template)


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
