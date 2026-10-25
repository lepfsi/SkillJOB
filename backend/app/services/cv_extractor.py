"""Extraction par règles d'un profil structuré depuis un texte de CV (§9ter).

Produit un **brouillon** de profil (jamais enregistré automatiquement) et un
rapport d'extraction. Aucune donnée n'est inventée : seules les informations
présentes dans le texte sont reprises.
"""
import io
import re

from app.services.skills_taxonomy import SkillsTaxonomy, load_taxonomy, normalize

SECTION_HEADERS: dict[str, list[str]] = {
    "education": [
        "formation", "education", "etudes", "diplomes", "parcours scolaire",
        "parcours academique", "cursus",
    ],
    "experience": [
        "experience professionnelle", "experiences professionnelles",
        "experience", "experiences", "parcours professionnel", "emplois",
        "activites professionnelles",
    ],
    "skills": [
        "competences", "skills", "competences techniques", "savoir-faire",
        "competences informatiques",
    ],
    "certifications": ["certifications", "certificats", "attestations"],
    "languages": ["langues", "languages", "langues parlees"],
    "projects": ["projets", "projects", "realisations"],
}

DEGREE_RE = re.compile(
    r"(doctorat|phd|master|mba|licence|bachelor|bts|dut|deug|baccalaur[eé]at|"
    r"probatoire|ing[eé]nieur|dipl[oô]me|certificat universitaire|cap\b|"
    r"formation professionnelle|dsep|dscn)",
    re.IGNORECASE,
)

DATE_RANGE_RE = re.compile(
    r"((?:19|20)\d{2}(?:[-/]\d{1,2})?)"
    r"\s*(?:[-\u2013/]|\bà\b|\ba\b|\bto\b)\s*"
    r"((?:19|20)\d{2}(?:[-/]\d{1,2})?|pr[eé]sent|aujourd.?hui|"
    r"en cours|now|present|current)?",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"(?:19|20)\d{2}")

LANGUAGE_NAMES = {
    "francais": "Français", "anglais": "Anglais", "english": "Anglais",
    "espagnol": "Espagnol", "allemand": "Allemand", "arabe": "Arabe",
    "italien": "Italien", "portugais": "Portugais", "chinois": "Chinois",
    "ewondo": "Ewondo", "douala": "Douala", "fulfulde": "Fulfuldé",
}
LEVEL_KEYWORDS = {
    "natif": "natif", "maternel": "natif", "courant": "courant",
    "bilingue": "courant", "fluent": "courant", "avance": "avance",
    "c1": "avance", "c2": "avance", "intermediaire": "intermediaire",
    "b1": "intermediaire", "b2": "intermediaire", "debutant": "debutant",
    "notions": "debutant", "a1": "debutant", "a2": "debutant",
}

CERT_KEYWORDS = re.compile(
    r"(ccna|ccnp|cissp|pmp|prince2|toeic|toefl|scrum|itil|fortinet|nse\d|"
    r"certifi[cé]|certification|attestation)",
    re.IGNORECASE,
)

TITLE_KEYWORDS = [
    "developpeur", "ingenieur", "technicien", "administrateur", "analyste",
    "comptable", "infirmier", "charge de", "responsable", "assistant",
    "commercial", "community manager", "agronome", "conducteur", "formateur",
    "consultant", "enseignant", "data analyst", "designer",
]

EXPERIENCE_TYPE_KEYWORDS: list[tuple[list[str], str]] = [
    (["stage", "stagiaire", "apprentissage", "apprenti", "alternance"], "apprenticeship"),
    (["freelance", "mission ponctuelle", "consultant independant", "prestation"], "freelance"),
    (["benevol", "volontr?", "volontariat", "associatif", "communautaire", "ong"], "volunteer"),
    (["informel", "petit commerce", "quartier", "activite familiale", "gagiste"], "informal"),
    (["projet personnel", "projet perso", "personal project", "side project"], "project"),
]

UP_KEYWORDS = ["expert", "senior", "maitrise", "avance", "confirmee", "confirmé"]
DOWN_KEYWORDS = ["notions", "debutant", "initiation", "bases", "decouverte", "en cours d"]


def _split_lines(text: str) -> list[str]:
    lines = []
    for raw in text.replace("\r", "\n").split("\n"):
        line = re.sub(r"^[•\-\*\u2022\t ]+", "", raw).strip()
        if line:
            lines.append(line)
    return lines


