"""Ingestion multi-source automatisée (§50) et import par URL (§10).

- Connecteurs RSS et JSON : collecte, normalisation, DÉDUPLICATION
  (une même offre vue sur plusieurs sources n'entre qu'une fois) et
  scoring de fiabilité par source (succès/échecs, offres importées).
- Import par URL : une page d'offre publique (LinkedIn ou autre) est
  analysée via son balisage JSON-LD « JobPosting ». L'import est
  explicitement soumis à validation humaine avant enregistrement.
"""
import hashlib
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Optional

from app.services import job_parser
from app.services.skills_taxonomy import load_taxonomy

_UA = {"User-Agent": "Mozilla/5.0 (OrientSkillAI/2.0; +https://orientskill.cm)"}


# ----------------------------------------------------------- collecte

def _fetch(url: str, timeout: int = 15) -> bytes:
    request = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _dedup_key(title: str, company: str, location: str) -> str:
    raw = f"{title.strip().lower()}|{company.strip().lower()}|{location.strip().lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1]


def parse_rss(xml_bytes: bytes) -> list[dict[str, str]]:
    """Extrait les items d'un flux RSS/Atom (sans dépendance externe)."""
    root = ET.fromstring(xml_bytes)
    items: list[dict[str, str]] = []

    def text_of(el, path: str) -> str:
        if el is None:
            return ""
        found = el.find(path)
        return (found.text or "").strip() if found is not None and found.text else ""

    for item in root.iter():
        if _strip_ns(item.tag) not in ("item", "entry"):
            continue
        title = text_of(item, "title")
        link_el = item.find("link")
        link = ""
        if link_el is not None:
            link = (link_el.get("href") or link_el.text or "").strip()
        description = text_of(item, "description") or text_of(item, "summary")
        pub = text_of(item, "pubDate") or text_of(item, "published") or text_of(item, "updated")
        author = text_of(item, "author") or text_of(item, "source")
        if title:
            items.append({
                "title": title,
                "link": link,
                "description": re.sub(r"<[^>]+>", " ", description)[:2000].strip(),
                "published": pub,
                "author": author,
            })
    return items


def parse_json_feed(raw: bytes) -> list[dict[str, str]]:
    """Connecteur JSON générique : liste d'objets avec clés usuelles."""
    data = json.loads(raw.decode("utf-8", errors="ignore"))
    if isinstance(data, dict):
        data = data.get("items") or data.get("jobs") or data.get("results") or data.get("data") or []
    items = []
    for entry in data if isinstance(data, list) else []:
        if not isinstance(entry, dict):
            continue
        items.append({
            "title": str(entry.get("title") or entry.get("position") or ""),
            "link": str(entry.get("url") or entry.get("link") or ""),
            "description": str(entry.get("description") or entry.get("summary") or "")[:2000],
            "published": str(entry.get("published_at") or entry.get("date") or entry.get("datePublished") or ""),
            "author": str(entry.get("company") or entry.get("organization") or entry.get("author") or ""),
        })
    return [i for i in items if i["title"]]


def run_source(db, source) -> dict[str, int]:
    """Exécute UN connecteur : collecte, normalise, déduplique, importe.
    Retourne {imported, skipped} et met à jour le scoring de la source."""
    from app import models

    taxonomy = load_taxonomy()
    imported = skipped = 0
    try:
        raw = _fetch(source.url)
        items = parse_rss(raw) if source.kind == "rss" else parse_json_feed(raw)
    except Exception as exc:
        source.runs += 1
        source.failures += 1
        source.last_run_at = datetime.utcnow()
        source.last_status = f"Échec : {str(exc)[:80]}"
        db.commit()
        return {"imported": 0, "skipped": 0, "error": str(exc)}

    existing_keys = {
        k for (k,) in db.query(models.Job.dedup_key).filter(models.Job.dedup_key.isnot(None)).all()
    }

    for item in items[:50]:
        text = " ".join(filter(None, [item["title"], item["description"]]))
        draft = job_parser.parse_job_description(text)
        title = draft["title"] or item["title"][:150]
        company = draft["company"] or item["author"] or source.name
        location = draft["location"]
        key = _dedup_key(title, company, location)
        if key in existing_keys:
            skipped += 1
            continue
        existing_keys.add(key)
        skills = draft["required_skills"] or [
            {"name": n, "importance": "preferred"} for n in
            (taxonomy.find_in_text(text)[:6])
        ]
        job = models.Job(
            title=title,
            company=company,
            location=location or "Cameroun",
            sector=draft["sector"] or source.sector or "À qualifier",
            contract_type=draft["contract_type"],
            description=item["description"] or text[:2000],
            requirements="",
            required_skills=skills,
            published_at=datetime.utcnow(),
            source_name=f"Collecte · {source.name}",
            source_url=item["link"] or source.url,
            dedup_key=key,
        )
        db.add(job)
        imported += 1

    source.runs += 1
    source.offers_imported += imported
    source.offers_skipped += skipped
    source.last_run_at = datetime.utcnow()
    source.last_status = f"OK : {len(items)} élément(s), {imported} importé(s), {skipped} doublon(s)"
    db.commit()
    return {"imported": imported, "skipped": skipped, "items": len(items)}


