"""Business plan et guidance entrepreneuriat (§11bis).

Deux engagements :
- construire un business plan AUCUNEMENT inventé : chaque section
  reprend les données fournies par l'utilisateur et les compétences
  réelles de son profil validé (§47) ;
- guider le jeune sur comment entreprendre dans SON domaine de
  compétence, à partir de son profil réel et des réalités locales.
"""
from typing import Any, Optional

from app.services.skills_taxonomy import load_taxonomy

# Pistes par catégorie de compétences (réalités du marché camerounais,
# présentées comme des opportunités à instruire, jamais comme garanties).
SECTOR_GUIDANCE: dict[str, dict[str, Any]] = {
    "IT": {
        "label": "Numérique",
        "opportunities": [
            "Maintenance et installation informatique pour PME et ménages",
            "Création de sites web et boutiques en ligne pour commerces locaux",
            "Formation de base au numérique (initiation, bureautique)",
            "Cybercafé moderne ou espace de coworking",
        ],
        "steps": [
            "Choisir un créneau précis (ex. maintenance PME) et le tester avec 2 ou 3 clients pilotes.",
            "Formaliser : RCCM, contribuable, compte bancaire dédié.",
            "Investir progressivement en matériel de diagnostic et pièces de rechange.",
            "Documenter chaque intervention : c'est votre preuve d'expérience.",
        ],
    },
    "Agriculture": {
        "label": "Agriculture / Agribusiness",
        "opportunities": [
            "Production maraîchère de proximité (villes : demande stable)",
            "Transformation agroalimentaire (farines, jus, séchage)",
            "Élevage de petits ruminants ou volaille",
            "Services agricoles (labour, traitement, conseil)",
        ],
        "steps": [
            "Viser une filière avec débouché local clair (marchés urbains).",
            "Commencer petit et mutualiser matériel (GIC ou coopérative).",
            "Structurer la commercialisation : contrats avec restaurants, boutiques.",
            "Tenir un cahier de production : coûts, rendements, clients.",
        ],
    },
    "Commerce / Vente": {
        "label": "Commerce",
        "opportunities": [
            "Revente spécialisée dans un produit maîtrisé",
            "Import-distribution régionale",
            "Commerce en ligne avec livraison locale",
        ],
        "steps": [
            "Choisir une niche que vous connaissez (vos compétences priment).",
            "Négocier un fournisseur fiable avant de louer un local.",
            "Limiter le stock initial et réinvestir les bénéfices.",
        ],
    },
    "BTP": {
        "label": "BTP",
        "opportunities": [
            "Petits travaux et finitions (carrelage, peinture, plomberie)",
            "Équipe de manœuvres spécialisée pour chantiers",
            "Location de petit matériel",
        ],
        "steps": [
            "Constituer une petite équipe complémentaire (maçon + plombier + électricien).",
            "Réaliser des chantiers pilotes et photographier vos travaux.",
            "Travailler d'abord en sous-traitance avec les entreprises locales.",
        ],
    },
    "Services": {
        "label": "Services",
        "opportunities": [
            "Services à la demande : couture, coiffure, réparation à domicile",
            "Gardiennage et nettoyage professionnel",
            "Livraison et messagerie urbaine",
        ],
        "steps": [
            "Standardiser votre offre (tarifs clairs, délais).",
            "Communiquer via les canaux que vos clients utilisent réellement.",
            "Demander des recommandations après chaque prestation.",
        ],
    },
}

DEFAULT_GUIDANCE = SECTOR_GUIDANCE["Services"]


def _match_category(profile: Optional[dict], taxonomy) -> Optional[str]:
    """Catégorie entrepreneuriat correspondant au profil (catégorie la
    plus fréquente des compétences)."""
    if not profile:
        return None
    counter: dict[str, int] = {}
    for s in profile.get("skills", []):
        cat = (s.get("category") or "").strip().lower()
        if cat in ("it", "data") or "informatique" in cat or "numéri" in cat:
            counter["IT"] = counter.get("IT", 0) + 2
        elif "agri" in cat:
            counter["Agriculture"] = counter.get("Agriculture", 0) + 2
        elif cat in ("marketing", "business") or "commerce" in cat or "vente" in cat:
            counter["Commerce / Vente"] = counter.get("Commerce / Vente", 0) + 2
        elif cat == "btp" or "construction" in cat or "génie" in cat:
            counter["BTP"] = counter.get("BTP", 0) + 2
        elif cat:  # logistique, santé, éducation, soft skills…
            counter["Services"] = counter.get("Services", 0) + 1
    if not counter:
        return None
    return max(counter.items(), key=lambda kv: kv[1])[0]