def _detect_section(line: str, current: str) -> str:
    norm = normalize(line)
    if len(line) <= 50:
        for section, keywords in SECTION_HEADERS.items():
            for kw in keywords:
                if norm == kw or norm.startswith(kw + " ") or norm.endswith(" " + kw):
                    return section
    return current


def _extract_years(line: str) -> tuple[str | None, str | None]:
    match = DATE_RANGE_RE.search(line)
    if not match:
        return None, None
    start = match.group(1)
    end_raw = match.group(2)
    end = end_raw if end_raw and end_raw[:2] in ("19", "20") else None
    if end_raw and end is None:
        end = None  # "présent" -> en cours, pas de date de fin
    return start, end


def _experience_type(line: str) -> str:
    norm = normalize(line)
    for keywords, exp_type in EXPERIENCE_TYPE_KEYWORDS:
        for kw in keywords:
            if re.search(kw, norm):
                return exp_type
    return "formal"


def _split_title_org(line: str) -> tuple[str, str]:
    """Sépare « Titre - Organisation » sur un séparateur courant."""
    parts = re.split(r"\s[\u2013\u2014|]\s|\s+-\s+|\s+chez\s+|\s+at\s+", line, maxsplit=1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return line.strip(), ""


def _proficiency_hint(norm_text: str, position: int) -> str:
    window = norm_text[max(0, position - 60): position + 60]
    if any(kw in window for kw in UP_KEYWORDS):
        return "avance"
    if any(kw in window for kw in DOWN_KEYWORDS):
        return "debutant"
    return "intermediaire"


def extract_profile(text: str) -> tuple[dict, dict]:
    """Extrait un brouillon de profil + rapport depuis un texte de CV."""
    taxonomy = load_taxonomy()
    lines = _split_lines(text)
    norm_text = normalize(text)

    # --- Découpage en sections
    sections: dict[str, list[str]] = {k: [] for k in SECTION_HEADERS}
    current = "summary"
    for line in lines:
        new_section = _detect_section(line, current)
        if new_section != current:
            current = new_section
            continue
        if current != "summary":
            sections.setdefault(current, []).append(line)

    # --- Titre professionnel : courte ligne avec mot-clé métier en tête du CV
    title: str | None = None
    for line in lines[:8]:
        norm = normalize(line)
        if len(line) <= 70 and any(kw in norm for kw in TITLE_KEYWORDS):
            title = line
            break

    # --- Compétences détectées via la taxonomie (alias -> canonique)
    skills: list[dict] = []
    seen: set[str] = set()
    for alias, canonical in sorted(
        taxonomy._aliases.items(), key=lambda kv: len(kv[0]), reverse=True
    ):
        pattern = taxonomy._boundary_pattern(alias)
        match = pattern.search(norm_text)
        if match and canonical not in seen:
            seen.add(canonical)
            skills.append({
                "skill": canonical,
                "category": taxonomy.category(canonical),
                "proficiency": _proficiency_hint(norm_text, match.start()),
                "source": "declared",
                "evidence_count": 0,
            })

    # --- Formation
    education: list[dict] = []
    for line in sections["education"]:
        if DEGREE_RE.search(line) or YEAR_RE.search(line):
            years = YEAR_RE.findall(line)
            clean = DATE_RANGE_RE.sub("", line).strip(" -\u2013\u2014|,")
            institution = ""
            inst_match = re.search(
                r"(universit[eé][^,;\-]*|[eé]cole[^,;\-]*|institut[^,;\-]*|"
                r"ENSA[^,;\-]*|IUT[^,;\-]*|lyc[eé]e[^,;\-]*)",
                line, re.IGNORECASE,
            )
            if inst_match:
                institution = inst_match.group(1).strip()
            if clean:
                education.append({
                    "degree": clean,
                    "institution": institution,
                    "field": "",
                    "start_year": int(years[0]) if years else None,
                    "end_year": int(years[1]) if len(years) > 1 else None,
                })
            elif years and education:
                # La période figure souvent sur la ligne suivante.
                education[-1]["start_year"] = int(years[0])
                if len(years) > 1:
                    education[-1]["end_year"] = int(years[1])

    # --- Expériences (formelles ou informelles : toutes comptent, §5bis.1)
    experiences: list[dict] = []
    experience_lines = list(sections["experience"])
    # date de période hors section expérience -> expérience probable
    for line in lines:
        if line in sections["experience"] or line in sections["education"]:
            continue
        if DATE_RANGE_RE.search(line) and not DEGREE_RE.search(line) and len(line) > 15:
            experience_lines.append(line)
    seen_lines: set[str] = set()
    dated_indices = [
        index for index, line in enumerate(experience_lines)
        if DATE_RANGE_RE.search(line) and not DEGREE_RE.search(line)
    ]
    if dated_indices:
        # Une expérience = un titre suivi d'une période. Les lignes de
        # description ne deviennent plus des expériences à part entière.
        for index in dated_indices:
            line = experience_lines[index]
            if line in seen_lines:
                continue
            seen_lines.add(line)
            start, end = _extract_years(line)
            clean = DATE_RANGE_RE.sub("", line).strip(" -\u2013\u2014|,")
            title_source = line if len(clean) >= 4 else (
                experience_lines[index - 1] if index > 0 else ""
            )
            if not title_source or title_source == title:
                continue
            if title_source in sections["education"]:
                continue
            title_clean = DATE_RANGE_RE.sub("", title_source).strip(
                " -\u2013\u2014|,"
            )
            title_part, org = _split_title_org(title_clean)
            if len(title_part) < 4:
                continue
            description_parts: list[str] = []
            if index + 1 < len(experience_lines):
                following = experience_lines[index + 1]
                next_is_date = (
                    index + 2 < len(experience_lines)
                    and DATE_RANGE_RE.search(experience_lines[index + 2])
                )
                if not DATE_RANGE_RE.search(following) and not next_is_date:
                    description_parts.append(following)
            block = [title_source, line, *description_parts]
            experiences.append({
                "title": title_part,
                "organization": org,
                "type": _experience_type(" ".join(block)),
                "description": " ".join(description_parts),
                "start_date": start,
                "end_date": end,
                "skills": taxonomy.find_in_text(" ".join(block)),
            })
    else:
        for line in experience_lines:
            if len(line) < 8 or line in seen_lines:
                continue
            seen_lines.add(line)
            if line == title or line in sections["education"]:
                continue
            title_part, org = _split_title_org(line)
            if len(title_part) < 4:
                continue
            experiences.append({
                "title": title_part,
                "organization": org,
                "type": _experience_type(line),
                "description": line,
                "start_date": None,
                "end_date": None,
                "skills": taxonomy.find_in_text(line),
            })

    # --- Certifications
    certifications: list[dict] = []
    cert_lines = list(sections["certifications"])
    for line in lines:
        if line not in cert_lines and CERT_KEYWORDS.search(line) and line not in seen_lines:
            cert_lines.append(line)
    for line in cert_lines:
        if len(line) < 4:
            continue
        year_match = YEAR_RE.search(line)
        certifications.append({
            "name": line.strip(" -\u2013\u2014"),
            "issuer": "",
            "year": int(year_match.group(0)) if year_match else None,
        })

    # --- Langues : section dédiée, sinon ligne avec un niveau explicite.
    # Scanne tout le texte ferait de "Douala" une langue dans l'en-tête.
    languages: list[dict] = []
    language_lines = sections["languages"] or None
    scan_lines = language_lines if language_lines else lines
    for line in scan_lines:
        norm = normalize(line)
        has_level = any(kw in norm for kw in LEVEL_KEYWORDS)
        if not language_lines and not has_level:
            continue
        for key, label in LANGUAGE_NAMES.items():
            if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", norm) and not any(
                l["language"] == label for l in languages
            ):
                level = ""
                for kw, lvl in LEVEL_KEYWORDS.items():
                    if kw in norm:
                        level = lvl
                        break
                languages.append({"language": label, "level": level})

    # --- Projets
    projects: list[dict] = []
    for line in sections["projects"]:
        if len(line) >= 8:
            name, _org = _split_title_org(line)
            projects.append({
                "name": name[:80],
                "description": line,
                "skills": taxonomy.find_in_text(line),
            })

    # --- Compte les preuves (expériences/projets mentionnant chaque compétence)
    for skill in skills:
        name = skill["skill"]
        count = sum(1 for e in experiences if name in e["skills"])
        count += sum(1 for p in projects if name in p["skills"])
        skill["evidence_count"] = count
        if count > 0:
            skill["source"] = "evidence"

    career_fields = sorted({s["category"] for s in skills})

    profile = {
        "user_id": 0,
        "summary": "",
        "title": title,
        "location": None,
        "mobility": None,
        "availability": None,
        "education": education,
        "experiences": experiences,
        "certifications": certifications,
        "languages": languages,
        "projects": projects,
        "skills": skills,
        "preferences": {
            "sectors": [], "target_roles": [], "contract_types": [],
            "remote_ok": False,
        },
    }
    report = {
        "skills_found": len(skills),
        "experiences_found": len(experiences),
        "certifications_found": len(certifications),
        "degrees_found": len(education),
        "career_fields": career_fields,
    }
    return profile, report


