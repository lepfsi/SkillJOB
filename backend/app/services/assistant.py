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
from app.services.market import market_trends
from app.services.matching import compute_match
from app.services.orientation import match_career
from app.services.skills_taxonomy import normalize


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
    Retourne [{title, url, snippet}] — liste vide si échec."""
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
                 applications=None, verified=False, web_results=None):
        self.profile = profile
        self.skills = profile.get("skills", []) if profile else []
        self.jobs = jobs
        self.careers = careers
        self.taxonomy = taxonomy
        self.resources = resources or {}
        self.role = role
        self.applications = applications or []
        self.verified = verified
        self.web_results = web_results or []
        self.best_match = _top_matches(self.skills, jobs, taxonomy, n=1)[0] if (profile and jobs) else None
        self.top_career = _top_careers(self.skills, careers, taxonomy, n=1)[0] if (profile and careers) else None
        self.gaps = _priority_gaps(self.skills, jobs, careers, taxonomy) if profile else []
        self.trends = market_trends(jobs)

    def resources_for(self, skill: str) -> list[dict]:
        """Ressources réelles (titre + URL) pour une compétence."""
        return self.resources.get(skill, [])

    def context_document(self) -> str:
        """Document de contexte complet pour le LLM : tout ce que l'agent
        sait, avec les liens EXACTS à citer. Le LLM n'invente rien, il
        puise ici (§47 : ancrage sur données réelles)."""
        parts: list[str] = []

        if self.profile:
            identity = [
                self.profile.get("title") or "sans titre",
                self.profile.get("location") or "",
            ]
            parts.append("PROFIL : " + " · ".join(filter(None, identity))
                         + (" · identité vérifiée" if self.verified else ""))
            skills_line = ", ".join(
                f"{s['skill']} ({s.get('proficiency', '')})"
                for s in self.skills[:10]
            )
            if skills_line:
                parts.append("COMPÉTENCES DU PROFIL : " + skills_line)

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

        # Formations disponibles : liens EXACTS à recopier dans la réponse
        formation_lines = []
        for skill in self.gaps[:4]:
            for r in self.resources_for(skill)[:2]:
                url = f" · {r['url']}" if r.get("url") else ""
                formation_lines.append(
                    f"[{r['title']}]({r['url']}) · {r['provider']}{url} [compétence : {skill}]"
                    if r.get("url")
                    else f"{r['title']} · {r['provider']} (sans lien) [compétence : {skill}]"
                )
        if formation_lines:
            parts.append(
                "FORMATIONS DISPONIBLES (cite ces liens markdown EXACTEMENT, "
                "sans en inventer d'autres) :\n" + "\n".join(formation_lines)
            )

        # Candidatures
        if self.applications:
            parts.append("CANDIDATURES : " + " ; ".join(
                f"{a.get('job_title', '?')} → {a.get('status', '?')}"
                for a in self.applications[:5]
            ))

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
    if not out:
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
    # fournie par l'utilisateur — jamais de collecte de masse)
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
            links = [{"label": "Apprentissage", "href": "/learning"}]
        return {
            "reply": reply,
            "suggestions": follow_ups(f"Quelles formations suivre pour {ctx.gaps[0]} ?"),
            "links": links,
        }

    # ---- Candidatures
    if re.search(r"\b(candidature|postule|postuler|relance)\b", norm):
        blocked = no_profile_reply()
        if blocked:
            return {"reply": blocked, "suggestions": [], "links": [{"label": "Compléter mon profil", "href": "/profile"}],
            "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}]}
        reply = (
            "La page Candidatures joue le rôle de mini-ATS personnel : chaque "
            "offre suivie affiche son pipeline (identifiée, CV préparé, envoyée, "
            "entretien, offre) et son historique daté. Relancez plutôt les "
            "candidatures en attente depuis plus de dix jours."
        )
        links = [{"label": "Mes candidatures", "href": "/applications"}]
        return {"reply": reply, "suggestions": follow_ups(), "links": links}

    # ---- Offres / opportunités / stages
    if re.search(r"(offre|emploi|job|stage|opportun|recrut|poste)", norm):
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

    # ---- CV / lettre / candidature
    if re.search(r"\b(cv|curriculum)\b|lettre|candidature", norm):
        blocked = no_profile_reply()
        if blocked:
            return {"reply": blocked, "suggestions": [], "links": [{"label": "Compléter mon profil", "href": "/profile"}],
            "actions": [{"type": "build_profile", "label": "On construit ton profil ?"}]}
        if not ctx.best_match:
            reply = "Aucune offre disponible pour générer un CV ciblé."
            links = []
        else:
            job, m = ctx.best_match
            reply = (
                f"Ta meilleure correspondance actuelle est « {job.title} » "
                f"chez {job.company} (score {m['score']}/100). "
                "Je peux générer un CV ciblé et une lettre de motivation qui "
                "réorganisent UNIQUEMENT les informations de votre profil "
                "validé : rien n'est inventé. Le PDF est aux normes A4. "
                "Ouvrez l'offre puis choisissez « Créer mon CV ciblé »."
            )
            links = [{"label": f"Offre : {job.title}", "href": f"/jobs/{job.id}"},
                     {"label": "Mes documents", "href": "/documents"}]
        return {
            "reply": reply,
            "suggestions": follow_ups("Quelles questions d'entretien anticiper ?"),
            "links": links,
            "actions": [
                {"type": "generate_cv", "job_id": job.id,
                 "label": "Générer mon CV ciblé"},
                {"type": "generate_letter", "job_id": job.id,
                 "label": "Rédiger ma lettre de motivation"},
            ],
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
                    if r.get("url"):
                        # Lien markdown : cliquable dans le chat
                        lines.append(f"- [{r['title']}]({r['url']}) · {r['provider']}")
                        links.append({
                            "label": f"{r['title'][:40]} · {r['provider']}",
                            "href": r["url"],
                        })
                    else:
                        lines.append(f"- {r['title']} · {r['provider']}")
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
        r"bas[ée]e?? sur ce que|autour de moi|ta analyse|ton analyse|conseille[- ]moi)",
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
        interviews = [a for a in ctx.applications if a.get("status") == "entretien"]
        if interviews:
            lines.append(
                "Et tu as " + str(len(interviews)) + " entretien(s) à préparer : "
                "on peut le simuler ensemble quand tu veux."
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
        "« salut » et propose ton aide en UNE phrase — ne balance jamais un "
        "bilan complet non demandé.\n"
        "- Pas de structure type « Opportunité immédiate : » ni de titres "
        "de sections. Les listes, seulement si l'utilisateur demande "
        "plusieurs éléments.\n"
        "- Tu te souviens de la conversation : ne redemande pas ce que tu "
        "sais déjà, ne répète pas le même conseil deux fois.\n\n"
        "CE QUE TU SAIS FAIRE (propose-le au bon moment, pas d'un coup) :\n"
        "- orienter vers des métiers, expliquer les écarts ;\n"
        "- recommander des formations avec leurs vrais liens (ceux du "
        "contexte, jamais d'URL inventée) ;\n"
        "- préparer les entretiens (propose une simulation quand c'est "
        "pertinent) ;\n"
        "- conseiller en entrepreneuriat (business plan, financements) ;\n"
        "- suivre les candidatures. Une suggestion d'action par réponse "
        "maximum.\n\n"
        "RÈGLES DE VÉRITÉ :\n"
        "- Uniquement le contexte et les résultats web fournis : rien "
        "d'inventé, aucun chiffre fabriqué.\n"
        "- Formations : 1 ou 2 liens max, intégrés naturellement à la "
        "phrase.\n"
        "- Si l'info n'est ni dans le contexte ni dans les résultats web, "
        "dis-le simplement.\n\n"
        "CONTEXTE (données réelles de l'utilisateur) :\n"
        + ctx.context_document()
    )
    messages = [{"role": "system", "content": system}]
    messages += [{"role": m["role"], "content": m["content"]} for m in history[-12:]]
    messages.append({"role": "user", "content": message})
    return llm_client.chat_completion(db, messages, max_tokens=450)


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
) -> dict[str, Any]:
    """Point d'entrée : LLM si configuré (avec succès), sinon règles.
    Les suggestions sont TOUJOURS calculées depuis les données réelles.
    `mode` révèle à l'interface le moteur utilisé (« llm » ou « local »)."""
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
    rules["mode"] = "llm" if llm_text else "local"
    return rules
