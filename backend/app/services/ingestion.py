"""Ingestion multi-source automatisée (§50) et import par URL (§10).

- Connecteurs RSS/Atom et JSON : collecte, normalisation, déduplication
  inter-sources, conservation de la date de publication d'origine et
  scoring de fiabilité par source (succès/échecs, offres importées).
- Exécution parallèle des téléchargements pour les collectes multi-sources,
  avec requêtes conditionnelles (ETag / Last-Modified) lorsque le serveur
  les expose : un flux inchangé répond 304 et n'est pas reparsé.
- Import par URL : une page d'offre publique (LinkedIn ou autre) est
  analysée via son balisage JSON-LD « JobPosting ». L'import est
  explicitement soumis à validation humaine avant enregistrement.
"""
import hashlib
import html as html_module
import json
import re
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

from app.services import job_parser
from app.services.skills_taxonomy import load_taxonomy

_UA = {
    "User-Agent": "Mozilla/5.0 (OrientSkillAI/2.0; +https://orientskill.cm)",
    "Accept": (
        "application/rss+xml, application/atom+xml, application/json, "
        "text/xml, application/xml, text/html;q=0.8, */*;q=0.5"
    ),
}
_MAX_BYTES = 5 * 1024 * 1024
_MAX_ITEMS = 50
_FETCH_WORKERS = 4
_RUN_LOCK = threading.Lock()
_LAST_HTTP = threading.local()


# ----------------------------------------------------------- collecte

def _read_limited(response) -> bytes:
    data = response.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError("Flux trop volumineux (limite 5 Mo).")
    return data


def _fetch(url: str, timeout: int = 15) -> bytes:
    """Télécharge une ressource publique avec une limite de taille."""
    request = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = _read_limited(response)
            _LAST_HTTP.headers = {
                "etag": (response.headers.get("ETag") or "").strip(),
                "last_modified": (
                    response.headers.get("Last-Modified") or ""
                ).strip(),
            }
            return data
    except Exception:
        _LAST_HTTP.headers = {}
        raise


def _fetch_conditional(
    url: str,
    etag: str = "",
    last_modified: str = "",
    timeout: int = 15,
) -> tuple[bytes, str, str, bool]:
    """Télécharge un flux, avec validation conditionnelle si possible.

    Retourne (contenu, etag, last_modified, inchangé). Le premier appel
    passe par ``_fetch`` pour rester compatible avec les connecteurs de
    test ; les appels suivants peuvent recevoir un 304.
    """
    if not etag and not last_modified:
        _LAST_HTTP.headers = {}
        raw = _fetch(url, timeout=timeout)
        meta = getattr(_LAST_HTTP, "headers", {}) or {}
        return (
            raw,
            str(meta.get("etag") or ""),
            str(meta.get("last_modified") or ""),
            False,
        )

    headers = dict(_UA)
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            # Un 200 signifie que le flux a changé : on repart des en-têtes
            # réellement renvoyés pour ne jamais conserver un ETag périmé.
            return (
                _read_limited(response),
                (response.headers.get("ETag") or "").strip(),
                (response.headers.get("Last-Modified") or "").strip(),
                False,
            )
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return b"", etag, last_modified, True
        raise