GENERATED_SECTIONS: list[tuple[str, tuple[str, ...]]] = [
    ("summary", ("resume", "professional summary")),
    (
        "skills",
        (
            "competences", "skills", "core skills", "additional skills",
            "autres competences",
        ),
    ),
    ("experience", ("experience", "professional experience", "experiences")),
    ("projects", ("projets", "projects")),
    ("education", ("formation", "education")),
    ("certifications", ("certifications",)),
    ("languages", ("langues", "languages")),
]

GENERATED_EXPERIENCE_TYPES = {
    "experience professionnelle": "formal",
    "experience informelle": "informal",
    "mission freelance": "freelance",
    "benevolat": "volunteer",
    "stage / apprentissage": "apprenticeship",
    "projet": "project",
}


def _generated_section(line: str) -> str | None:
    """Reconnaît un intitulé de section produit par cv_builder."""
    clean = line.strip()
    if clean.startswith("## "):
        clean = clean[3:].strip()
    norm = normalize(clean)
    if norm.startswith("competences cles pour le poste"):
        return "skills"
    for section, labels in GENERATED_SECTIONS:
        if norm in labels:
            return section
    return None


def _generated_period(text: str) -> tuple[str | None, str | None]:
    """Sépare ``2024-01 à 2025-01`` sans transformer les dates."""
    clean = text.strip()
    if not clean:
        return None, None
    parts = re.split(r"\s+à\s+", clean, maxsplit=1)
    start = parts[0].strip() or None
    end = parts[1].strip() if len(parts) > 1 else None
    if end and normalize(end) in ("present", "aujourd hui", "en cours", "now", "current"):
        end = None
    return start, end


