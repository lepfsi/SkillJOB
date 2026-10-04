"""Diagnostic par questionnaire (§9ter, mode sans CV).

Définit les étapes/questions et transforme les réponses en **brouillon** de
profil (non enregistré tant que l'utilisateur ne valide pas via PUT /api/profile).
"""
from app.services.skills_taxonomy import load_taxonomy

SECTOR_OPTIONS = [
    "Informatique / IT", "Data / Analyse", "Finance / Comptabilité",
    "Marketing / Communication", "BTP / Construction", "Agriculture / Agribusiness",
    "Santé", "Éducation / Formation", "Logistique / Transport", "ONG / International",
    "Commerce / Vente",
]
CONTRACT_OPTIONS = ["CDI", "CDD", "Stage", "Freelance", "Apprentissage"]
EXPERIENCE_KIND_MAP = {
    "Emploi salarié": "formal",
    "Freelance / missions": "freelance",
    "Bénévolat / associatif": "volunteer",
    "Apprentissage / stage": "apprenticeship",
    "Projet personnel": "project",
    "Petit boulot / activité informelle": "informal",
}
EDUCATION_LEVELS = [
    # Parcours francophones
    "Certificat d'études primaires (CEP)",
    "Secondaire (probatoire / baccalauréat)",
    "CAP / BEP",
    "BTS / DUT",
    "Licence",
    "Master",
    "Diplôme d'ingénieur (travaux ou conception)",
    "Doctorat",
    # Parcours anglophones (Cameroon)
    "First School Leaving Certificate (FSLC)",
    "GCE Ordinary Level",
    "GCE Advanced Level",
    # Sans diplôme scolaire : compétences reconnues
    "Formation professionnelle courte / recyclage (conduite, plomberie, manœuvre, gardiennage…)",
    "Compétences acquises sur le terrain (sans diplôme)",
]

# Niveau « sans diplôme » : on ne demande NI filière, NI établissement,
# NI certifications — seulement le domaine de débrouillardise (§5bis).
SANS_DIPLOME = "Compétences acquises sur le terrain (sans diplôme)"


def get_steps() -> dict:
    soft_skills = [
        e["name"] for e in load_taxonomy().all_entries()
        if e.get("category") == "Soft skills"
    ]
    return {
        "steps": [
            {
                "id": "identite",
                "title": "Informations générales",
                "questions": [
                    {"id": "q_title", "label": "Quel intitulé décrit le mieux votre profil ? (ex. Technicien support IT)", "type": "text"},
                    {"id": "q_location", "label": "Où habitez-vous ? (ville, région)", "type": "text"},
                    {"id": "q_availability", "label": "Quelle est votre disponibilité ?", "type": "choice",
                     "options": ["Immédiate", "Sous 1 mois", "Sous 3 mois"]},
                    {"id": "q_mobility", "label": "Quelle mobilité acceptez-vous ?", "type": "choice",
                     "options": ["Ma ville uniquement", "National", "International"]},
                ],
            },
            {
                "id": "formation",
                "title": "Formation",
                "questions": [
                    {"id": "q_education_level", "label": "Quel est votre plus haut niveau de formation ?", "type": "choice",
                     "options": EDUCATION_LEVELS},
                    # Questions académiques : posées uniquement si le talent
                    # n'est PAS en « sans diplôme » (le frontend les masque).
                    {"id": "q_field", "label": "Dans quelle filière ou spécialité ?", "type": "text"},
                    {"id": "q_institution", "label": "Dans quel établissement ?", "type": "text"},
                    {"id": "q_certifications", "label": "Certifications obtenues (une par ligne : nom, organisme, année)", "type": "textarea"},
                    # Compétences de terrain (« débrouillardise ») : posée à la
                    # place des questions académiques si « sans diplôme ».
                    {"id": "q_domain", "label": "Dans quel domaine savez-vous vous débrouiller ? Décrivez ce que vous savez faire (ex. plomberie, conduite de véhicules, manœuvre de chantier, gardiennage, mécanique, couture, cuisine…)", "type": "textarea"},
                ],
            },
            {
                "id": "experience",
                "title": "Expériences",
                "questions": [
                    {"id": "q_experience_kinds", "label": "Quels types d'expériences avez-vous vécues ?", "type": "multi_choice",
                     "options": list(EXPERIENCE_KIND_MAP.keys())},
                    {"id": "q_experience_desc", "label": "Décrivez vos expériences (une par ligne : rôle — structure — période — ce que vous faisiez)", "type": "textarea"},
                    {"id": "q_languages", "label": "Langues parlées (une par ligne : langue niveau)", "type": "textarea"},
                ],
            },
            {
                "id": "competences",
                "title": "Compétences",
                "questions": [
                    {"id": "q_skills", "label": "Listez vos compétences techniques (séparées par des virgules ou des retours à la ligne)", "type": "textarea"},
                    {"id": "q_soft_skills", "label": "Quelles qualités professionnelles vous décrivent ?", "type": "multi_choice",
                     "options": soft_skills},
                ],
            },
            {
                "id": "objectifs",
                "title": "Objectifs professionnels",
                "questions": [
                    {"id": "q_sectors", "label": "Quels secteurs vous intéressent ?", "type": "multi_choice",
                     "options": SECTOR_OPTIONS},
                    {"id": "q_target_roles", "label": "Quels métiers visez-vous ?", "type": "list"},
                    {"id": "q_contract_types", "label": "Quels types de contrat recherchez-vous ?", "type": "multi_choice",
                     "options": CONTRACT_OPTIONS},
                    {"id": "q_remote_ok", "label": "Acceptez-vous le télétravail ?", "type": "choice",
                     "options": ["Oui", "Non"]},
                ],
            },
        ]
    }


