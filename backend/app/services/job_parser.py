"""Parseur d'offres d'emploi « intelligent » (§10, aide à la saisie).

Transforme une brève description libre en offre STRUCTURÉE : intitulé,
localisation, type de contrat, secteur, compétences requises (reconnues
dans la taxonomie). Utilisé par l'assistant, l'espace recruteur et la
console admin. Le brouillon reste à VALIDER par l'humain avant
enregistrement (§47 : pas d'invention — l'extraction ne fait que
reconnaître, et le recruteur corrige).
"""
import re
from typing import Any

from app.services.skills_taxonomy import load_taxonomy

CONTRACT_PATTERNS = [
    ("CDI", r"\bcdi\b|contrat à durée indéterminée"),
    ("CDD", r"\bcdd\b|contrat à durée déterminée"),
    ("Stage", r"\bstage\b|stagiaire"),
    ("Apprentissage", r"\bapprenti\w*\b"),
    ("Freelance", r"\bfreelance\b|\bmission\b"),
]

CAMEROON_CITIES = [
    "Douala", "Yaoundé", "Bafoussam", "Bamenda", "Garoua", "Maroua",
    "Ngaoundéré", "Bertoua", "Buea", "Ebolowa", "Kribi", "Limbe",
    "Kumba", "Foumban", "Dschang", "Nkongsamba", "Edéa", "Bafia",
    "Kousséri", "Mokolo", "Kaélé", "Yagoua", "Guider", "Tiko", "Mbalmayo",
    "Sangmélima", "Abong-Mbang", "Batouri", "Kumbo", "Mbouda", "Dschang",
    "Bangangté", "Bafang", "Tombel", "Mamfe", "Kribi", "Ngaoundal",
]

SECTOR_PATTERNS = [
    ("Informatique / IT", r"\b(informatique|it\b|numérique|développeur|réseau|tech|software|support informatique)"),
    ("Data / Analyse", r"\b(data|données|analyste|statistique)"),
    ("Finance / Comptabilité", r"\b(comptab|financ|banque|fiscal|audit|paie|trésorerie)"),
    ("Marketing / Communication", r"\b(marketing|communication|community|publicité|seo|média)"),
    ("BTP / Construction", r"\b(btp|construction|chantier|bâtiment|génie civil|maçon|architecte)"),
    ("Agriculture / Agribusiness", r"\bagr(iculture|i)\b|agrobusiness|élevage|plantation|cacao|café"),
    ("Santé", r"\b(santé|hopital|hôpital|médical|infirmier|pharmac\w+|clinique)"),
    ("Éducation / Formation", r"\b(école|enseignant|éducation|formation|professeur|instituteur)"),
    ("Logistique / Transport", r"\b(logistique|transport|chauffeur|transit|douane|livraison)"),
    ("Commerce / Vente", r"\b(commerce|vente|vendeur|commercial|boutique|magasin)"),
    ("Hôtellerie / Restauration", r"\b(hôtel|restauration|cuisine|réceptionniste|serveur)"),
    ("Sécurité / Gardiennage", r"\b(sécurité|gardi\w+|vigile|surveillance)"),
    ("Industrie", r"\b(usine|production|industrie|maintenance|mécanicien|électricien|technicien)"),
    ("ONG / International", r"\b(ong|humanitaire|international)"),
]


def parse_job_description(text: str) -> dict[str, Any]:
    """Extrait une offre structurée d'une description libre.

    Règles honnêtes : ne reconnaît que des éléments présents dans le
    texte ; tout le reste reste vide pour correction humaine.
    """
    text = (text or "").strip()
    if not text:
        return {"error": "Description vide"}

    taxonomy = load_taxonomy()
    norm = text.lower()

    # ---- Compétences : détection via la taxonomie (§8)
    found = taxonomy.find_in_text(text)
    # Importance : les compétences citées le plus tôt / répétées = core
    core, preferred = [], []
    seen: set[str] = set()
    for name in found:
        if name in seen:
            continue
        seen.add(name)
        (core if len(core) < 5 else preferred).append(name)

    # ---- Type de contrat
    contract_type = "CDI"
    for value, pattern in CONTRACT_PATTERNS:
        if re.search(pattern, norm):
            contract_type = value
            break

    # ---- Localisation
    location = ""
    for city in CAMEROON_CITIES:
        if re.search(re.escape(city.lower()), norm):
            location = city
            break

    # ---- Secteur
    sector = ""
    for value, pattern in SECTOR_PATTERNS:
        if re.search(pattern, norm):
            sector = value
            break

    # ---- Intitulé du poste : première ligne courte, ou groupe nominal
    # autour d'un mot-clé de fonction.
    first_line = text.splitlines()[0].strip()
    title = first_line if 4 <= len(first_line) <= 80 and not first_line.endswith((".", ":", ";")) else ""
    if not title:
        m = re.search(
            r"(?:poste de|recrutons un|recrute un|recherche un|nous cherchons un|cherche)\s+(?:un |une |des )?([A-Za-zÀ-ÿ' \-]{4,60})",
            text,
            re.IGNORECASE,
        )
        if m:
            title = m.group(1).strip()
            title = re.sub(r"\s+(chez|pour|à)\b.*$", "", title, flags=re.IGNORECASE).strip()
            title = title[:1].upper() + title[1:] if title else ""

    # ---- Entreprise : « chez X », « pour X » ou « Entreprise : X ».
    # Le nom s'arrête aux prépositions et aux villes.
    company = ""
    m = re.search(r"(?:chez|pour(?: le compte de)?)\s+([A-Z][A-Za-zÀ-ÿ0-9&' \-]{2,50})", text)
    if m:
        company = re.split(r"\s+(?:à|au|x)\s+[A-ZÀ-ÿ]", m.group(1).strip())[0].strip()
    m = re.search(r"entreprise\s*:\s*(.+)", norm)
    if m and not company:
        company = m.group(1).strip()[:60].capitalize()

    return {
        "title": title,
        "company": company,
        "location": location,
        "sector": sector,
        "contract_type": contract_type,
        "description": text,
        "requirements": "",
        "salary": "",
        "required_skills": [
            {"name": n, "importance": "core"} for n in core
        ] + [
            {"name": n, "importance": "preferred"} for n in preferred
        ],
        "warning": (
            "Brouillon généré depuis votre description : vérifiez et "
            "complétez chaque champ avant de publier. Rien n'est inventé : "
            "seuls les éléments reconnus sont pré-remplis."
        ),
    }