def _generated_skills(text: str) -> list[str]:
    return [
        part.strip()
        for part in re.split(r"\s*,\s*", text or "")
        if part.strip()
    ]


def _generated_skill(line: str) -> tuple[str, str] | None:
    clean = re.sub(r"^[-*]\s*", "", line.strip())
    clean = re.sub(r"^#{1,6}\s*", "", clean)
    bold = re.match(r"^\*\*(.+?)\*\*\s*(?:\(([^()]*)\))?$", clean)
    if bold:
        name, level = bold.group(1).strip(), (bold.group(2) or "").strip()
    else:
        regular = re.match(r"^(.+?)\s*\(([^()]*)\)$", clean)
        if regular:
            name, level = regular.group(1).strip(), regular.group(2).strip()
        else:
            name, level = clean, ""
    if not name:
        return None
    normalized_level = normalize(level)
    level = {
        "avance": "avance", "intermediaire": "intermediaire",
        "debutant": "debutant", "courant": "courant", "natif": "natif",
        "bilingue": "courant", "notions": "debutant",
    }.get(normalized_level, "")
    return name, level


def _generated_skill_items(
    lines: list[str], taxonomy: SkillsTaxonomy,
) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    for line in lines:
        if not line.strip():
            continue
        parsed = _generated_skill(line)
        if not parsed:
            continue
        name, level = parsed
        canonical = taxonomy.canonical(name)
        if normalize(canonical) in seen:
            continue
        seen.add(normalize(canonical))
        items.append({
            "skill": canonical,
            "category": taxonomy.category(canonical),
            "proficiency": level or "intermediaire",
            "source": "declared",
            "evidence_count": 0,
        })
    return items