def run_all_sources(db) -> list[dict[str, Any]]:
    """Exécute tous les connecteurs ACTIVÉS (§50 : architecture
    multi-source à connecteurs interchangeables)."""
    from app import models

    results = []
    for source in db.query(models.SourceConfig).filter_by(enabled=True).all():
        res = run_source(db, source)
        results.append({"source": source.name, **res})
    return results


# ----------------------------------------------------- import par URL

def import_job_from_url(url: str) -> dict[str, Any]:
    """Importe une offre depuis une page publique (LinkedIn ou autre)
    via son balisage JSON-LD « JobPosting ».

    Mécanisme autorisé : la page est fournie par l'utilisateur et lue
    une seule fois pour en extraire le balisage standard. Le résultat
    est un BROUILLON à valider (§47) — aucun scraping de masse.
    """
    html = _fetch(url).decode("utf-8", errors="ignore")

    # 1) JSON-LD (standard schema.org utilisé par LinkedIn et la plupart
    #    des job boards)
    for match in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    ):
        try:
            data = json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            continue
        for node in (data if isinstance(data, list) else [data]):
            if isinstance(node, dict) and str(node.get("@type", "")).lower() in ("jobposting", "job posting"):
                return _jobposting_to_draft(node, url)

    # 2) Repli : extraction « Open Graph »
    og = {}
    for prop, content in re.findall(
        r'<meta[^>]+(?:property|name)=["\'](og:[a-z]+|title|description)["\'][^>]+content=["\']([^"\']*)["\']',
        html, re.IGNORECASE,
    ):
        og.setdefault(prop.lower(), content)
    if og.get("og:title") or og.get("title"):
        text = " ".join(filter(None, [og.get("og:title") or og.get("title"), og.get("description") or og.get("og:description")]))
        draft = job_parser.parse_job_description(text)
        draft["description"] = text[:4000]
        draft["company"] = draft["company"] or og.get("og:site_name") or ""
        draft["source_url"] = url
        draft["warning"] = (
            "Brouillon importé depuis la page (balisage de base) : vérifiez "
            "chaque champ avant de publier."
        )
        return draft

    return {"error": (
        "Aucun balisage d'offre reconnu sur cette page. Vérifiez que l'URL "
        "pointe directement vers une offre publique."
    )}


def _jobposting_to_draft(node: dict, url: str) -> dict[str, Any]:
    """Convertit un objet JSON-LD JobPosting en brouillon normalisé."""
    org = node.get("hiringOrganization") or {}
    if isinstance(org, list):
        org = org[0] if org else {}
    org_name = org.get("name") if isinstance(org, dict) else str(org)

    location = ""
    loc = node.get("jobLocation") or {}
    if isinstance(loc, list):
        loc = loc[0] if loc else {}
    if isinstance(loc, dict):
        address = loc.get("address") or {}
        location = ", ".join(
            filter(None, [
                address.get("addressLocality") or "",
                address.get("addressRegion") or "",
                address.get("addressCountry") or "",
            ])
        )

    skills_raw = node.get("skills") or node.get("qualifications") or ""
    if isinstance(skills_raw, list):
        skills_raw = " ".join(str(s) for s in skills_raw)

    taxonomy = load_taxonomy()
    found = taxonomy.find_in_text(
        " ".join(filter(None, [str(skills_raw), str(node.get("description") or "")]))
    )
    seen: set[str] = set()
    required = []
    for name in found:
        if name not in seen:
            seen.add(name)
            required.append({"name": name, "importance": "core" if len(seen) <= 5 else "preferred"})

    employment = str(node.get("employmentType") or "").lower()
    contract = (
        "CDI" if any(k in employment for k in ("full", "permanent", "cdi"))
        else "CDD" if any(k in employment for k in ("contract", "cdd"))
        else "Stage" if "intern" in employment or "trainee" in employment
        else "Apprentissage" if "apprent" in employment
        else "Freelance" if "part" in employment or "temp" in employment
        else "CDI"
    )

    description = re.sub(r"<[^>]+>", " ", str(node.get("description") or ""))[:4000]
    valid_through = str(node.get("validThrough") or "")[:10]

    return {
        "title": str(node.get("title") or "")[:200],
        "company": str(org_name or "")[:150],
        "location": location[:150] or "Cameroun",
        "sector": job_parser.parse_job_description(
            f"{node.get('title', '')} {org_name} {description[:300]}"
        )["sector"],
        "contract_type": contract,
        "description": description,
        "requirements": re.sub(r"<[^>]+>", " ", str(skills_raw or ""))[:1000],
        "salary": str(
            (node.get("baseSalary") or {}).get("value", {}).get("value", "")
            if isinstance(node.get("baseSalary"), dict) else ""
        ),
        "required_skills": required,
        "source_url": url,
        "warning": (
            "Brouillon importé depuis le balisage public de la page : "
            "vérifiez et complétez chaque champ avant publication."
        ),
    }