def _as_lines(value) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        parts = []
        for chunk in value.replace(";", "\n").split("\n"):
            parts.extend(c.strip() for c in chunk.split(",") if c.strip())
        return parts
    return []


def build_draft(answers: dict) -> tuple[dict, dict]:
    """Transforme les réponses du questionnaire en brouillon de profil."""
    taxonomy = load_taxonomy()

    # Compétences : résolution dans la taxonomie (alias -> canonique)
    skills: list[dict] = []
    seen: set[str] = set()
    for raw in _as_lines(answers.get("q_skills", "")):
        canonical = taxonomy.canonical(raw)
        if canonical not in seen:
            seen.add(canonical)
            skills.append({
                "skill": canonical,
                "category": taxonomy.category(canonical),
                "proficiency": "intermediaire",
                "source": "declared",
                "evidence_count": 0,
            })
    for soft in answers.get("q_soft_skills", []) or []:
        canonical = taxonomy.canonical(str(soft))
        if canonical not in seen:
            seen.add(canonical)
            skills.append({
                "skill": canonical,
                "category": taxonomy.category(canonical),
                "proficiency": "intermediaire",
                "source": "declared",
                "evidence_count": 0,
            })

    # Expériences
    kinds = [EXPERIENCE_KIND_MAP[k] for k in answers.get("q_experience_kinds", []) or []
             if k in EXPERIENCE_KIND_MAP]
    default_kind = kinds[0] if kinds else "informal"
    experiences = []
    for i, line in enumerate(_as_lines(answers.get("q_experience_desc", "")), start=1):
        detected = taxonomy.find_in_text(line)
        experiences.append({
            "id": f"q{i}",
            "title": line[:80],
            "organization": "",
            "type": default_kind,
            "description": line,
            "start_date": None,
            "end_date": None,
            "skills": detected,
        })
        for name in detected:
            for s in skills:
                if s["skill"] == name:
                    s["evidence_count"] += 1
                    s["source"] = "evidence"

    # Formation
    education = []
    certifications = []
    level = answers.get("q_education_level")
    domain = " ".join(_as_lines(answers.get("q_domain", "")))[:300]
    domain_title = ""
    domain_summary = ""
    if level == SANS_DIPLOME:
        # Parcours « sans diplôme » (§5bis) : pas de filière, d'établissement
        # ni de certifications demandés. Le domaine de débrouillardise
        # devient le titre du profil et nourrit la détection de compétences.
        if domain:
            # Titre : première clause, courte et lisible
            first_clause = domain.split(":")[0].split(",")[0].split(".")[0].strip()
            domain_title = (first_clause[:60] if first_clause else domain[:60]).capitalize()
            domain_summary = (
                f"Compétences de terrain : {domain}. "
                "L'absence de diplôme ne reflète pas l'absence de compétence."
            )
        for name in taxonomy.find_in_text(domain):
            if name not in seen:
                seen.add(name)
                skills.append({
                    "skill": name,
                    "category": taxonomy.category(name),
                    "proficiency": "intermediaire",
                    "source": "inferred",
                    "evidence_count": 0,
                })
    else:
        if level:
            education.append({
                "degree": str(level),
                "institution": str(answers.get("q_institution") or ""),
                "field": str(answers.get("q_field") or ""),
                "start_year": None,
                "end_year": None,
            })
        # Format documenté : « une par ligne : nom, organisme, année »
        for line in (answers.get("q_certifications", "") or "").replace(";", "\n").split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",") if p.strip()]
            certifications.append({
                "name": parts[0],
                "issuer": parts[1] if len(parts) > 1 else "",
                "year": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else None,
            })

    # Langues
    languages = []
    for line in _as_lines(answers.get("q_languages", "")):
        parts = line.rsplit(" ", 1)
        if len(parts) == 2:
            languages.append({"language": parts[0], "level": parts[1]})
        else:
            languages.append({"language": line, "level": ""})

    preferences = {
        "sectors": [str(s) for s in answers.get("q_sectors", []) or []],
        "target_roles": _as_lines(answers.get("q_target_roles", [])),
        "contract_types": [str(c) for c in answers.get("q_contract_types", []) or []],
        "remote_ok": str(answers.get("q_remote_ok", "")).lower() in ("oui", "yes", "o", "true"),
    }

    profile = {
        "user_id": 0,
        "summary": domain_summary,
        "title": str(answers.get("q_title") or "") or domain_title or None,
        "location": str(answers.get("q_location") or "") or None,
        "mobility": str(answers.get("q_mobility") or "") or None,
        "availability": str(answers.get("q_availability") or "") or None,
        "education": education,
        "experiences": experiences,
        "certifications": certifications,
        "languages": languages,
        "projects": [],
        "skills": skills,
        "preferences": preferences,
    }
    report = {
        "skills_found": len(skills),
        "experiences_found": len(experiences),
        "certifications_found": len(certifications),
        "degrees_found": len(education),
        "career_fields": sorted({s["category"] for s in skills}),
    }
    return profile, report