def _generated_experience(
    header: str,
    meta: str,
    body: list[str],
    taxonomy: SkillsTaxonomy,
    period_text: str | None = None,
) -> dict:
    if " · " in header:
        title, organization = [
            part.strip() for part in header.split(" · ", 1)
        ]
    else:
        title, organization = _split_title_org(header)
    label = ""
    start_date = end_date = None
    if meta:
        clean_meta = meta.strip().strip("*").strip()
        meta_parts = re.split(r"\s+·\s+", clean_meta, maxsplit=1)
        if meta_parts:
            label = meta_parts[0].strip()
        if len(meta_parts) > 1 and not period_text:
            start_date, end_date = _generated_period(meta_parts[1])
    if period_text:
        start_date, end_date = _generated_period(period_text)
    description_lines = []
    skills: list[str] = []
    for line in body:
        clean = line.strip()
        if not clean:
            continue
        if normalize(clean).startswith("competences mobilisees"):
            skills = _generated_skills(clean.split(":", 1)[-1])
        else:
            description_lines.append(clean)
    exp_type = GENERATED_EXPERIENCE_TYPES.get(normalize(label))
    if not exp_type:
        exp_type = _experience_type(" ".join([header, meta, *body]))
    return {
        "title": title,
        "organization": organization,
        "type": exp_type,
        "description": " ".join(description_lines).strip(),
        "start_date": start_date,
        "end_date": end_date,
        "skills": [taxonomy.canonical(s) for s in skills],
    }


def _generated_project(
    name: str, body: list[str], taxonomy: SkillsTaxonomy,
) -> dict:
    description_lines = []
    skills: list[str] = []
    for line in body:
        clean = line.strip()
        if not clean:
            continue
        if normalize(clean).startswith("competences mobilisees"):
            skills = _generated_skills(clean.split(":", 1)[-1])
        else:
            description_lines.append(clean)
    return {
        "name": name.strip(),
        "description": " ".join(description_lines).strip(),
        "skills": [taxonomy.canonical(s) for s in skills],
    }


