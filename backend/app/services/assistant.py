"""Assistant conversationnel hybride (§26).

Principes :
- Réponses ancrées UNIQUEMENT sur les données réelles : profil, offres,
  métiers, tendances. Jamais d'invention (§47).
- Suggestions DYNAMIQUES : calculées depuis l'état réel du profil et du
  marché (métier le plus proche, principal écart, meilleure offre,
  entretiens en cours), pas des listes pré-écrites.
- Si un LLM est configuré (paramètres admin, cf. llm_client), la réponse
  est générée par le modèle avec le contexte ; sinon moteur de règles.
"""
import re
import urllib.parse
import urllib.request
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services import llm_client
from app.services import cv_builder
from app.services.applications import CLOSED_STATUSES, STATUS_LABELS as APPLICATION_LABELS
from app.services.market import market_trends
from app.services.matching import compute_match
from app.services.orientation import match_career
from app.services.skills_taxonomy import normalize


# Aide contextuelle quand l'agent est ouvert depuis une page précise et
# que la demande reste vague : chaque page a son angle d'attaque réel.
_PAGE_HINTS = {
    "entrepreneuriat": (
        "Ici, sur Entrepreneuriat, on peut travailler ton projet pour de "
        "vrai : clarifier ton offre, vérifier ton modèle économique, ou "
        "identifier un financement adapté parmi ceux du référentiel. Dis-moi "
        "où en est ton projet, je pars de là."
    ),
    "offres": (
        "Tu es sur les offres : dis-moi le poste ou la ville qui t'intéresse, "
        "je te sors les offres réelles qui collent à ton profil et j'explique "
        "les écarts."
    ),
    "candidatures": (
        "Tu es sur tes candidatures : on peut préparer un entretien, relire "
        "une candidature ou décider d'une relance, à partir de ce que tu as "
        "réellement envoyé."
    ),
    "documents": (
        "Tu es sur tes documents : je peux t'aider à choisir le bon modèle et "
        "à adapter un CV ou une lettre à une offre précise, sans rien inventer."
    ),
    "competences": (
        "Tu es sur tes compétences : on peut cibler celles qui manquent le "
        "plus dans les offres de ton domaine et trouver une ressource réelle "
        "pour les monter."
    ),
    "formations": (
        "Tu es sur les formations : dis-moi la compétence à travailler, je te "
        "relie à une ressource réelle du référentiel."
    ),
    "carriere": (
        "Tu es sur les métiers : je peux t'expliquer les passerelles "
        "réalistes depuis ton profil et les compétences à combler."
    ),
    "profil": (
        "Tu es sur ton profil : on peut compléter ce qui bloque réellement les "
        "recruteurs et rendre ton dossier plus lisible."
    ),
}


def _find_job_by_mention(ctx, message: str):
    """Offre mentionnée dans la question (titre complet ou fragment entre
    guillemets). Aucune invention : on ne cite que des offres réelles."""
    text = message.lower()
    for job in ctx.jobs:
        title = (job.title or "").lower()
        if len(title) >= 6 and title in text:
            return job
    m = re.search(r"[«\u201c]([^»\u201d]{4,})[»\u201d]", message)
    if m:
        frag = m.group(1).strip().lower()
        for job in ctx.jobs:
            if frag and frag in (job.title or "").lower():
                return job
    return None


def _learning_href(resource: dict) -> str:
    """Lien profond vers la fiche exacte d'une formation dans Learning."""
    key = resource.get("key")
    return f"/learning/{key}" if key else "/learning"


def _top_matches(profile_skills: list[dict], jobs: list[Any], taxonomy, n: int = 3):
    scored = [
        (job, compute_match(profile_skills, job.required_skills, taxonomy))
        for job in jobs
    ]
    scored.sort(key=lambda t: t[1]["score"], reverse=True)
    return scored[:n]


def _top_careers(profile_skills: list[dict], careers: list[Any], taxonomy, n: int = 3):
    scored = [(c, match_career(profile_skills, c, taxonomy)) for c in careers]
    scored.sort(key=lambda t: t[1]["score"], reverse=True)
    return scored[:n]


def _priority_gaps(profile_skills: list[dict], jobs: list[Any], careers: list[Any], taxonomy) -> list[str]:
    """Écarts PRIORITAIRES, orientés métiers : d'abord les compétences
    manquantes des métiers qui correspondent au profil (§9bis), ensuite
    celles des meilleures offres. Fini les recommandations hors-domaine
    (plus de « Excel » pour un technicien réseau)."""
    gaps: list[str] = []
    seen: set[str] = set()

    for career, _m in _top_careers(profile_skills, careers, taxonomy, n=3):
        for name in _career_missing(profile_skills, career, taxonomy):
            if name not in seen:
                seen.add(name)
                gaps.append(name)
    for job, match in _top_matches(profile_skills, jobs, taxonomy, n=5):
        for name in match["missing"]:
            if name not in seen:
                seen.add(name)
                gaps.append(name)
    return gaps[:8]


def _career_missing(profile_skills: list[dict], career: Any, taxonomy) -> list[str]:
    """Compétences du métier absentes du profil (mêmes règles que matching)."""
    from app.services.orientation import match_career

    return match_career(profile_skills, career, taxonomy)["missing"]


def _cv_completion_notes(profile: dict) -> list[str]:
    """Ce qui rend un CV « vide », détecté depuis le profil réel. On
    propose d'AJOUTER des faits vrais, jamais d'en inventer (§47, §5bis)."""
    notes = []
    if not (profile.get("experiences") or []):
        notes.append(
            "aucune expérience enregistrée : ajoutez même les expériences "
            "informelles (aide familiale, petit commerce, bénévolat) : elles "
            "comptent dans le CV et le matching (§5bis)"
        )
    if len(profile.get("skills") or []) < 5:
        notes.append(
            "peu de compétences listées : le questionnaire en capte d'autres "
            "que vous n'avez peut-être pas pensé à mentionner"
        )
    if not (profile.get("education") or []):
        notes.append(
            "formation absente : ajoutez-la, même si le parcours n'est pas terminé"
        )
    if not profile.get("summary"):
        notes.append("pas de résumé de profil : il devient l'accroche du CV")
    if not (profile.get("certifications") or []):
        notes.append(
            "aucune certification : ajoutez celles en cours ou préparez-en une "
            "avec les formations suivies"
        )
    return notes[:3]


def _entrepreneur_guidance(profile, taxonomy) -> dict:
    """Pistes « comment entreprendre dans MON domaine » (§11bis)."""
    from app.services.business_plan import guidance_for

    return guidance_for(profile, taxonomy)


# ------------------------------------------------- recherche web

_SEARCH_TRIGGERS = re.compile(
    r"\b(cherche|recherche|trouve|renseigne(?:[- ]toi)?|actualit[ée]s?|"
    r"sur internet|sur le net|des infos? sur|des informations sur|"
    r"qu'est[- ]ce que c'est|c'est quoi)\b",
    re.IGNORECASE,
)

_STOPWORDS = re.compile(
    r"\b(moi|je|tu|il|elle|on|nous|vous|peux|pourrais|pourra[sz]?|stp|"
    r"svp|s'il|te|pla[îi]t|fouille|internet|net|le|la|les|un|une|des|"
    r"sur|de|du|d'|que|quelles?|qui|est|sont|pour|rien|y|a|ya|dispo|"
    r"disponibles?|quoi|trucs?|choses?|toujours|encore)\b",
    re.IGNORECASE,
)


def _detect_search(message: str) -> "str | None":
    """Requête de recherche si l'utilisateur demande explicitement à
    fouiller le web (ou une actualité/information externe)."""
    if not _SEARCH_TRIGGERS.search(message):
        return None
    query = _SEARCH_TRIGGERS.sub(" ", message)
    query = _STOPWORDS.sub(" ", query)
    query = re.sub(r"[?!.;,]", " ", query)
    query = re.sub(r"\s+", " ", query).strip()
    return query[:120] if len(query) >= 8 else None


def _web_search(query: str) -> list[dict]:
    """Recherche web bornée via l'interface HTML publique de DuckDuckGo
    (sans clé API) : 1 requête, timeout 10 s, 4 résultats maximum.
    Retourne [{title, url, snippet}] : liste vide si échec."""
    try:
        url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (OrientSkillAI/2.0)"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            html = response.read(150_000).decode("utf-8", errors="ignore")
    except Exception:
        return []

    results = []
    blocks = re.findall(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    )
    snippets = re.findall(
        r'class="result__snippet"[^>]*>(.*?)</a>',
        html, re.DOTALL,
    )
    for i, (raw_href, raw_title) in enumerate(blocks[:4]):
        href = raw_href
        m = re.search(r"uddg=([^&]+)", href)
        if m:
            href = urllib.parse.unquote(m.group(1))
        if not href.startswith("http"):
            continue
        title = re.sub(r"<[^>]+>", "", raw_title).strip()
        snippet = ""
        if i < len(snippets):
            snippet = re.sub(r"<[^>]+>", " ", snippets[i])
            snippet = re.sub(r"\s+", " ", snippet).strip()[:200]
        results.append({"title": title, "url": href, "snippet": snippet})
    return results