def _strip_html(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", text)


def _dedup_key(title: str, company: str, location: str) -> str:
    raw = f"{_normalize(title)}|{_normalize(company)}|{_normalize(location)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def _canonical_url(value: Any) -> str:
    """Normalise une URL pour éviter les doublons de tracking."""
    url = str(value or "").strip()
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("http", "https"):
            return url[:1000]
        query = [
            (key, item)
            for key, item in urllib.parse.parse_qsl(
                parsed.query, keep_blank_values=True
            )
            if not key.lower().startswith(("utm_", "fbclid", "gclid", "mc_"))
        ]
        path = parsed.path.rstrip("/") or "/"
        return urllib.parse.urlunsplit((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            urllib.parse.urlencode(query),
            "",
        ))[:1000]
    except Exception:
        return url[:1000]


def _parse_date(value: Any) -> Optional[datetime]:
    """Convertit une date RSS/JSON en datetime UTC naïf."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        stamp = float(value)
        if stamp > 10_000_000_000:
            stamp /= 1000
        try:
            return datetime.fromtimestamp(stamp, tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None

    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return _parse_date(int(text))

    iso = text.replace("Z", "+00:00")
    parsed: Optional[datetime] = None
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError):
            parsed = None
    if parsed is None:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    if parsed.year < 2000 or parsed > datetime.utcnow() + timedelta(days=366):
        return None
    return parsed


def _date_only(value: Any) -> str:
    parsed = _parse_date(value)
    if parsed is not None:
        return parsed.strftime("%Y-%m-%d")
    return str(value or "").strip()[:160]


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1]


def _child_text(element, *names: str) -> str:
    wanted = set(names)
    for child in list(element):
        if _strip_ns(child.tag) in wanted:
            text = " ".join(
                part.strip() for part in child.itertext() if part.strip()
            )
            if text:
                return text
    return ""


def _item_link(element) -> str:
    for child in list(element):
        if _strip_ns(child.tag) != "link":
            continue
        href = (child.get("href") or "").strip()
        if href:
            return href
        text = "".join(child.itertext()).strip()
        if text:
            return text
    return _child_text(element, "guid", "id")


def parse_rss(xml_bytes: bytes) -> list[dict[str, str]]:
    """Extrait les items d'un flux RSS/Atom (sans dépendance externe)."""
    root = ET.fromstring(xml_bytes)
    items: list[dict[str, str]] = []
    for item in root.iter():
        if _strip_ns(item.tag) not in ("item", "entry"):
            continue
        title = _child_text(item, "title")
        if not title:
            continue
        description = _child_text(
            item, "encoded", "description", "summary", "content"
        )
        items.append({
            "title": title,
            "link": _item_link(item),
            "description": _strip_html(description)[:4000],
            "published": _child_text(
                item, "pubDate", "published", "updated", "date", "created"
            ),
            "author": _child_text(
                item, "creator", "author", "source", "company", "employer"
            ),
            "location": _child_text(item, "location", "jobLocation", "city"),
            "deadline": _child_text(item, "validThrough", "deadline"),
        })
    return items


def _first(entry: dict, *keys: str) -> Any:
    for key in keys:
        value = entry.get(key)
        if value not in (None, "", [], {}):
            return value
    return ""


def _as_text(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "title", "label", "value", "addressLocality", "city"):
            if value.get(key) not in (None, "", [], {}):
                return str(value[key]).strip()
        return ""
    if isinstance(value, list):
        return ", ".join(
            part for part in (_as_text(item) for item in value) if part
        )
    return str(value or "").strip()


def _location_text(value: Any) -> str:
    if isinstance(value, dict):
        address = value.get("address")
        if isinstance(address, dict):
            parts = [
                _as_text(address.get("addressLocality")),
                _as_text(address.get("addressRegion")),
                _as_text(address.get("addressCountry")),
            ]
            text = ", ".join(part for part in parts if part)
            if text:
                return text
        if address:
            return _as_text(address)
        if value.get("name"):
            return _as_text(value.get("name"))
        return _as_text(value)
    return _as_text(value)


def _json_items(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [entry for entry in data if isinstance(entry, dict)]
    if isinstance(data, dict):
        for key in (
            "items", "jobs", "results", "data", "offers", "records", "content"
        ):
            value = data.get(key)
            if isinstance(value, list):
                found = [entry for entry in value if isinstance(entry, dict)]
                if found:
                    return found
            elif isinstance(value, dict):
                found = _json_items(value)
                if found:
                    return found
        if any(key in data for key in ("title", "position", "job_title")):
            return [data]
    return []


def parse_json_feed(raw: bytes) -> list[dict[str, str]]:
    """Connecteur JSON générique : liste d'objets avec clés usuelles."""
    data = json.loads(raw.decode("utf-8-sig", errors="ignore"))
    items: list[dict[str, str]] = []
    for entry in _json_items(data):
        title = _as_text(_first(entry, "title", "position", "job_title", "name"))
        if not title:
            continue
        description = _as_text(_first(
            entry, "description", "summary", "content", "content_html",
            "content_text", "job_description", "details",
        ))
        items.append({
            "title": title,
            "link": _as_text(_first(
                entry, "url", "link", "external_url", "apply_url", "job_url",
                "absolute_url",
            )),
            "description": _strip_html(description)[:4000],
            "published": _as_text(_first(
                entry, "date_published", "published_at", "date", "datePublished",
                "published", "created_at", "posted_at",
            )),
            "author": _as_text(_first(
                entry, "company", "company_name", "organization", "employer",
                "authors", "author",
            )),
            "location": _location_text(_first(
                entry, "location", "city", "job_location", "place"
            )),
            "deadline": _as_text(_first(
                entry, "deadline", "validThrough", "valid_through"
            )),
        })
    return items


def test_source(kind: str, url: str) -> dict[str, Any]:
    """Lit un flux sans l'enregistrer, pour valider sa configuration."""
    try:
        raw = _fetch(url, timeout=12)
        items = parse_rss(raw) if kind == "rss" else parse_json_feed(raw)
    except Exception as exc:
        return {
            "ok": False,
            "items": 0,
            "sample": None,
            "detail": f"Lecture impossible : {exc}",
        }
    sample = items[0] if items else None
    if items:
        detail = f"Flux accessible : {len(items)} élément(s) détecté(s)."
    else:
        detail = "Flux accessible, mais aucun élément reconnu."
    return {"ok": True, "items": len(items), "sample": sample, "detail": detail}


def _parse_payload(kind: str, raw: bytes) -> list[dict[str, str]]:
    return parse_rss(raw) if kind == "rss" else parse_json_feed(raw)


def _collect_source(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Télécharge et parse une source dans un thread de collecte."""
    started = time.perf_counter()
    try:
        raw, etag, last_modified, not_modified = _fetch_conditional(
            snapshot["url"],
            etag=snapshot.get("etag") or "",
            last_modified=snapshot.get("last_modified") or "",
        )
        items = [] if not_modified else _parse_payload(snapshot["kind"], raw)
        return {
            "items": items,
            "etag": etag,
            "last_modified": last_modified,
            "not_modified": not_modified,
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "duration_ms": int((time.perf_counter() - started) * 1000),
        }


def _record_failure(db, source, error: str, duration_ms: int) -> dict[str, Any]:
    previous_error = source.last_error or ""
    source.runs += 1
    source.failures += 1
    source.last_run_at = datetime.utcnow()
    source.last_items = 0
    source.last_duration_ms = duration_ms
    source.last_error = str(error)[:1000]
    source.last_status = f"Échec : {str(error)[:80]}"
    db.commit()
    if not previous_error:
        # Alerte uniquement à la première panne : une source qui échoue
        # plusieurs fois de suite ne spamme pas l'équipe.
        from app.services import admin_alerts

        admin_alerts.notify_admins(
            db,
            "ingestion",
            f"Échec de collecte : {source.name}",
            (
                f"La source « {source.name} » ({source.url}) n'a pas pu être "
                f"lue.\nErreur : {str(error)[:1000]}\n"
                "La collecte reprendra automatiquement au prochain passage."
            ),
        )
    return {
        "source": source.name,
        "imported": 0,
        "skipped": 0,
        "items": 0,
        "duration_ms": duration_ms,
        "error": str(error),
    }


def _job_index(db) -> tuple[set[str], set[str]]:
    """Charge une seule fois les clés de déduplication de la base.

    Une passe multi-source réutilise cet index : éviter une requête sur
    toutes les offres pour chaque source garde la collecte fluide même
    lorsque plusieurs connecteurs sont exécutés ensemble.
    """
    from app import models

    keys: set[str] = set()
    urls: set[str] = set()
    for key, source_url in db.query(
        models.Job.dedup_key, models.Job.source_url
    ).all():
        if key:
            keys.add(key)
        if source_url:
            urls.add(_canonical_url(source_url))
    return keys, urls


def _persist_source(
    db,
    source,
    items: list[dict[str, str]],
    duration_ms: int,
    etag: str = "",
    last_modified: str = "",
    not_modified: bool = False,
    existing_keys: Optional[set[str]] = None,
    existing_urls: Optional[set[str]] = None,
) -> dict[str, Any]:
    from app import models

    now = datetime.utcnow()
    source.runs += 1
    source.last_run_at = now
    source.last_duration_ms = duration_ms
    source.last_error = ""
    if etag:
        source.etag = etag[:255]
    if last_modified:
        source.last_modified = last_modified[:255]

    if not_modified:
        source.last_items = 0
        source.last_status = "OK : flux inchangé (aucun nouvel élément)"
        db.commit()
        return {
            "source": source.name,
            "imported": 0,
            "skipped": 0,
            "items": 0,
            "duration_ms": duration_ms,
            "not_modified": True,
        }

    if existing_keys is None or existing_urls is None:
        if items:
            existing_keys, existing_urls = _job_index(db)
        else:
            existing_keys, existing_urls = set(), set()

    taxonomy = load_taxonomy() if items else None
    imported = skipped = 0
    for item in items[:_MAX_ITEMS]:
        title_raw = str(item.get("title") or "").strip()
        if not title_raw:
            continue
        description = _strip_html(item.get("description"))[:4000]
        text = " ".join(filter(None, [title_raw, description]))
        draft = job_parser.parse_job_description(text)
        title = (draft["title"] or title_raw)[:255]
        company = (
            draft["company"]
            or str(item.get("author") or "").strip()
            or source.name
        )[:255]
        location = (
            draft["location"]
            or str(item.get("location") or "").strip()
            or "Cameroun"
        )[:255]
        link = _canonical_url(item.get("link"))
        if link and link in existing_urls:
            skipped += 1
            continue
        key = _dedup_key(title, company, location)
        if key in existing_keys:
            skipped += 1
            continue
        existing_keys.add(key)
        if link:
            existing_urls.add(link)

        skills = draft["required_skills"] or [
            {"name": name, "importance": "preferred"}
            for name in taxonomy.find_in_text(text)[:6]
        ]
        published_at = _parse_date(item.get("published")) or now
        deadline = _parse_date(item.get("deadline"))
        job = models.Job(
            title=title,
            company=company,
            location=location,
            sector=draft["sector"] or source.sector or "À qualifier",
            contract_type=draft["contract_type"],
            description=description or text[:4000],
            requirements="",
            required_skills=skills,
            published_at=published_at,
            source_name=f"Collecte · {source.name}",
            source_url=link or source.url,
            dedup_key=key,
            deadline=deadline or None,
        )
        db.add(job)
        imported += 1

    source.offers_imported += imported
    source.offers_skipped += skipped
    source.last_items = len(items)
    source.last_status = (
        f"OK : {len(items)} élément(s), {imported} importé(s), "
        f"{skipped} doublon(s)"
    )[:120]
    db.commit()
    return {
        "source": source.name,
        "imported": imported,
        "skipped": skipped,
        "items": len(items),
        "duration_ms": duration_ms,
    }


def run_sources(db, sources) -> list[dict[str, Any]]:
    """Exécute plusieurs sources : téléchargements parallèles, écriture
    séquentielle dans une seule session SQLAlchemy."""
    if not sources:
        return []
    snapshots = [
        {
            "id": source.id,
            "name": source.name,
            "kind": source.kind,
            "url": source.url,
            "sector": source.sector,
            "etag": source.etag or "",
            "last_modified": source.last_modified or "",
        }
        for source in sources
    ]

    with _RUN_LOCK:
        if len(snapshots) == 1:
            collected = [_collect_source(snapshots[0])]
        else:
            with ThreadPoolExecutor(
                max_workers=min(_FETCH_WORKERS, len(snapshots))
            ) as pool:
                collected = list(pool.map(_collect_source, snapshots))

        existing_keys: Optional[set[str]] = None
        existing_urls: Optional[set[str]] = None
        results: list[dict[str, Any]] = []
        for snapshot, outcome in zip(snapshots, collected):
            source = db.get(type(sources[0]), snapshot["id"])
            if source is None:
                continue
            if "error" in outcome:
                results.append(_record_failure(
                    db, source, outcome["error"], outcome["duration_ms"]
                ))
            else:
                items = outcome["items"]
                if items and existing_keys is None:
                    existing_keys, existing_urls = _job_index(db)
                results.append(_persist_source(
                    db,
                    source,
                    items,
                    outcome["duration_ms"],
                    etag=outcome.get("etag") or "",
                    last_modified=outcome.get("last_modified") or "",
                    not_modified=bool(outcome.get("not_modified")),
                    existing_keys=existing_keys,
                    existing_urls=existing_urls,
                ))
    return results


def run_source(db, source) -> dict[str, Any]:
    """Exécute UN connecteur : collecte, normalise, déduplique, importe."""
    result = run_sources(db, [source])
    if result:
        return result[0]
    return {"source": source.name, "imported": 0, "skipped": 0, "items": 0}


def run_all_sources(db) -> list[dict[str, Any]]:
    """Exécute tous les connecteurs ACTIVÉS (§50 : architecture
    multi-source à connecteurs interchangeables)."""
    from app import models

    sources = (
        db.query(models.SourceConfig)
        .filter_by(enabled=True)
        .order_by(models.SourceConfig.id.asc())
        .all()
    )
    return run_sources(db, sources)


def _is_due(source, now: datetime) -> bool:
    if not source.enabled:
        return False
    if source.last_run_at is None:
        return True
    interval = max(5, int(source.interval_minutes or 60))
    return source.last_run_at + timedelta(minutes=interval) <= now


def due_sources(db, now: Optional[datetime] = None) -> list[Any]:
    """Sources activées dont l'intervalle de collecte est échu."""
    from app import models

    current = now or datetime.utcnow()
    sources = db.query(models.SourceConfig).filter_by(enabled=True).all()
    return [source for source in sources if _is_due(source, current)]


def run_due_sources(db) -> list[dict[str, Any]]:
    """Passe de collecte autonome : seules les sources échues sont lues."""
    return run_sources(db, due_sources(db))


# ----------------------------------------------------- import par URL

def _jsonld_nodes(data: Any):
    if isinstance(data, list):
        for node in data:
            yield from _jsonld_nodes(node)
    elif isinstance(data, dict):
        if "@graph" in data:
            yield from _jsonld_nodes(data.get("@graph"))
        yield data
        for value in data.values():
            if isinstance(value, (dict, list)):
                yield from _jsonld_nodes(value)


def _is_job_posting(node: dict) -> bool:
    value = node.get("@type")
    types = value if isinstance(value, list) else [value]
    return any(
        str(item).strip().lower().replace(" ", "") == "jobposting"
        for item in types
    )


def _meta_tags(html: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for match in re.finditer(r"<meta\b[^>]*>", html, re.IGNORECASE):
        attrs = dict(re.findall(
            r'([a-zA-Z:_-]+)\s*=\s*["\']([^"\']*)["\']',
            match.group(0),
        ))
        key = (attrs.get("property") or attrs.get("name") or "").lower()
        if key:
            tags.setdefault(key, html_module.unescape(attrs.get("content", "")))
    return tags


def import_job_from_url(url: str) -> dict[str, Any]:
    """Importe une offre depuis une page publique (LinkedIn ou autre)
    via son balisage JSON-LD « JobPosting ».

    Mécanisme autorisé : la page est fournie par l'utilisateur et lue
    une seule fois pour en extraire le balisage standard. Le résultat
    est un BROUILLON à valider (§47), aucun scraping de masse.
    """
    try:
        html = _fetch(url).decode("utf-8", errors="ignore")
    except Exception as exc:
        return {"error": f"Impossible de lire la page : {exc}"}

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
        for node in _jsonld_nodes(data):
            if isinstance(node, dict) and _is_job_posting(node):
                return _jobposting_to_draft(node, url)

    # 2) Repli : extraction « Open Graph »
    og = _meta_tags(html)
    if og.get("og:title") or og.get("title"):
        text = " ".join(filter(None, [
            og.get("og:title") or og.get("title"),
            og.get("og:description") or og.get("description"),
        ]))
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
        if isinstance(address, dict):
            location = ", ".join(filter(None, [
                _as_text(address.get("addressLocality")),
                _as_text(address.get("addressRegion")),
                _as_text(address.get("addressCountry")),
            ]))
        elif address:
            location = _as_text(address)
        if not location and loc.get("name"):
            location = _as_text(loc.get("name"))
    if not location and str(node.get("jobLocationType") or "").upper() == "TELECOMMUTE":
        location = "Télétravail"

    skills_raw = node.get("skills") or node.get("qualifications") or ""
    skills_text = _as_text(skills_raw)

    taxonomy = load_taxonomy()
    description = _strip_html(node.get("description"))[:4000]
    found = taxonomy.find_in_text(
        " ".join(filter(None, [skills_text, description]))
    )
    seen: set[str] = set()
    required = []
    for name in found:
        if name not in seen:
            seen.add(name)
            required.append({
                "name": name,
                "importance": "core" if len(seen) <= 5 else "preferred",
            })

    employment = _as_text(node.get("employmentType")).lower()
    contract = (
        "CDI" if any(k in employment for k in ("full", "permanent", "cdi"))
        else "CDD" if any(k in employment for k in ("contract", "cdd"))
        else "Stage" if "intern" in employment or "trainee" in employment
        else "Apprentissage" if "apprent" in employment
        else "Freelance" if "part" in employment or "temp" in employment
        else "CDI"
    )

    salary = ""
    base_salary = node.get("baseSalary")
    if isinstance(base_salary, dict):
        value = base_salary.get("value")
        if isinstance(value, dict):
            salary = str(
                value.get("value")
                or value.get("minValue")
                or value.get("maxValue")
                or ""
            )
        elif value not in (None, ""):
            salary = str(value)

    valid_through = _date_only(node.get("validThrough"))

    return {
        "title": _as_text(node.get("title"))[:200],
        "company": _as_text(org_name)[:150],
        "location": location[:150] or "Cameroun",
        "sector": job_parser.parse_job_description(
            f"{node.get('title', '')} {org_name} {description[:300]}"
        )["sector"],
        "contract_type": contract,
        "description": description,
        "requirements": skills_text[:1000],
        "salary": salary,
        "required_skills": required,
        "source_url": url,
        "deadline": valid_through,
        "warning": (
            "Brouillon importé depuis le balisage public de la page : "
            "vérifiez et complétez chaque champ avant publication."
        ),
    }