def guidance_for(profile: Optional[dict], taxonomy) -> dict[str, Any]:
    """« Comment entreprendre dans mon domaine » : ancré sur le profil."""
    if not profile:
        return {
            "category": None,
            "introduction": (
                "Construisez d'abord votre profil : la guidance s'appuie sur "
                "VOS compétences réelles pour proposer des pistes pertinentes."
            ),
            "opportunities": [],
            "steps": [],
        }
    category = _match_category(profile, taxonomy)
    data = SECTOR_GUIDANCE.get(category, DEFAULT_GUIDANCE)
    skills = [s["skill"] for s in profile.get("skills", [])][:6]
    intro = (
        f"D'après votre profil ({profile.get('title') or 'compétences multiples'}), "
        f"votre domaine d'atout naturel est : {data['label']}. "
        + (f"Vos compétences ({', '.join(skills)}) y sont directement mobilisables. " if skills else "")
        + "Voici des pistes concrètes : à instruire, jamais garanties."
    )
    return {
        "category": category,
        "category_label": data["label"],
        "introduction": intro,
        "opportunities": data["opportunities"],
        "steps": data["steps"],
    }


def build_business_plan(
    user: Any,
    profile: Optional[dict],
    form: dict[str, Any],
    taxonomy,
) -> str:
    """Génère un business plan markdown depuis le formulaire ET le profil
    validé. Aucune donnée inventée : chaque chiffre vient du porteur."""
    activity = (form.get("activity") or "").strip()
    target = (form.get("target") or "").strip()
    capital = (form.get("capital") or "").strip()
    location = (form.get("location") or (profile or {}).get("location") or "Cameroun").strip()

    skills = [s["skill"] for s in (profile or {}).get("skills", [])][:8]
    experiences = (profile or {}).get("experiences", [])[:3]

    lines: list[str] = []
    lines.append("# Business plan : " + (activity or "Projet à préciser"))
    lines.append("")
    lines.append(f"**Porteur du projet** : {user.full_name}")
    if (profile or {}).get("title"):
        lines.append(f"**Profil professionnel** : {profile['title']}")
    lines.append(f"**Localisation visée** : {location}")
    if capital:
        lines.append(f"**Capital de départ déclaré** : {capital}")
    lines.append(f"**Date d'édition** : document généré par OrientSkill AI")
    lines.append("")

    lines.append("## 1. Résumé du projet")
    if activity:
        lines.append(f"Activité : {activity}.")
    if target:
        lines.append(f"Clientèle visée : {target}.")
    lines.append(
        "Ce business plan reprend uniquement les informations fournies et "
        "les éléments vérifiables du profil du porteur : à compléter avec "
        "une étude de marché terrain avant tout dépôt bancaire."
    )
    lines.append("")

    lines.append("## 2. Atouts du porteur (issus du profil validé)")
    if skills:
        lines.append("Compétences mobilisables : " + ", ".join(skills) + ".")
    if experiences:
        lines.append("Expériences pertinentes :")
        for e in experiences:
            label = e.get("title") or "Expérience"
            org = e.get("organization") or ""
            lines.append(f"- {label}" + (f" · {org}" if org else ""))
    if not skills and not experiences:
        lines.append(
            "Aucune compétence enregistrée pour l'instant : complétez votre "
            "profil OrientSkill, il constitue votre preuve d'expérience."
        )
    lines.append("")

    lines.append("## 3. Marché")
    if target:
        lines.append(f"Clientèle cible déclarée : {target}.")
    lines.append(
        "À instruire : taille du marché local, concurrence identifiée sur "
        "le terrain, prix pratiqués par les concurrents, saisonnalité."
    )
    lines.append("")

    lines.append("## 4. Plan financier à construire")
    lines.append("Rassemblez et chiffrez :")
    lines.append("- Investissement de départ (matériel, local, formalités)")
    lines.append("- Coûts mensuels récurrents (achats, loyer, transport, communication)")
    lines.append("- Chiffre d'affaires prévisionnel prudent (3 scénarios : faible, moyen, élevé)")
    lines.append("- Point mort : chiffre d'affaires minimum pour couvrir les charges")
    if capital:
        lines.append(f"Capital disponible déclaré : {capital}. Planifiez son usage ligne par ligne.")
    lines.append("")

    lines.append("## 5. Checklist avant la banque")
    for item in (
        "Statut juridique (RCCM, contribuable) à jour",
        "Compte bancaire dédié à l'activité",
        "Business plan chiffré et cohérent",
        "Garanties et apport personnel identifiés",
        "Expérience du porteur documentée (profil OrientSkill à jour)",
    ):
        lines.append(f"- {item}")
    lines.append("")
    lines.append(
        "*Document généré par OrientSkill AI à partir des données fournies "
        "par le porteur. Aucune promesse de financement : la décision "
        "appartient à l'institution sollicitée.*"
    )
    return "\n".join(lines)