def _detect_search_from_history(history: list[dict[str, str]]) -> "str | None":
    """« Et sur internet, il y a rien ? » : la recherche porte sur le
    sujet de la question précédente. On relit l'historique récent."""
    previous_user = [m["content"] for m in history[-4:] if m.get("role") == "user"]
    if not previous_user:
        return None
    query = previous_user[-1]
    query = re.sub(r"[?!.;,]", " ", query)
    query = _STOPWORDS.sub(" ", query)
    query = re.sub(r"\s+", " ", query).strip()
    return query[:120] if len(query) >= 8 else None


class _Context:
    """État réel du jeune, calculé une fois par requête pour ancrer
    réponses ET suggestions. Sert aussi à construire le document de
    contexte transmis au LLM (les pouvoirs de l'agent : données vivantes)."""

    def __init__(self, profile, jobs, careers, taxonomy, resources=None, role="candidate",
                 applications=None, verified=False, web_results=None,
                 entrepreneur_resources=None, financing=None, enrollments=None,
                 documents=None, agent_mode="preparation", user=None,
                 page_context=None):
        self.profile = profile
        self.skills = profile.get("skills", []) if profile else []
        self.jobs = jobs
        self.careers = careers
        self.taxonomy = taxonomy
        self.resources = resources or {}
        self.role = role
        self.applications = applications or []
        self.enrollments = enrollments or []
        self.documents = documents or []
        self.agent_mode = agent_mode or "preparation"
        self.user = user
        self.page_context = (page_context or "").strip()[:120]
        self.verified = verified
        self.web_results = web_results or []
        self.entrepreneur_resources = entrepreneur_resources or []
        self.financing = financing or []
        self._entrepreneur: Optional[dict] = None
        self.best_match = _top_matches(self.skills, jobs, taxonomy, n=1)[0] if (profile and jobs) else None
        self.top_career = _top_careers(self.skills, careers, taxonomy, n=1)[0] if (profile and careers) else None
        self.gaps = _priority_gaps(self.skills, jobs, careers, taxonomy) if profile else []
        self.trends = market_trends(jobs)

    def resources_for(self, skill: str) -> list[dict]:
        """Ressources réelles (titre + URL) pour une compétence."""
        return self.resources.get(skill, [])

    def first_resource_for(self, skill: str) -> Optional[dict]:
        rows = self.resources_for(skill)
        return rows[0] if rows else None

    def has_document(self, kind: str, job_id: Optional[int] = None) -> bool:
        for doc in self.documents:
            if doc.get("kind") != kind:
                continue
            if job_id is None or doc.get("job_id") == job_id:
                return True
        return False

    def next_action(self) -> dict:
        """Action la plus utile maintenant, calculée depuis les données réelles.

        L'agent ne déclenche rien seul : il propose une action cliquable,
        le candidat garde la décision.
        """
        if not self.profile:
            return {
                "label": "Créer votre profil pour débloquer les recommandations",
                "type": "build_profile",
                "href": "/profile",
            }
        applied_ids = {a.get("job_id") for a in self.applications}
        interview = next(
            (a for a in self.applications if a.get("status") == "entretien"), None
        )
        if interview:
            return {
                "label": f"Préparer l'entretien pour « {interview.get('job_title')} »",
                "type": "prepare_interview",
                "job_id": interview.get("job_id"),
                "href": f"/jobs/{interview.get('job_id')}",
            }
        prepared = next(
            (a for a in self.applications if a.get("status") == "cv_prepare"), None
        )
        if prepared:
            return {
                "label": f"Valider la candidature préparée pour « {prepared.get('job_title')} »",
                "type": "review_application",
                "job_id": prepared.get("job_id"),
                "href": "/applications",
            }
        if self.best_match:
            job, match = self.best_match
            if match["score"] >= 75 and job.id not in applied_ids:
                return {
                    "label": f"Adapter votre CV pour « {job.title} » chez {job.company}",
                    "type": "adapt_cv",
                    "job_id": job.id,
                    "href": f"/jobs/{job.id}",
                }
        if self.gaps:
            skill = self.gaps[0]
            resource = self.first_resource_for(skill)
            return {
                "label": f"Développer « {skill} », demandée par le marché",
                "type": "learn",
                "skill": skill,
                "href": _learning_href(resource) if resource else "/learning",
            }
        if self.best_match:
            job, _match = self.best_match
            return {
                "label": f"Candidater à « {job.title} » chez {job.company}",
                "type": "apply",
                "job_id": job.id,
                "href": f"/jobs/{job.id}",
            }
        return {
            "label": "Explorer les offres correspondant à votre profil",
            "type": "explore",
            "href": "/jobs",
        }

    def entrepreneur(self) -> dict:
        """Lecture entrepreneuriale du profil (§11bis), calculée à la
        demande : compétences du référentiel couvertes / partielles /
        manquantes, d'après NOTRE taxonomie."""
        if self._entrepreneur is None:
            from app.services.entrepreneurship import entrepreneur_profile

            self._entrepreneur = entrepreneur_profile(self.profile, self.taxonomy)
        return self._entrepreneur

    def context_document(self) -> str:
        """Document de contexte complet pour le LLM : tout ce que l'agent
        sait, avec les liens EXACTS à citer. Le LLM n'invente rien, il
        puise ici (§47 : ancrage sur données réelles)."""
        parts: list[str] = []

        if self.user is not None:
            full_name = (getattr(self.user, "full_name", "") or "").strip()
            if full_name:
                parts.append("IDENTITÉ DE L'UTILISATEUR : " + full_name)

        if self.profile:
            identity = [
                self.profile.get("title") or "sans titre",
                self.profile.get("location") or "",
            ]
            parts.append("PROFIL : " + " · ".join(filter(None, identity))
                         + (" · identité vérifiée" if self.verified else ""))
            if self.profile.get("summary"):
                parts.append("RÉSUMÉ DU PROFIL : " + self.profile["summary"])
            skills_line = ", ".join(
                f"{s['skill']} ({s.get('proficiency', '')})"
                for s in self.skills[:10]
            )
            if skills_line:
                parts.append("COMPÉTENCES DU PROFIL : " + skills_line)
            experiences = self.profile.get("experiences") or []
            if experiences:
                exp_lines = []
                for exp in experiences[:5]:
                    label = exp.get("title") or exp.get("role") or "expérience"
                    org = exp.get("company") or exp.get("organization") or ""
                    kind = exp.get("type") or ""
                    exp_lines.append(
                        f"{label}" + (f" chez {org}" if org else "")
                        + (f" ({kind})" if kind else "")
                    )
                parts.append("EXPÉRIENCES : " + " ; ".join(exp_lines))
            education = self.profile.get("education") or []
            if education:
                edu_lines = []
                for edu in education[:4]:
                    label = edu.get("title") or edu.get("degree") or "formation"
                    org = edu.get("school") or edu.get("institution") or ""
                    edu_lines.append(label + (f" · {org}" if org else ""))
                parts.append("FORMATION : " + " ; ".join(edu_lines))
            certifications = self.profile.get("certifications") or []
            if certifications:
                parts.append("CERTIFICATIONS : " + " ; ".join(
                    c.get("name", "") for c in certifications[:5]
                ))

        # Métiers recommandés (orientation §9bis)
        for career, m in _top_careers(self.skills, self.careers, self.taxonomy, n=3):
            parts.append(
                f"MÉTIER RECOMMANDÉ : « {career.title} » (score {m['score']}/100, "
                f"accessibilité {m['accessibility']})"
                + (f" · manques : {', '.join(_career_missing(self.skills, career, self.taxonomy)[:4])}"
                   if self.skills else "")
            )

        # Meilleures offres
        for job, m in _top_matches(self.skills, self.jobs, self.taxonomy, n=3):
            parts.append(
                f"OFFRE : « {job.title} » chez {job.company} ({job.location}, "
                f"{job.contract_type}) · correspondance {m['score']}/100"
            )

        # Écarts prioritaires orientés métiers
        if self.gaps:
            parts.append("ÉCARTS PRIORITAIRES (par rapport à vos métiers visés) : "
                         + ", ".join(self.gaps[:5]))

        # Entrepreneuriat (§11bis) : domaine, pistes et compétences réelles
        if self.profile:
            guidance = _entrepreneur_guidance(self.profile, self.taxonomy)
            if guidance.get("category_label"):
                parts.append(
                    "ENTREPRENEURIAT : domaine d'atout « "
                    + guidance["category_label"] + " » · pistes : "
                    + " ; ".join(guidance.get("opportunities", [])[:4])
                )
            ent = self.entrepreneur()
            couvertes = [
                i["name"] for g in ent["groups"] for i in g["items"]
                if i["state"] != "missing"
            ]
            parts.append(
                f"COMPÉTENCES ENTREPRENEURIALES ({ent['covered_count']}/{ent['total']} "
                "couvertes, référentiel issu de la taxonomie) : "
                + (", ".join(couvertes) if couvertes else "aucune pour l'instant")
            )
        if self.financing:
            parts.append(
                "FINANCEMENTS RÉPERTORIÉS (ne pas en inventer d'autres) : "
                + " ; ".join(f"{f['name']} ({f['type']})" for f in self.financing[:5])
            )
        if self.entrepreneur_resources:
            parts.append(
                "PROGRAMMES ENTREPRENEURIAUX RÉPERTORIÉS : "
                + " ; ".join(r["title"] for r in self.entrepreneur_resources[:6])
                + " · page : /entrepreneurship"
            )

        # Formations disponibles : liens EXACTS à recopier dans la réponse
        formation_lines = []
        for skill in self.gaps[:4]:
            for r in self.resources_for(skill)[:2]:
                fiche = _learning_href(r)
                if r.get("url"):
                    nature = r.get("link_kind_label") or "Lien"
                    formation_lines.append(
                        f"[{r['title']}]({r['url']}) · {r['provider']} "
                        f"(lien : {nature}) · fiche OrientSkill : {fiche} "
                        f"[compétence : {skill}]"
                    )
                else:
                    formation_lines.append(
                        f"{r['title']} · {r['provider']} (sans lien : "
                        f"{r.get('link_kind_label') or 'formation sur place'}) "
                        f"· fiche OrientSkill : {fiche} [compétence : {skill}]"
                    )
        if formation_lines:
            parts.append(
                "FORMATIONS DISPONIBLES (cite ces liens markdown EXACTEMENT, "
                "sans en inventer d'autres ; précise la nature du lien quand "
                "ce n'est pas la formation exacte) :\n" + "\n".join(formation_lines)
            )

        # Formations réellement suivies par le jeune (suivi + preuves)
        if self.enrollments:
            suivies = []
            for e in self.enrollments[:6]:
                état = e.get("status_label", "?")
                if e.get("verifiable"):
                    état += ", preuve fournie"
                if e.get("added_to_profile"):
                    état += ", rattachée au profil"
                suivies.append(f"« {e.get('title', '?')} » ({e.get('provider') or 'fournisseur non précisé'}) · {e.get('skill', '?')} · {état}")
            parts.append(
                "FORMATIONS SUIVIES PAR LE JEUNE (données réelles, ne pas en "
                "inventer) : " + " ; ".join(suivies)
            )

        # Candidatures
        if self.applications:
            parts.append("CANDIDATURES : " + " ; ".join(
                f"{a.get('job_title', '?')} → {a.get('status', '?')}"
                for a in self.applications[:5]
            ))

        # Prochaine action réelle et documents déjà produits
        action = self.next_action()
        parts.append(
            f"PROCHAINE ACTION PRIORITAIRE : {action.get('label', '?')} "
            f"· lien interne : {action.get('href', '/dashboard')}"
        )
        if self.documents:
            docs = " ; ".join(
                f"{'CV' if d.get('kind') == 'cv' else 'Lettre'} « {d.get('title', '?')} »"
                + (f" (offre {d.get('job_id')})" if d.get("job_id") else "")
                for d in self.documents[:5]
            )
            parts.append("DOCUMENTS DÉJÀ GÉNÉRÉS (ne pas prétendre qu'ils n'existent pas) : " + docs)
        parts.append(
            "MODE DE L'AGENT : " + self.agent_mode
            + " · l'agent prépare, le candidat valide toujours avant envoi."
        )

        # Résultats de recherche web (fraîchement collectés, citables)
        if self.web_results:
            lines = [
                f"[{r['title']}]({r['url']})"
                + (f" · {r['snippet']}" if r.get("snippet") else "")
                for r in self.web_results
            ]
            parts.append(
                "RÉSULTATS WEB (recherche fraîche, cite ces liens si "
                "pertinents) :\n" + "\n".join(lines)
            )

        # Tendances marché
        if self.trends.get("top_skills"):
            parts.append("TENDANCES MARCHÉ : " + ", ".join(
                f"{s['name']} ({s['count']})" for s in self.trends["top_skills"][:5]
            ))
        return "\n\n".join(parts)


