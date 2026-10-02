"""Extraction par règles d'un profil structuré depuis un texte de CV (§9ter).

Produit un **brouillon** de profil (jamais enregistré automatiquement) et un
rapport d'extraction. Aucune donnée n'est inventée : seules les informations
présentes dans le texte sont reprises.
"""
import io
import re

from app.services.skills_taxonomy import load_taxonomy, normalize

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
    r"((?:19|20)\d{2})"
    r"\s*(?:[-–/]|\bà\b|\ba\b|\bto\b)\s*"
    r"((?:19|20)\d{2}|pr[eé]sent|aujourd.?hui|en cours|now|present|current)?",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"(19|20)\d{2}")

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
    parts = re.split(r"\s[–—|]\s|\s+-\s+|\s+chez\s+|\s+at\s+", line, maxsplit=1)
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
        current = _detect_section(line, current)
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
            clean = DATE_RANGE_RE.sub("", line).strip(" -–—|,")
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
    for line in experience_lines:
        if len(line) < 8 or line in seen_lines:
            continue
        seen_lines.add(line)
        if line == title or line in sections["education"]:
            continue
        start, end = _extract_years(line)
        title_part, org = _split_title_org(DATE_RANGE_RE.sub("", line).strip(" -–—|,"))
        if len(title_part) < 4:
            continue
        experiences.append({
            "title": title_part,
            "organization": org,
            "type": _experience_type(line),
            "description": line,
            "start_date": start,
            "end_date": end,
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
            "name": line.strip(" -–—"),
            "issuer": "",
            "year": int(year_match.group(0)) if year_match else None,
        })

    # --- Langues (scannées sur tout le texte, niveau détecté sur la ligne)
    languages: list[dict] = []
    for line in lines:
        norm = normalize(line)
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


def extract_text_from_pdf(data: bytes) -> str:
    """Extraction texte d'un PDF via pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)
