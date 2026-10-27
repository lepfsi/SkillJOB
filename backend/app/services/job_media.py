"""Photo d'illustration d'une offre d'emploi (facultative).

Déposée par le publieur, recruteur ou administration, au moment de la
publication. Elle reste FACULTATIVE : une offre sans photo s'affiche
normalement. Le fichier est conservé tel quel et servi aux candidats.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app import config

# Bac à sable des dépôts : UPLOAD_DIR isolé pour les tests et le smoke,
# jamais le dossier réel de l'utilisateur.
JOBS_DIR = config.UPLOAD_DIR / "jobs"
_ALLOWED = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_BYTES = 5 * 1024 * 1024


def photo_url(job) -> str | None:
    """URL publique de la photo, ou None si l'offre n'en a pas."""
    if not job.photo_path:
        return None
    return f"/api/jobs/{job.id}/photo"


def save(job, file: UploadFile) -> str:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED:
        raise HTTPException(
            status_code=400,
            detail="Format accepté : JPG, PNG ou WebP",
        )
    payload = file.file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Fichier vide")
    if len(payload) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="Image trop volumineuse (5 Mo maximum)")
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    remove(job)  # une seule photo par offre : l'ancienne est remplacée
    stored = f"offre-{job.id}{ext}"
    (JOBS_DIR / stored).write_bytes(payload)
    job.photo_path = stored
    return stored


def remove(job) -> None:
    if not job.photo_path:
        return
    try:
        (JOBS_DIR / Path(job.photo_path).name).unlink(missing_ok=True)
    except OSError:  # pragma: no cover : fichier déjà absent
        pass
    job.photo_path = None


def path_for(job) -> Path:
    stored = Path(str(job.photo_path or "")).name
    target = JOBS_DIR / stored
    if not stored or not target.exists():
        raise HTTPException(status_code=404, detail="Photo introuvable")
    return target


# Visuel de repli quand la photo déposée a disparu (stockage local éphémère
# après un redéploiement). Le domaine donne la teinte, jamais une donnée
# inventée : titre, entreprise et lieu viennent uniquement de l'offre.
_TONE_PALETTES = (
    (("informatique", "numérique", "numerique", "digital", "tech", "logiciel", "data"),
     ("#071f15", "#0a6b4c", "#7ff0c4")),
    (("santé", "sante", "soin", "médical", "medical", "pharma"),
     ("#062a2a", "#0f766e", "#5eead4")),
    (("finance", "banque", "comptab", "assurance", "audit"),
     ("#1f1a07", "#8a6d1f", "#f5c26b")),
    (("éducation", "education", "formation", "enseignement", "école", "ecole"),
     ("#0b1e3a", "#1d4ed8", "#93c5fd")),
    (("bâtiment", "batiment", "construction", "industrie", "mécanique",
      "mecanique", "énergie", "energie"),
     ("#1c1917", "#9a3412", "#fdba74")),
    (("commerce", "vente", "marketing", "communication", "clientèle", "clientele"),
     ("#2a0a2e", "#a21caf", "#f0abfc")),
    (("ong", "international", "humanitaire", "social", "association"),
     ("#06281f", "#0f766e", "#fcd34d")),
    (("transport", "logistique", "supply", "achat"),
     ("#0c1a2b", "#0369a1", "#7dd3fc")),
    (("agriculture", "agro", "environnement", "forêt", "foret"),
     ("#14200a", "#4d7c0f", "#bef264")),
    (("droit", "justice", "administration", "public", "juridique"),
     ("#1a1a2e", "#4338ca", "#c7d2fe")),
)


def _palette(label: str) -> tuple[str, str, str]:
    normalized = (label or "").lower()
    for keywords, colors in _TONE_PALETTES:
        if any(keyword in normalized for keyword in keywords):
            return colors
    return ("#071f15", "#0a6b4c", "#f5c26b")


def _wrap(value: str, max_chars: int, max_lines: int = 3) -> list[str]:
    words = (value or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if not lines:
        lines = [""]
    if len(lines) == max_lines and len(" ".join(words)) > len(" ".join(lines)):
        lines[-1] = lines[-1].rstrip(".") + "..."
    return lines


def _initials(name: str) -> str:
    parts = [part for part in (name or "?").split() if part]
    return "".join(part[0] for part in parts)[:2].upper() or "?"


def default_svg(job, domain_name: str = "", public_url: str = "") -> str:
    """Visuel paysage autonome, utilisé si le fichier photo est introuvable."""
    label = domain_name or getattr(job, "sector", "") or "Opportunité"
    start, end, accent = _palette(label)
    title_lines = _wrap(getattr(job, "title", "") or "Offre à pourvoir", 34, 3)
    title_y = {1: 320, 2: 290}.get(len(title_lines), 260)
    meta = " · ".join(
        value for value in (
            getattr(job, "company", ""),
            getattr(job, "location", ""),
            getattr(job, "contract_type", ""),
        ) if value
    )
    meta_y = title_y + (len(title_lines) - 1) * 60 + 46
    pill_width = max(180, min(460, 48 + len(label) * 13))
    url = public_url or (
        f"{config.PUBLIC_BASE_URL.rstrip('/')}/postuler/{getattr(job, 'id', '')}"
    )
    title_block = "".join(
        f'<text x="72" y="{title_y + index * 60}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="54" '
        f'font-weight="700" fill="#ffffff">{escape(line)}</text>'
        for index, line in enumerate(title_lines)
    )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800" role="img" aria-label="{escape(f"Visuel de l'offre {getattr(job, 'title', '')}")}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{start}"/>
      <stop offset="0.55" stop-color="{end}"/>
      <stop offset="1" stop-color="{start}"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.18" cy="0.12" r="0.85">
      <stop offset="0" stop-color="{accent}" stop-opacity="0.32"/>
      <stop offset="1" stop-color="{accent}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="800" fill="url(#bg)"/>
  <rect width="1200" height="800" fill="url(#glow)"/>
  <circle cx="1080" cy="120" r="220" fill="{accent}" fill-opacity="0.08"/>
  <circle cx="1020" cy="640" r="160" fill="{accent}" fill-opacity="0.06"/>
  <rect x="0" y="0" width="1200" height="10" fill="{accent}"/>

  <text x="72" y="86" font-family="Arial, Helvetica, sans-serif" font-size="40" font-weight="700" fill="#ffffff">OrientSkill AI</text>
  <text x="72" y="118" font-family="Arial, Helvetica, sans-serif" font-size="19" font-weight="400" fill="{accent}">Intelligence professionnelle</text>

  <rect x="72" y="160" width="{pill_width}" height="44" rx="22" fill="{accent}" fill-opacity="0.16" stroke="{accent}" stroke-opacity="0.5"/>
  <text x="96" y="189" font-family="Arial, Helvetica, sans-serif" font-size="18" font-weight="700" letter-spacing="1" fill="{accent}">{escape(label)}</text>

  {title_block}
  <text x="72" y="{meta_y}" font-family="Arial, Helvetica, sans-serif" font-size="24" font-weight="400" fill="#d7f8e9">{escape(meta)}</text>

  <circle cx="1020" cy="620" r="100" fill="{accent}" fill-opacity="0.12" stroke="{accent}" stroke-opacity="0.38"/>
  <text x="1020" y="655" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="64" font-weight="700" fill="{accent}">{escape(_initials(getattr(job, 'company', '')))}</text>

  <text x="72" y="716" font-family="Arial, Helvetica, sans-serif" font-size="20" font-weight="700" fill="#ffffff">Offre publiée sur OrientSkill AI</text>
  <text x="72" y="750" font-family="Arial, Helvetica, sans-serif" font-size="18" font-weight="400" fill="#bff3dd">{escape(url)}</text>
</svg>
'''