def dynamic_suggestions(ctx: _Context) -> list[str]:
    """Suggestions de suivi calculées (aucune liste pré-écrite)."""
    if ctx.role == "recruiter":
        return [
            "Publie une offre depuis une description",
            "Montre-moi les talents disponibles en réseaux",
            "Où en sont les candidatures reçues ?",
            "Comment rédiger une offre claire ?",
        ]
    if ctx.role == "admin":
        return [
            "Où en sont les vérifications de profil ?",
            "Publie une offre depuis une description",
            "Quelles sont les tendances du marché ?",
        ]
    if ctx.profile is None:
        base = ["Comment créer mon profil sans CV ?", "Quelles sont les tendances du marché ?"]
        return base
    out: list[str] = []
    if ctx.top_career:
        out.append(f"Pourquoi me recommandes-tu « {ctx.top_career[0].title} » ?")
    if ctx.best_match:
        out.append(f"Prépare mon CV pour « {ctx.best_match[0].title} »")
    if ctx.gaps:
        out.append(f"Quelles formations suivre pour {ctx.gaps[0]} ?")
    out.insert(0, "Que dois-je faire maintenant ?")
    if not out[1:]:
        out.append("Montre-moi les offres les plus récentes.")
    out.append("Où en sont mes candidatures ?")
    return out[:4]


def _summarize_url(url: str) -> str:
    """Accès internet borné : lit UNE page fournie par l'utilisateur
    (timeout 10 s, 200 Ko max), en extrait le balisage standard et en
    fait un résumé honnête. Aucune navigation automatisée."""
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (OrientSkillAI/2.0)"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            html = response.read(200_000).decode("utf-8", errors="ignore")
    except Exception as exc:
        return (
            f"Je n'ai pas pu ouvrir cette page ({str(exc)[:60]}). Je travaille "
            "sinon sur les données de la plateforme ; vous pouvez aussi "
            " importer cette offre manuellement depuis l'espace concerné."
        )

    # JSON-LD JobPosting (la plupart des pages d'offres)
    import json as _json

    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = _json.loads(match.group(1).strip())
        except _json.JSONDecodeError:
            continue
        for node in (data if isinstance(data, list) else [data]):
            if isinstance(node, dict) and "jobposting" in str(node.get("@type", "")).lower():
                org = node.get("hiringOrganization") or {}
                title = node.get("title") or "offre"
                company = org.get("name", "") if isinstance(org, dict) else str(org)
                return (
                    f"Voici ce que je lis sur cette page d'offre :\n\n"
                    f"- **Poste** : {title}\n"
                    f"- **Entreprise** : {company or 'non précisée'}\n\n"
                    f"Le contenu complet est sur la page. Un administrateur ou "
                    f"recruteur peut l'importer proprement via l'import par URL."
                )

    # Repli : title / meta description
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    desc = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']{10,400})["\']',
        html, re.IGNORECASE,
    )
    if title or desc:
        parts = ["Voici ce que je lis sur cette page :"]
        if title:
            clean = re.sub(r"<[^>]+>", " ", title.group(1)).strip()
            parts.append(f"- **Titre** : {clean[:120]}")
        if desc:
            parts.append(f"- **Contenu** : {desc.group(1).strip()[:250]}")
        return "\n".join(parts)
    return (
        "Page ouverte, mais sans balisage exploitable. Si c'est une offre, "
        "collez plutôt sa description : je l'analyserai (compétences, "
        "correspondance avec votre profil)."
    )