def _generated_blocks(lines: list[str], heading: str = "### ") -> list[list[str]]:
    """Découpe une section en blocs introduits par ``###`` (ou paragraphes)."""
    blocks: list[list[str]] = []
    current: list[str] = []
    if not heading:
        for line in lines:
            if line.strip():
                current.append(line)
            elif current:
                blocks.append(current)
                current = []
        if current:
            blocks.append(current)
        return blocks

    for line in lines:
        if line.strip().startswith(heading):
            if current:
                blocks.append(current)
            current = [line.strip()[len(heading):].strip()]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def extract_generated_cv_profile(markdown: str) -> tuple[dict, dict] | None:
    """Relit un CV produit par cv_builder sans passer par les heuristiques.

    Les anciens CV de la bibliothèque n'ont pas d'instantané de profil. Leur
    markdown est structuré : on reprend les intitulés, dates, niveaux et
    compétences tels quels. Retourne ``None`` si le document n'est pas
    reconnaissable, afin de ne jamais inventer un profil à partir d'un texte
    ambigu.
    """
    raw_lines = (markdown or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if not raw_lines or not raw_lines[0].startswith("# "):
        return None

    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in raw_lines[1:]:
        section = _generated_section(line) if line.strip() else None
        if section:
            current = section
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line.rstrip())

    if len([key for key in sections if key != "header"]) == 0:
        return None

    taxonomy = load_taxonomy()
    header = sections.get("header") or []
    title = location = availability = None
    for line in header:
        clean = line.strip()
        if not clean:
            continue
        headline = re.match(r"^\*\*(.+?)\*\*\s*(?:·\s*(.+))?$", clean)
        if headline:
            candidate = headline.group(1).strip()
            place = (headline.group(2) or "").strip()
            if candidate and not candidate.startswith("Candidature :") \
                    and candidate != "Profil professionnel":
                title = candidate
            if place and place != "Cameroun":
                location = place
        elif normalize(clean).startswith("disponibilite"):
            availability = clean.split(":", 1)[-1].strip() or None

    summary = " ".join(
        line.strip() for line in sections.get("summary", []) if line.strip()
    ).strip()

    skills = _generated_skill_items(sections.get("skills", []), taxonomy)

    experiences: list[dict] = []
    experience_lines = sections.get("experience", [])
    if any(line.strip().startswith("### ") for line in experience_lines):
        for block in _generated_blocks(experience_lines):
            if not block:
                continue
            header_line = block[0]
            meta = ""
            body = block[1:]
            if body and body[0].strip().startswith("*"):
                meta = body[0].strip()
                body = body[1:]
            experiences.append(
                _generated_experience(header_line, meta, body, taxonomy)
            )
    else:
        for block in _generated_blocks(experience_lines, ""):
            if not block:
                continue
            header_line = block[0].strip()
            body = block[1:]
            period_text = ""
            if body:
                start, end = _generated_period(body[0])
                if start or end:
                    period_text = body[0].strip()
                    body = body[1:]
            experiences.append(
                _generated_experience(
                    header_line, "", body, taxonomy,
                    period_text=period_text or None,
                )
            )

    projects: list[dict] = []
    project_lines = sections.get("projects", [])
    has_project_headings = any(
        line.strip().startswith("### ") for line in project_lines
    )
    for block in _generated_blocks(project_lines, "### " if has_project_headings else ""):
        if not block:
            continue
        projects.append(_generated_project(block[0], block[1:], taxonomy))

    education: list[dict] = []
    for line in sections.get("education", []):
        clean = re.sub(r"^[-*]\s*", "", line.strip())
        if not clean:
            continue
        years = [int(y) for y in re.findall(r"(?:19|20)\d{2}", clean)]
        clean = re.sub(
            r"\s*·\s*(?:19|20)\d{2}(?:\s*à\s*(?:19|20)\d{2})?\s*$",
            "", clean,
        )
        parts = [part.strip() for part in clean.split(" · ")]
        degree = parts[0] if parts else ""
        institution = parts[1] if len(parts) > 1 else ""
        field = ""
        field_match = re.search(r"\(([^()]*)\)\s*$", institution)
        if field_match:
            field = field_match.group(1).strip()
            institution = institution[:field_match.start()].strip()
        if degree:
            education.append({
                "degree": degree,
                "institution": institution,
                "field": field,
                "start_year": years[0] if years else None,
                "end_year": years[1] if len(years) > 1 else None,
            })

    certifications: list[dict] = []
    for line in sections.get("certifications", []):
        clean = re.sub(r"^[-*]\s*", "", line.strip())
        if not clean:
            continue
        year_match = re.search(r"\(((?:19|20)\d{2})\)\s*$", clean)
        year = int(year_match.group(1)) if year_match else None
        if year_match:
            clean = clean[:year_match.start()].strip()
        parts = [part.strip() for part in clean.split(" · ", 1)]
        if parts[0]:
            certifications.append({
                "name": parts[0],
                "issuer": parts[1] if len(parts) > 1 else "",
                "year": year,
            })

    languages: list[dict] = []
    seen_languages: set[str] = set()
    for line in sections.get("languages", []):
        for part in re.split(r"\s*,\s*", line.strip()):
            if not part:
                continue
            language_match = re.match(r"^(.+?)\s*(?:\(([^()]*)\))?$", part)
            if not language_match:
                continue
            language = language_match.group(1).strip()
            level = normalize(language_match.group(2) or "")
            level = {
                "avance": "avance", "intermediaire": "intermediaire",
                "debutant": "debutant", "courant": "courant",
                "natif": "natif", "bilingue": "courant",
            }.get(level, "")
            key = normalize(language)
            if key and key not in seen_languages:
                seen_languages.add(key)
                languages.append({"language": language, "level": level})

    for skill in skills:
        count = sum(1 for item in experiences if skill["skill"] in item["skills"])
        count += sum(1 for item in projects if skill["skill"] in item["skills"])
        skill["evidence_count"] = count
        if count > 0:
            skill["source"] = "evidence"

    profile = {
        "user_id": 0,
        "summary": summary,
        "title": title,
        "location": location,
        "mobility": None,
        "availability": availability,
        "education": education,
        "experiences": experiences,
        "certifications": certifications,
        "languages": languages,
        "projects": projects,
        "skills": skills,
        "preferences": {
            "sectors": [], "target_roles": [], "contract_types": [],
            "remote_ok": False, "linkedin_url": "",
        },
    }
    report = {
        "skills_found": len(skills),
        "experiences_found": len(experiences),
        "certifications_found": len(certifications),
        "degrees_found": len(education),
        "career_fields": sorted({s["category"] for s in skills}),
    }
    return profile, report


def extract_text_from_pdf(data: bytes) -> str:
    """Extraction texte d'un PDF via pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)