def _rules_reply(message: str, ctx: _Context) -> dict[str, Any]:
    """Moteur par règles : réponses fondées sur les données réelles."""
    norm = normalize(message)
    links: list[dict[str, str]] = []

    def no_profile_reply() -> str | None:
        if ctx.profile is None:
            return (
                "Je vois que ton profil n'est pas encore complet, pas de "
                "souci : on le construit ensemble. Pas besoin d'un CV tout "
                "fait, la plateforme le fabrique avec toi, question par "
                "question, et tu valides chaque étape. En attendant, je "
                "peux te parler du marché ou des offres du moment."
            )
        return None

    def follow_ups(*items: str) -> list[str]:
        """Suggestions de suivi : items contextuels + base dynamique."""
        seen = list(items)
        for s in dynamic_suggestions(ctx):
            if s not in seen and len(seen) < 4:
                seen.append(s)
        return seen[:4]

    # ---- Résultats de recherche web (collectés dans answer())
    if ctx.web_results:
        lines = ["Voilà ce que j'ai trouvé sur le web :"]
        for r in ctx.web_results[:3]:
            line = f"- [{r['title']}]({r['url']})"
            if r.get("snippet"):
                line += f" · {r['snippet'][:120]}"
            lines.append(line)
        links = [{"label": r["title"][:40], "href": r["url"]}
                 for r in ctx.web_results[:3]]
        return {
            "reply": "\n".join(lines),
            "suggestions": dynamic_suggestions(ctx),
            "links": links,
        }

    # ---- Analyse d'une page web (accès internet BORNÉ : une seule page,
    # fournie par l'utilisateur : jamais de collecte de masse)
    url_match = re.search(r"https?://[^\s]+", message)
    if url_match and not re.search(r"linkedin", norm):
        url = url_match.group(0).rstrip(".,;)")
        reply = _summarize_url(url)
        if reply:
            return {
                "reply": reply,
                "suggestions": dynamic_suggestions(ctx),
                "links": [
                    {"label": "Ouvrir la page", "href": url},
                    {"label": "Voir les offres similaires", "href": "/jobs"},
                ],
            }

    # ---- Agent recruteur : talents, candidatures reçues, offres
    if ctx.role == "recruiter":
        if re.search(r"(candidatures? recues?|mes candidatures|qui a postul|postule|postule)", norm):
            return {
                "reply": (
                    "Toutes les candidatures reçues sur tes offres sont "
                    "sur ton espace : tu peux faire avancer le statut "
                    "(partagé avec le candidat, avec notification "
                    "automatique) ou contacter directement par messagerie."
                ),
                "suggestions": dynamic_suggestions(ctx),
                "links": [
                    {"label": "Mon espace recruteur", "href": "/recruiter"},
                    {"label": "Candidatures reçues", "href": "/recruiter"},
                ],
            }
        if re.search(r"(talent|candidat|profil|cherche des (gens|gens à)|cv|recrute quelqu|embauche)", norm):
            skills = ctx.taxonomy.find_in_text(message)[:5]
            if skills:
                query = ",".join(skills)
                return {
                    "reply": (
                        "Je repère dans ta demande : " + ", ".join(skills)
                        + ". Lance la recherche de talents avec ces compétences "
                        " : le matching est expliqué (couvertes, partielles, "
                        "manquantes) et tu peux shortlister les meilleurs."
                    ),
                    "suggestions": dynamic_suggestions(ctx),
                    "links": [
                        {"label": "Rechercher ces talents",
                         "href": "/recruiter/candidates?skills=" + query},
                        {"label": "Mes shortlists", "href": "/recruiter/shortlists"},
                    ],
                }
            return {
                "reply": (
                    "Précise les compétences que tu cherches (ex. "
                    "« TCP/IP, Fortinet, Linux ») : la recherche de "
                    "talents te donne le matching expliqué par candidat."
                ),
                "suggestions": dynamic_suggestions(ctx),
                "links": [{"label": "Recherche de talents", "href": "/recruiter/candidates"}],
            }
        if re.search(r"(rédiger une offre|offre claire|comment.*offre|structurer une offre)", norm):
            return {
                "reply": (
                    "Pour une offre efficace : un intitulé métier "
                    "précis, les 3à5 compétences vraiment "
                    "nécessaires (essentielles vs appréciées), la "
                    "localisation et le type de contrat. Tu peux aussi me "
                    "donner une description libre : je la structure en offre."
                ),
                "suggestions": dynamic_suggestions(ctx),
                "links": [{"label": "Publier une offre", "href": "/recruiter/jobs"}],
            }

    # ---- Prochaine étape : l'agent s'appuie sur l'état réel du dossier
    if re.search(
        r"(quoi faire|que faire|dois[- ]je faire|par o[uù]|prochaine [eé]tape|"
        r"priorit[eé]|aujourd.?hui|comment avancer|o[uù] commencer)",
        norm,
    ):
        blocked = no_profile_reply()
        if blocked:
            return {
                "reply": blocked,
                "suggestions": ["Comment créer mon profil sans CV ?"],
                "links": [{"label": "Créer mon profil", "href": "/profile"}],
                "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}],
            }
        action = ctx.next_action()
        lines = [f"La prochaine action la plus utile : **{action['label']}**."]
        kind = action.get("type")
        if kind == "prepare_interview":
            lines.append(
                "Je peux te préparer un pitch, les questions probables et les "
                "points à vérifier sur l'offre. Tu valides le contenu avant l'entretien."
            )
        elif kind == "review_application":
            lines.append(
                "La candidature et ses documents sont prêts : relis-les puis "
                "confirme l'envoi. Rien n'est envoyé sans ta validation."
            )
        elif kind == "adapt_cv":
            lines.append(
                "Le CV ciblé reprend uniquement ton profil validé et les "
                "compétences demandées par cette offre. Le CV généraliste reste privé."
            )
        elif kind == "learn":
            lines.append(
                "Une formation réelle correspond à cette compétence. La fiche "
                "précise ce que le lien ouvre avant que tu cliques."
            )
        elif kind == "apply":
            lines.append(
                "Vérifie la source de l'offre, puis choisis le modèle de CV "
                "ciblé adapté. La lettre reste facultative."
            )
        if ctx.documents:
            lines.append(
                f"Tu as déjà {len(ctx.documents)} document(s) dans ta bibliothèque : "
                "inutile de tout régénérer, tu peux les relire et les télécharger."
            )
        return {
            "reply": "\n\n".join(lines),
            "suggestions": follow_ups("Où en sont mes candidatures ?"),
            "links": [
                {"label": "Faire cette action", "href": action.get("href", "/dashboard")},
                {"label": "Mes documents", "href": "/documents"},
            ],
        }

    # ---- Salutations : une vraie conversation commence simplement
    if re.search(r"\b(bonjour|salut|hello|bonsoir|mbote|coucou|yo)\b", norm):
        if ctx.profile is None:
            reply = (
                "Salut ! Bienvenue. Le plus simple pour commencer : importe "
                "ton CV ou réponds au questionnaire, et je m'occupe du reste."
            )
        else:
            reply = (
                "Salut, ça va ? Qu'est-ce qu'on fait aujourd'hui : chercher "
                "des offres, progresser sur une compétence, ou préparer un "
                "entretien ?"
            )
        links = [{"label": "Mon profil", "href": "/profile"}]
        return {"reply": reply, "suggestions": dynamic_suggestions(ctx), "links": links}

    # ---- Justification d'une recommandation (explicabilité §42)
    if re.search(r"(pourquoi|comment.*choisi|explication|justifie)", norm):
        blocked = no_profile_reply()
        if blocked:
            return {"reply": blocked, "suggestions": [], "links": [{"label": "Compléter mon profil", "href": "/profile"}],
            "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}]}
        lines = ["Voici comment j'ai construit mes recommandations :"]
        if ctx.best_match:
            job, m = ctx.best_match
            lines.append(
                f"- Meilleure offre « {job.title} » ({m['score']}/100) : "
                f"{len(m['covered'])} compétence(s) couverte(s), "
                f"{len(m['partial'])} partielle(s), {len(m['missing'])} manquante(s). "
                "Chaque score est expliqué sur la page de l'offre."
            )
        if ctx.top_career:
            career, m = ctx.top_career
            lines.append(
                f"- Métier recommandé « {career.title} » : accessibilité "
                f"« {m['accessibility']} » d'après vos compétences actuelles."
            )
        if ctx.gaps:
            lines.append(
                f"- Compétence prioritaire « {ctx.gaps[0]} » : absente de votre "
                "profil mais demandée par plusieurs offres actives."
            )
        reply = "\n".join(lines)
        links = [{"label": "Carrières", "href": "/careers"}]
        if ctx.best_match:
            links.append({"label": f"Offre : {ctx.best_match[0].title}", "href": f"/jobs/{ctx.best_match[0].id}"})
        return {"reply": reply, "suggestions": follow_ups("Comment réduire mes écarts ?"), "links": links}

    # ---- Recruteur : publier une offre depuis une brève description
    if ctx.role in ("recruiter", "admin") and re.search(
        r"(publi|créer|creer|ajouter|poster|rédiger|rediger).*offre|^(offre|recrute)\b", norm
    ):
        from app.services.job_parser import parse_job_description

        draft = parse_job_description(message)
        lines = ["Voici l'offre structurée depuis votre description :"]
        lines.append(f"- Poste : {draft['title'] or 'à préciser'}")
        lines.append(f"- Entreprise : {draft['company'] or 'à préciser'}")
        lines.append(f"- Localisation : {draft['location'] or 'à préciser'}")
        lines.append(f"- Contrat : {draft['contract_type']}")
        lines.append(f"- Secteur détecté : {draft['sector'] or 'à préciser'}")
        if draft["required_skills"]:
            names = ", ".join(
                f"{s['name']} ({'essentielle' if s['importance'] == 'core' else 'appréciée'})"
                for s in draft["required_skills"]
            )
            lines.append(f"- Compétences reconnues : {names}")
        lines.append(
            "Vérifiez et complétez ce brouillon dans « Mes offres » puis publiez : "
            "le bouton « Générer depuis une description » pré-remplit le "
            "formulaire. Rien n'est publié sans votre validation."
        )
        return {
            "reply": "\n".join(lines),
            "suggestions": ["Montre-moi les candidats correspondants."],
            "links": [
                {"label": "Publier cette offre", "href": "/recruiter/jobs"},
                {"label": "Rechercher des talents", "href": "/recruiter/candidates"},
            ] if ctx.role == "recruiter" else [{"label": "Base d'offres", "href": "/admin/jobs"}],
        }

    # ---- Entrepreneuriat (§11bis) : « comment entreprendre dans mon
    # domaine ? », financements, concours, incubateurs, business plan.
    _ent_core = re.search(
        r"(entreprendre|entrepreneur\w*|business[- ]?plan|startup|incubateur|"
        r"auto[- ]?emploi|micro[- ]?finance|microcr[ée]dit|"
        r"cr[ée]er (mon|ma|une) (entreprise|activit[ée]|boutique|soci[ée]t[ée]|bo[îi]te|affaire)|"
        r"lancer (mon|ma|une) (entreprise|activit[ée]|boutique|startup|affaire)|"
        r"monter (mon|ma|une) (entreprise|activit[ée]|boutique|affaire)|"
        r"mon (propre )?(business|projet d'entreprise)|[àa] mon compte|"
        r"devenir (mon|son) (propre )?patron)",
        norm,
    )
    # « financement » seul ne suffit pas : il faut un contexte de PROJET
    # (sinon « financer ma formation » reste du ressort de l'apprentissage).
    _ent_study = re.search(
        r"(formation|[eé]tudes?|[eé]cole|universit[eé]|bourse|master|licence)",
        norm,
    )
    _ent_money = re.search(
        r"(financement|financer|banque|banquier|cr[ée]dit|apport personnel|"
        r"fonds de garantie|dossier bancaire)",
        norm,
    )
    _ent_project = re.search(
        r"(projet|entreprise|activit[ée]|business|soci[ée]t[ée]|boutique|affaire)",
        norm,
    )
    if ctx.role == "candidate" and (
        _ent_core or (not _ent_study and _ent_money and _ent_project)
    ):
        guidance = _entrepreneur_guidance(ctx.profile, ctx.taxonomy)
        state = ctx.entrepreneur()
        lines: list[str] = []
        if ctx.profile:
            line = (
                f"D'après ton profil ({ctx.profile.get('title') or 'compétences multiples'}), "
                f"ton domaine d'atout est le {guidance.get('category_label') or 'à préciser'}."
            )
            if ctx.skills:
                line += (" Tes compétences ("
                         + ", ".join(s["skill"] for s in ctx.skills[:5])
                         + ") y sont directement mobilisables.")
            lines.append(line)
        else:
            lines.append(
                "L'entrepreneuriat est une trajectoire à part entière ici : "
                "financements, concours, incubateurs et accompagnement sont "
                "répertoriés. Complète ton profil et je précise le domaine où "
                "tes compétences sont le plus mobilisables."
            )

        if guidance.get("opportunities"):
            lines.append("\nPistes à instruire (jamais garanties) :")
            lines.extend(f"- {idea}" for idea in guidance["opportunities"][:3])
        if guidance.get("steps"):
            lines.append("\nPremières étapes :")
            lines.extend(f"- {step}" for step in guidance["steps"][:3])

        couvertes = [
            i["name"] for g in state["groups"] for i in g["items"]
            if i["state"] != "missing"
        ]
        if couvertes:
            lines.append(
                "\nCôté entreprise, ton profil couvre déjà "
                f"{len(couvertes)} compétence(s) du référentiel "
                f"({', '.join(couvertes[:4])})."
            )
        if ctx.gaps:
            lines.append("À renforcer : " + ", ".join(ctx.gaps[:3]) + ".")
        if ctx.financing:
            lines.append(
                "\nFinancements à instruire : "
                + ", ".join(f["name"] for f in ctx.financing[:3]) + "…"
            )
        if ctx.entrepreneur_resources:
            kinds: dict[str, int] = {}
            for r in ctx.entrepreneur_resources:
                kinds[r["kind_label"]] = kinds.get(r["kind_label"], 0) + 1
            lines.append(
                "Déjà répertoriés sur ta page Entrepreneuriat : "
                + " ; ".join(f"{label} : {n}" for label, n in kinds.items())
                + "."
            )
        lines.append(
            "\nJe peux te générer un business plan à partir de TES chiffres "
            "(activité, cible, capital, localisation) : il rejoint tes "
            "documents, sans rien inventer."
        )
        links = [
            {"label": "Ma page Entrepreneuriat", "href": "/entrepreneurship"},
            {"label": "Générer mon business plan", "href": "/entrepreneurship#business-plan"},
        ]
        if ctx.gaps:
            links.append({"label": "Combler mes écarts", "href": "/learning"})
        return {
            "reply": "\n".join(lines),
            "suggestions": follow_ups(
                "Quels financements pour mon projet ?",
                "Quelles compétences me manquent ?",
            ),
            "links": links,
        }

    # ---- Métiers compatibles (orientation, §26)
    if re.search(r"(metier|orientation|carrier|viser|quel boulot|quelle direction)", norm):
        blocked = no_profile_reply()
        if blocked:
            return {"reply": blocked, "suggestions": [], "links": [{"label": "Compléter mon profil", "href": "/profile"}],
            "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}]}
        tops = _top_careers(ctx.skills, ctx.careers, ctx.taxonomy)
        if not tops:
            reply = "Aucun métier référencé pour le moment."
        else:
            lines = ["Voici les métiers les plus compatibles avec ton profil :"]
            for career, m in tops:
                lines.append(
                    f"- « {career.title} » ({career.family}) : score {m['score']}/100, "
                    f"accessibilité {m['accessibility']}."
                )
            lines.append("Le détail complet est disponible sur la page Carrières.")
            reply = "\n".join(lines)
        if tops:
            links = [{"label": "Carrières", "href": "/careers"}]
        sugg = follow_ups(
            f"Pourquoi me recommandes-tu « {tops[0][0].title} » ?" if tops else "Quelles compétences me manquent ?",
        )
        return {"reply": reply, "suggestions": sugg, "links": links}

    # ---- Compétences manquantes (gap analysis)
    if re.search(r"(manque|ecart|competence.*a (developper|apprendre)|gap|point faible)", norm):
        blocked = no_profile_reply()
        if blocked:
            return {"reply": blocked, "suggestions": [], "links": [{"label": "Compléter mon profil", "href": "/profile"}],
            "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}]}
        if not ctx.gaps:
            reply = (
                "Bonne nouvelle : vous couvrez déjà les compétences des "
                "meilleures offres actuelles. Vous pouvez candidater !"
            )
            links = [{"label": "Voir les offres", "href": "/jobs"}]
        else:
            reply = (
                "Par rapport à tes métiers recommandés, tes écarts "
                "prioritaires sont : " + ", ".join(ctx.gaps[:5])
                + ". La page Apprentissage propose des formations concrètes "
                "pour chacune, avec leurs liens."
            )
            first = (ctx.resources_for(ctx.gaps[0]) or [])[:1]
            links = [{"label": "Apprentissage", "href": "/learning"}]
            if first:
                links.insert(0, {
                    "label": f"Fiche : {first[0]['title'][:42]}",
                    "href": _learning_href(first[0]),
                })
        return {
            "reply": reply,
            "suggestions": follow_ups(f"Quelles formations suivre pour {ctx.gaps[0]} ?"),
            "links": links,
        }

    # ---- Candidatures : le mini-ATS personnel, avec les données RÉELLES
    # (sauf demande de RÉDACTION : « rédige mon mail de candidature… »
    # relève de l'agent rédacteur, traité plus bas)
    if re.search(r"\b(candidatures?|postule|postuler|relances?)\b", norm) and not re.search(
        r"(mail|courriel|e-?mail|messagerie|r[eé]dige|[eé]cris|r[eé]daction)", norm
    ):
        if not ctx.applications:
            # Rien à lister : on guide (le profil n'est pas nécessaire pour
            # suivre une candidature, mais il l'est pour la suite).
            blocked = no_profile_reply()
            if blocked:
                return {"reply": blocked, "suggestions": [], "links": [{"label": "Compléter mon profil", "href": "/profile"}],
                "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}]}
            return {
                "reply": (
                    "Tu ne suis encore aucune candidature. La page Candidatures "
                    "sert de mini-ATS personnel : pour chaque offre suivie, tu "
                    "retrouves l'étape franchie (identifiée → CV préparé → "
                    "envoyée → en attente → entretien → offre), les documents "
                    "générés et l'historique daté. Ouvre une offre qui "
                    "t'intéresse et clique sur « Suivre ma candidature »."
                ),
                "suggestions": follow_ups("Quelles offres me correspondent ?"),
                "links": [{"label": "Parcourir les offres", "href": "/jobs"}],
            }

        ongoing = [
            a for a in ctx.applications
            if a.get("status") not in CLOSED_STATUSES
        ]
        interviews = [a for a in ctx.applications if a.get("status") == "entretien"]
        waiting = [a for a in ctx.applications if a.get("status") == "en_attente"]

        lines = [
            "Tu suis " + str(len(ctx.applications)) + " candidature(s), dont "
            + str(len(ongoing)) + " encore en cours :"
        ]
        for a in ctx.applications[:6]:
            status = a.get("status") or ""
            lines.append(
                "- « " + str(a.get("job_title") or "?") + " » : "
                + APPLICATION_LABELS.get(status, status)
            )
        if interviews:
            lines.append(
                "Ton entretien pour « " + str(interviews[0].get("job_title"))
                + " » se prépare : questions probables, pitch et conseils sont "
                "générés uniquement depuis ton profil validé (§47)."
            )
        if waiting:
            lines.append(
                str(len(waiting)) + " candidature(s) en attente de réponse : "
                "fais avancer l'étape dès que tu reçois un retour, l'historique "
                "reste daté et vérifiable."
            )
        links = [{"label": "Mes candidatures", "href": "/applications"}]
        if interviews and interviews[0].get("job_id"):
            links.append({
                "label": "Préparer l'entretien",
                "href": "/jobs/" + str(interviews[0]["job_id"]),
            })
        return {"reply": "\n".join(lines), "suggestions": follow_ups(), "links": links}

    # ---- Offres / opportunités / stages (sauf demande CV/lettre :
    # « adapte mon CV pour l'offre X » relève de l'adaptation)
    if re.search(r"(offre|emploi|job|stage|opportun|recrut|poste)", norm) and not re.search(
        r"\b(cv|curriculum)\b|lettre|adapt|mail|courriel", norm
    ):
        ordered = sorted(ctx.jobs, key=lambda j: j.published_at, reverse=True)
        if ctx.profile:
            ordered = [j for j, _m in _top_matches(ctx.skills, ctx.jobs, ctx.taxonomy, n=5)]
        if not ordered:
            reply = "Aucune offre ne correspond aux critères pour l'instant."
            links = []
        else:
            lines = ["Voici les offres les plus pertinentes :"]
            for job in ordered[:5]:
                extra = ""
                if ctx.profile:
                    m = compute_match(ctx.skills, job.required_skills, ctx.taxonomy)
                    extra = f" · correspondance {m['score']}/100 ({m['level']})"
                lines.append(
                    f"- « {job.title} » chez {job.company} ({job.location}, "
                    f"{job.contract_type}, publiée le {job.published_at.date().isoformat()}){extra}"
                )
            reply = "\n".join(lines)
            links = [{"label": f"Offre : {ordered[0].title}", "href": f"/jobs/{ordered[0].id}"}]
        return {
            "reply": reply,
            "suggestions": follow_ups(f"Prépare mon CV pour « {ordered[0].title} »" if ordered else "Quelles compétences me manquent ?"),
            "links": links,
        }

    # ---- Courriel d'accompagnement : rédigé depuis le profil valide,
    # prêt à coller dans une messagerie (§47 : aucun fait inventé).
    if re.search(r"(courriel|e-?mail|\bmail\b|messagerie|message d'accompagnement)", norm):
        blocked = no_profile_reply()
        if blocked:
            return {
                "reply": blocked,
                "suggestions": [],
                "links": [{"label": "Compléter mon profil", "href": "/profile"}],
                "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}],
            }
        job = _find_job_by_mention(ctx, message)
        if job is None and ctx.best_match:
            job = ctx.best_match[0]
        # « généraliste / sans offre » explicite : on ne retombe PAS sur la
        # meilleure correspondance, l'utilisateur veut un document non ciblé.
        generalist = bool(re.search(
            r"(generaliste|sans offre|sans ciblage|sans poste|non cible)", norm))
        if generalist:
            job = None
        structure = cv_builder.build_letter_paragraphs(
            ctx.profile, job, ctx.user, ctx.taxonomy)
        headline = ctx.profile.get("title") or "profil professionnel"
        subject = (
            f"Candidature au poste de {job.title} - {job.company}"
            if job is not None
            else f"Candidature spontanée - {headline}"
        )
        blocks = [
            "Voici votre courriel d'accompagnement, prêt à coller, uniquement "
            "des faits de votre profil validé :",
            f"**Objet : {subject}**",
            "Madame, Monsieur,",
        ]
        blocks += list(structure["paragraphs"])
        blocks.append(structure["closing"][0])
        signature = [structure["signature"]]
        extra = []
        if headline:
            extra.append(headline)
        if ctx.profile.get("location"):
            extra.append(str(ctx.profile["location"]))
        if getattr(ctx.user, "email", None):
            extra.append(str(ctx.user.email))
        if extra:
            signature.append(" · ".join(extra))
        blocks.append("\n".join(["", "--", *signature]))
        links = [{"label": "Mes documents", "href": "/documents"}]
        actions = []
        if job is not None:
            links.insert(0, {"label": f"Choisir ma lettre : {job.title}",
                             "href": f"/opportunites/{job.id}?galerie=lettre"})
            actions = [
                {"type": "generate_letter", "job_id": job.id,
                 "label": "Adapter ma lettre (choisir le modèle)"},
            ]
        else:
            links.insert(0, {"label": "Créer ma lettre généraliste",
                             "href": "/documents?lettre=1"})
        return {
            "reply": "\n\n".join(blocks),
            "suggestions": follow_ups("Prépare mon entretien."),
            "links": links,
            "actions": actions,
        }

    # ---- CV / lettre / candidature : l'AGENT propose les textes
    # d'adaptation (réorganisation factuelle du profil, §47), puis le
    # candidat choisit son modèle dans la galerie de l'offre.
    if re.search(r"\b(cv|curriculum)\b|lettre|candidature|adapt", norm):
        blocked = no_profile_reply()
        if blocked:
            return {"reply": blocked, "suggestions": [], "links": [{"label": "Compléter mon profil", "href": "/profile"}],
            "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}]}
        # Offre mentionnée dans la question ? Sinon meilleure correspondance.
        # « Généraliste / sans offre » explicite : aucun ciblage, jamais.
        generalist = bool(re.search(
            r"(generaliste|sans offre|sans ciblage|sans poste|non cible)", norm))
        job = None if generalist else _find_job_by_mention(ctx, message)
        if job is None and not generalist and ctx.best_match:
            job = ctx.best_match[0]
        if job is None:
            reply = (
                "Aucune offre disponible pour l'instant. Je peux quand même "
                "préparer des documents GÉNÉRALISTES depuis votre profil validé "
                ", sans ciblage d'offre : un CV complet, ou une lettre de "
                "motivation dont vous complétez le destinataire."
            )
            links = [
                {"label": "Créer mon CV généraliste", "href": "/documents"},
                {"label": "Créer ma lettre généraliste", "href": "/documents?lettre=1"},
            ]
            actions = []
            notes = _cv_completion_notes(ctx.profile) if ctx.profile else []
            if notes:
                reply += (" Avant l'export, il reste à ajouter, pour un dossier "
                          "bien rempli : " + " ; ".join(notes) + ".")
                links.append({"label": "Compléter mon profil", "href": "/profile"})
                actions = [{"type": "build_profile", "label": "Compléter mon profil"}]
            return {
                "reply": reply,
                "suggestions": follow_ups("Quelles compétences me manquent ?"),
                "links": links,
                "actions": actions,
            }
        m = compute_match(ctx.skills, job.required_skills, ctx.taxonomy) if ctx.skills else None
        lines = [f"Pour l'offre « {job.title} » ({job.company}), voici les textes que je propose d'insérer, uniquement à partir de votre profil validé :"]
        summary = ctx.profile.get("summary") if ctx.profile else None
        if not summary and m and m["covered"]:
            summary = (
                f"Profil orienté « {job.title} » ; compétences pertinentes "
                f"déjà acquises : {', '.join(m['covered'][:5])}."
            )
        if summary:
            lines += ["", "Accroche du CV :", summary]
        if m and m["covered"]:
            lines += ["", "Compétences à mettre en avant : " + ", ".join(m["covered"][:6]) + "."]
        letter = cv_builder.build_letter_paragraphs(
            ctx.profile, job, ctx.user, ctx.taxonomy)
        if letter["paragraphs"]:
            lines += ["", "Lettre (ouverture) :", letter["paragraphs"][0]]
            if len(letter["paragraphs"]) > 1:
                lines += ["", "Lettre (correspondance) :", letter["paragraphs"][1]]
        lines += [
            "",
            "Validez en choisissant le modèle et la couleur : les documents "
            "reprendront exactement ces éléments, sans rien inventer 🙂",
        ]
        notes = _cv_completion_notes(ctx.profile) if ctx.profile else []
        if notes:
            lines += ["", "Pour un dossier bien rempli, il reste à ajouter :"]
            lines += [f"- {n}" for n in notes]
        links = [
            {"label": f"Choisir le modèle de CV : {job.title}", "href": f"/opportunites/{job.id}?galerie=cv"},
            {"label": f"Choisir le modèle de lettre", "href": f"/opportunites/{job.id}?galerie=lettre"},
            {"label": "Mes documents", "href": "/documents"},
        ]
        actions = [
            {"type": "generate_cv", "job_id": job.id,
             "label": "Adapter mon CV (choisir le modèle)"},
            {"type": "generate_letter", "job_id": job.id,
             "label": "Adapter ma lettre (choisir le modèle)"},
        ]
        if notes:
            links.append({"label": "Compléter mon profil", "href": "/profile"})
            actions.append({"type": "build_profile", "label": "Compléter mon profil"})
        return {
            "reply": "\n".join(lines),
            "suggestions": follow_ups(f"Prépare mon entretien pour « {job.title} »"),
            "links": links,
            "actions": actions,
        }

    # ---- Entretien
    if re.search(r"(entretien|interview)", norm):
        blocked = no_profile_reply()
        if blocked:
            return {"reply": blocked, "suggestions": [], "links": [{"label": "Compléter mon profil", "href": "/profile"}],
            "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}]}
        if not ctx.best_match:
            reply = "Aucune offre disponible pour préparer un entretien."
            links = []
        else:
            job, m = ctx.best_match
            reply = (
                f"Pour ta meilleure offre (« {job.title} », {job.company}), la "
                "page de détail propose une préparation d'entretien : questions "
                "probables, questions techniques sur les compétences demandées, "
                "questions comportementales et un pitch professionnel factuel."
            )
            links = [{"label": "Préparer l'entretien", "href": f"/jobs/{job.id}"}]
        return {
            "reply": reply,
            "suggestions": follow_ups("Génère mon CV ciblé."),
            "links": links,
            "actions": [
                {"type": "interview_prep", "job_id": job.id,
                 "label": "Simuler l'entretien maintenant"},
            ],
        }

    # ---- Tendances / marché
    if re.search(r"(tendance|marche|secteur|demande|salaire)", norm):
        trends = ctx.trends
        lines = ["Tendances calculées sur les offres de la base (dates traçables) :"]
        if trends["top_skills"]:
            lines.append(
                "Compétences les plus demandées : "
                + ", ".join(f"{s['name']} ({s['count']})" for s in trends["top_skills"][:5])
                + "."
            )
        if trends["trending_up"]:
            lines.append("En hausse : " + ", ".join(trends["trending_up"][:5]) + ".")
        if trends["emerging"]:
            lines.append("Émergentes : " + ", ".join(trends["emerging"][:5]) + ".")
        reply = "\n".join(lines)
        links = [{"label": "Marché", "href": "/market"}]
        return {"reply": reply, "suggestions": follow_ups("Comment mes compétences se positionnent-elles ?"), "links": links}

    # ---- Mes formations suivies et leurs preuves (§19)
    if re.search(
        r"(formation(s)? suivie|mon suivi|suivi de (mes|ma) formation|"
        r"o[uù] en sont? mes formations|ajouter (une|ma) formation (a|à) mon profil|"
        r"preuve de formation|certificat.*(profil|preuve)|badge|"
        r"formation[^.?]{0,25}preuve|preuve[^.?]{0,25}formation|"
        r"devient une preuve|rendre[^.?]{0,20}v[eé]rifiable|"
        r"v[eé]rifier[^.?]{0,20}(formation|certificat))",
        norm,
    ) and not re.search(r"(offre|poste|candidature)", norm):
        blocked = no_profile_reply()
        if blocked:
            return {"reply": blocked, "suggestions": [],
                    "links": [{"label": "Compléter mon profil", "href": "/profile"}],
                    "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}]}
        lines = []
        if not ctx.enrollments:
            lines.append(
                "Vous ne suivez aucune formation pour l'instant. Ouvrez une "
                "formation depuis la page Apprentissage : elle rejoint votre "
                "suivi, avec son avancement."
            )
        else:
            vérifiées = [e for e in ctx.enrollments if e.get("verifiable")]
            ajoutées = [e for e in ctx.enrollments if e.get("added_to_profile")]
            lines.append(
                f"Vous suivez {len(ctx.enrollments)} formation(s) : "
                f"{len(vérifiées)} avec une pièce vérifiable, "
                f"{len(ajoutées)} rattachée(s) à votre profil."
            )
            for e in ctx.enrollments[:4]:
                ligne = f"- « {e['title']} » · {e['provider'] or 'fournisseur non précisé'} · {e['status_label']}"
                if e.get("verifiable"):
                    ligne += f" · pièce : {e.get('proof_label', 'fournie')}"
                if e.get("added_to_profile"):
                    ligne += " · au profil"
                lines.append(ligne)
        lines.append(
            "Rappel : c'est la pièce (certificat, attestation, badge ou "
            "portfolio) fournie par le fournisseur qui rend la formation "
            "vérifiable ; l'ajout au profil reste votre décision."
        )
        return {
            "reply": "\n".join(lines),
            "suggestions": follow_ups(
                f"Quelles formations suivre pour {ctx.gaps[0]} ?" if ctx.gaps
                else "Quels métiers puis-je viser ?"
            ),
            "links": [{"label": "Mes formations", "href": "/learning"}],
        }

    # ---- Formation / apprentissage (avec liens réels vers les cours)
    if re.search(r"(formation|apprendre|cours|certif|etudier|upskill|remis(es|e)? (à|a|en) niveau|mise (à|a) niveau|recyclage|perfectionnement|se perfectionner)", norm):
        blocked = no_profile_reply()
        if blocked:
            return {"reply": blocked, "suggestions": [], "links": [{"label": "Compléter mon profil", "href": "/profile"}],
            "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}]}
        # Compétence précise dans la question ? Sinon, premier écart prioritaire.
        asked = next(
            (name for name in ctx.gaps if name.lower() in message.lower()),
            ctx.gaps[0] if ctx.gaps else None,
        )
        resources = ctx.resources_for(asked) if asked else []
        links = [{"label": "Apprentissage", "href": "/learning"}]
        lines = []
        if ctx.gaps:
            lines.append(
                "Tes écarts prioritaires, par rapport à tes métiers recommandés : "
                + ", ".join(ctx.gaps[:3]) + "."
            )
            if asked and resources:
                lines.append(f"Pour « {asked} », voici des formations concrètes :")
                for r in resources[:3]:
                    # La nature du lien est dite : aucune page trompeuse.
                    nature = r.get("link_kind_label") or ""
                    suffixe = f" · {nature}" if nature and nature != "Formation exacte" else ""
                    if r.get("url"):
                        # Lien markdown : cliquable dans le chat
                        lines.append(f"- [{r['title']}]({r['url']}) · {r['provider']}{suffixe}")
                    else:
                        lines.append(
                            f"- {r['title']} · {r['provider']}"
                            + (f" ({nature})" if nature else "")
                        )
                    # Bouton interne : ouvre LA fiche de cette formation
                    # (et non la page Apprentissage générique).
                    links.append({
                        "label": f"Fiche : {r['title'][:40]}",
                        "href": _learning_href(r),
                    })
                lines.append(
                    "Ouvrez celle qui vous convient depuis la page Apprentissage : "
                    "vous pourrez y suivre votre avancement et joindre votre pièce "
                    "pour la rendre vérifiable."
                )
            elif asked:
                lines.append(
                    f"Aucune ressource référencée pour « {asked} » pour l'instant ; "
                    "la page Apprentissage reste la référence."
                )
        else:
            lines.append(
                "Aucun écart majeur détecté : la page Apprentissage liste "
                "des ressources pour consolider vos compétences."
            )
        reply = "\n".join(lines)
        return {
            "reply": reply,
            "suggestions": follow_ups(f"Quelles formations suivre pour {ctx.gaps[0]} ?" if ctx.gaps else "Quels métiers puis-je viser ?"),
            "links": links,
        }

    # ---- Profil LinkedIn : recommandations d'amélioration
    if re.search(r"linkedin", norm):
        blocked = no_profile_reply()
        if blocked:
            return {"reply": blocked, "suggestions": [], "links": [{"label": "Compléter mon profil", "href": "/profile"}],
            "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}]}
        url_match = re.search(r"https?://[^\s]+linkedin[^\s]+", message, re.IGNORECASE)
        lines = []
        if url_match:
            lines.append(
                "Merci pour le lien. Enregistrez-le dans votre profil OrientSkill "
                "(Préférences) pour vos prochaines visites."
            )
        lines.append(
            "Note honnête : je ne consulte pas directement votre page LinkedIn "
            "(accès autorisé uniquement). Ces recommandations s'appuient sur "
            "votre profil OrientSkill validé et sur les exigences réelles des offres :"
        )
        title = ctx.profile.get("title") or ""
        if title:
            lines.append(
                f"- Titre : reprenez « {title} » sur LinkedIn plutôt qu'un libellé "
                "vague ; les recruteurs cherchent par mots-clés."
            )
        if ctx.best_match:
            job, m = ctx.best_match
            lines.append(
                f"- Pour viser « {job.title} », mettez en avant : "
                + ", ".join(m["covered"][:5])
                + " (compétences demandées par les offres actuelles)."
            )
        informal = [e for e in ctx.profile.get("experiences", []) if e.get("type") != "formal"]
        if informal:
            lines.append(
                "- Listez aussi vos expériences informelles ("
                + ", ".join((e.get("title") or "?") for e in informal[:3])
                + ") : sur le marché camerounais, elles comptent et OrientSkill "
                "les valorise déjà dans vos correspondances."
            )
        if ctx.profile.get("certifications"):
            lines.append(
                "- Ajoutez vos certifications (" +
                ", ".join(c.get("name", "") for c in ctx.profile["certifications"][:3])
                + ") dans la section Licences et certifications."
            )
        lines.append(
            "- Faites vérifier votre profil OrientSkill (pièce d'identité) : le "
            "badge « Profil vérifié » rassure les recruteurs."
        )
        reply = "\n".join(lines)
        links = [{"label": "Mon profil OrientSkill", "href": "/profile"}]
        return {"reply": reply, "suggestions": follow_ups("Quelles compétences me manquent ?"), "links": links}

    # ---- Bilan : « c'est à toi de me dire, d'après ce que tu observes »
    if re.search(
        r"(où j'en suis|mon bilan|fais le point|faire le point|le point sur|"
        r"ce que tu (vois|observes?|repères?|as repéré)|d'après ce que|"
        r"bas[ée]e?? sur ce que|autour de moi|ta analyse|ton analyse|conseille[- ]moi|"
        r"pending|en attente|t[aâ]ches|pas accompli|non accomplpl?i|me reste|"
        r"qu'est[- ]ce qui me reste|mon dashboard|tableau de bord|pas encore fait)",
        norm,
    ):
        blocked = no_profile_reply()
        if blocked:
            return {
                "reply": blocked,
                "suggestions": [],
                "links": [{"label": "Compléter mon profil", "href": "/profile"}],
                "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}],
            }
        lines = []
        if ctx.top_career:
            career, m = ctx.top_career
            lines.append(
                "Ton profil colle bien avec « " + career.title + " » "
                "(score " + str(m["score"]) + "/100)."
            )
        if ctx.best_match:
            job, m = ctx.best_match
            lines.append(
                "Côté offres, ta meilleure piste reste « " + job.title + " » chez "
                + job.company + " (" + str(m["score"]) + "/100)."
            )
        if ctx.gaps:
            lines.append(
                "Pour progresser, tes écarts prioritaires sont : "
                + ", ".join(ctx.gaps[:3]) + "."
            )
        ongoing = [
            a for a in ctx.applications
            if a.get("status") not in ("acceptee", "refusee", None)
        ]
        if ongoing:
            detail = ", ".join(
                f"« {a.get('job_title', '?')} » ({a.get('status')})"
                for a in ongoing[:3]
            )
            lines.append("En cours de ton côté : " + detail + ".")
        interviews = [a for a in ctx.applications if a.get("status") == "entretien"]
        if interviews:
            lines.append(
                "Et tu as " + str(len(interviews)) + " entretien(s) à préparer : "
                "on peut le simuler ensemble quand tu veux 🙂"
            )
        lines.append("On commence par quoi ?")
        links = []
        if ctx.best_match:
            links.append({"label": "Offre : " + ctx.best_match[0].title,
                          "href": "/jobs/" + str(ctx.best_match[0].id)})
        links.append({"label": "Apprentissage", "href": "/learning"})
        return {
            "reply": "\n".join(lines),
            "suggestions": dynamic_suggestions(ctx),
            "links": links,
        }

    # ---- Fallback honnête, mais vivant : on oriente vers le concret
    import random as _random

    page_hint = _PAGE_HINTS.get((ctx.page_context or "").strip().lower())
    if page_hint:
        return {
            "reply": page_hint,
            "suggestions": dynamic_suggestions(ctx),
            "links": [{"label": "Tableau de bord", "href": "/dashboard"}],
        }

    fallbacks = [
        "Là, je ne suis pas sûr d'avoir saisi. Reformule autrement : par "
        "exemple « où j'en suis », « formations pour Cisco », « prépare mon "
        "CV », ou « cherche des bourses MINFOP sur internet ».",
        "Je n'ai pas compris la demande. Essaie avec un exemple concret : "
        "« quelles formations pour Azure », « prépare mon entretien », ou "
        "colle l'URL d'une offre à analyser.",
        "Hmm, reformule pour moi : quel est le but ? Trouver une offre, "
        "monter en compétence, préparer une candidature ou comprendre où "
        "tu en es ?",
    ]
    links = [{"label": "Tableau de bord", "href": "/dashboard"}]
    return {
        "reply": _random.choice(fallbacks),
        "suggestions": dynamic_suggestions(ctx),
        "links": links,
    }


def _llm_reply(
    message: str,
    history: list[dict[str, str]],
    ctx: _Context,
    db: Session,
) -> Optional[str]:
    """Appel LLM (paramètres admin). L'agent reçoit une PERSONNALITÉ
    conversationnelle + le contexte complet (données vivantes + web)."""
    if not llm_client.get_llm_config(db)["enabled"]:
        return None
    system = (
        "Tu es Ori, l'assistant personnel d'OrientSkill AI (plateforme "
        "camounaise d'intelligence professionnelle). Tu tutoies l'utilisateur. "
        "Tu es un mentor : direct, chaleureux, jamais robotique.\n\n"
        "COMMENT TU PARLES :\n"
        "- Phrases courtes et naturelles, comme dans une vraie discussion.\n"
        "- Réponds À LA QUESTION POSÉE. Si on te dit « bonjour », réponds "
        "« salut » et propose ton aide en UNE phrase, ne balance jamais un "
        "bilan complet non demandé.\n"
        "- Pas de structure type « Opportunité immédiate : » ni de titres "
        "de sections. Les listes, seulement si l'utilisateur demande "
        "plusieurs éléments.\n"
        "- Tu te souviens de la conversation : ne redemande pas ce que tu "
        "sais déjà, ne répète pas le même conseil deux fois.\n"
        "- Une émoticône quand c'est naturel (encouragement, réussite, "
        "conclusion positive), jamais sur chaque phrase.\n\n"
        "CE QUE TU SAIS FAIRE (propose-le au bon moment, pas d'un coup) :\n"
        "- orienter vers des métiers, expliquer les écarts ;\n"
        "- recommander des formations avec leurs vrais liens (ceux du "
        "contexte, jamais d'URL inventée) ;\n"
        "- préparer les entretiens (propose une simulation quand c'est "
        "pertinent) ;\n"
        "- générer un CV ciblé ou une lettre de motivation à partir du "
        "profil validé (l'utilisateur valide ensuite, tu ne modifies "
        "rien sans accord) ;\n"
        "- conseiller en entrepreneuriat (business plan, financements) ;\n"
        "- suivre les candidatures. Une suggestion d'action par réponse "
        "maximum.\n\n"
        "RÈGLES DE VÉRITÉ :\n"
        "- Uniquement le contexte et les résultats web fournis : rien "
        "d'inventé, aucun chiffre fabriqué.\n"
        "- Formations : 1 ou 2 liens max, intégrés naturellement à la "
        "phrase.\n"
        "- Si l'info n'est ni dans le contexte ni dans les résultats web, "
        "dis-le simplement.\n"
        "- Tu ne prétends jamais ignorer une donnée présente dans le "
        "contexte (prénom, métier, ville, candidatures).\n"
        "- Historique de conversation : conservé 30 jours par défaut ; "
        "l'utilisateur peut l'effacer ou passer en mode éphémère.\n\n"
        + (
            "PAGE OÙ SE TROUVE L'UTILISATEUR : « " + ctx.page_context + " ». "
            "Oriente naturellement tes conseils et tes actions vers ce qui se "
            "fait sur cette page, sans l'annoncer mécaniquement.\n\n"
            if ctx.page_context else ""
        )
        + "CONTEXTE (données réelles de l'utilisateur) :\n"
        + ctx.context_document()
    )
    messages = [{"role": "system", "content": system}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-12:]]
    messages.append({"role": "user", "content": message})
    return llm_client.chat_completion(db, messages, max_tokens=900)


def answer(
    message: str,
    history: list[dict[str, str]],
    profile: Optional[dict],
    jobs: list[Any],
    careers: list[Any],
    taxonomy,
    db: Optional[Session] = None,
    resources: Optional[dict] = None,
    role: str = "candidate",
    applications: Optional[list[dict]] = None,
    verified: bool = False,
    entrepreneur_resources: Optional[list[dict]] = None,
    financing: Optional[list[dict]] = None,
    enrollments: Optional[list[dict]] = None,
    documents: Optional[list[dict]] = None,
    agent_mode: str = "preparation",
    user: Any = None,
    context: Optional[str] = None,
) -> dict[str, Any]:
    """Point d'entrée : LLM si configuré (avec succès), sinon règles.
    Les suggestions sont TOUJOURS calculées depuis les données réelles.
    `mode` révèle à l'interface le moteur utilisé (« llm » ou « local »)."""
    # Continuation d'une réponse interrompue ou tronquée : on relance
    # la demande précédente au lieu de tomber dans le fallback.
    if re.search(
        r"(vas[- ]?y|continue|termine|finis|g[eè]n[eè]re la r[eé]ponse compl[eè]te|"
        r"r[eé]ponse compl[eè]te|pas compl[eè]tement g[eé]n[eé]r[eé]e|tu t'es coup[eé])",
        message, re.IGNORECASE,
    ):
        previous = [
            m["content"] for m in history[-8:]
            if m.get("role") == "user"
            and not re.search(
                r"(vas[- ]?y|continue|termine|finis|g[eè]n[eè]re la r[eé]ponse|"
                r"compl[eè]tement g[eé]n[eé]r[eé]e)", m["content"], re.IGNORECASE)
        ]
        if previous:
            message = previous[-1]

    # Fouille web bornée : si l'utilisateur demande une recherche, on
    # collecte AVANT de répondre. Le sujet vient du message courant,
    # ou de la question précédente (« et sur internet, il y a rien ? »).
    web_results = []
    search_query = None
    if _SEARCH_TRIGGERS.search(message):
        search_query = _detect_search(message) or _detect_search_from_history(history)
    if search_query:
        web_results = _web_search(search_query)

    ctx = _Context(
        profile, jobs, careers, taxonomy,
        resources=resources, role=role,
        applications=applications, verified=verified,
        web_results=web_results,
        entrepreneur_resources=entrepreneur_resources,
        financing=financing,
        enrollments=enrollments,
        documents=documents,
        agent_mode=agent_mode,
        user=user,
        page_context=context,
    )
    llm_text = _llm_reply(message, history, ctx, db) if db is not None else None
    rules = _rules_reply(message, ctx)
    if llm_text:
        rules["reply"] = llm_text
        # Robustesse : les liens cités par le LLM deviennent AUSSI des
        # boutons cliquables sous la réponse (le rendu du chat gère déjà
        # le markdown ; les boutons restent là en secours).
        md_links = re.findall(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", llm_text)
        existing = {l.get("href") for l in rules.get("links", [])}
        for label, url in md_links[:4]:
            if url not in existing:
                existing.add(url)
                rules.setdefault("links", []).append(
                    {"label": label[:40] or "Lien", "href": url}
                )
    rules.setdefault("actions", [])
    if role == "admin":
        rules["mode"] = "llm" if llm_text else "local"
    else:
        rules["mode"] = "orientskill"
    return rules
