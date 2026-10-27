"""Visuel public de candidature par e-mail (LinkedIn, WhatsApp, etc.).

Le fichier est un SVG autonome de 1200 x 1500 : il ne dépend d'aucune
ressource externe et peut être converti en PNG dans le navigateur pour
être publié sur LinkedIn. Toutes les informations viennent de l'offre et
de la configuration de la boîte interne : rien n'est inventé.
"""
from html import escape
from typing import Iterable


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


def _text_block(
    lines: Iterable[str],
    x: int,
    y: int,
    size: int,
    fill: str,
    weight: int = 700,
    line_height: float = 1.12,
) -> str:
    return "".join(
        f'<text x="{x}" y="{int(y + index * size * line_height)}" '
        f'font-family="Arial, Helvetica, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}">{escape(line)}</text>'
        for index, line in enumerate(lines)
    )


def build_svg(
    job,
    address: str,
    reference: str,
    public_url: str,
) -> str:
    title_lines = _wrap(job.title, 28, max_lines=3)
    company_lines = _wrap(job.company, 38, max_lines=2)
    subject = f"CANDIDATURE {reference} - {job.title}"
    subject_lines = _wrap(subject, 48, max_lines=3)
    title_y = {1: 550, 2: 520}.get(len(title_lines), 500)
    meta_y = title_y + (len(title_lines) - 1) * 69 + 42

    meta = [
        value for value in (job.location, job.contract_type, job.sector)
        if value
    ]
    meta_pills = []
    x = 100
    count = max(1, len(meta))
    max_width = min(430, (1000 - 16 * (count - 1)) // count)
    for value in meta:
        width = max(140, min(max_width, 28 + len(value) * 13))
        label = value if len(value) <= 26 else f"{value[:24]}…"
        meta_pills.append(
            f'<rect x="{x}" y="{meta_y}" width="{width}" height="52" rx="26" '
            f'fill="#ffffff" fill-opacity="0.12" stroke="#7ff0c4" '
            f'stroke-opacity="0.45"/>'
            f'<text x="{x + 24}" y="{meta_y + 35}" '
            f'font-family="Arial, Helvetica, sans-serif" font-size="23" '
            f'font-weight="600" fill="#d7f8e9">{escape(label)}</text>'
        )
        x += width + 16

    has_email = bool(address.strip())
    badge_text = "CANDIDATURE PAR E-MAIL" if has_email else "CANDIDATURE EN LIGNE"
    badge_width = 420 if has_email else 380

    if has_email:
        email_size = 52 if len(address) <= 30 else 42 if len(address) <= 38 else 34
        subject_y = 1072
        subject_block = _text_block(
            subject_lines, 150, subject_y, 32, "#0a5c42", weight=700
        )
        card_content = f'''
  <rect x="80" y="800" width="1040" height="530" rx="30" fill="#ffffff"/>
  <text x="150" y="875" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="400" fill="#4b5f57">Envoyez votre CV et votre lettre à</text>
  <text x="150" y="945" font-family="Arial, Helvetica, sans-serif" font-size="{email_size}" font-weight="700" fill="#0a6b4c">{escape(address)}</text>

  <rect x="150" y="990" width="900" height="2" fill="#dbe9e2"/>
  <text x="150" y="1030" font-family="Arial, Helvetica, sans-serif" font-size="25" font-weight="700" letter-spacing="1" fill="#6b7f76">OBJET CONSEILLÉ</text>
  {subject_block}

  <rect x="150" y="1175" width="900" height="95" rx="14" fill="#f2faf6"/>
  <text x="176" y="1212" font-family="Arial, Helvetica, sans-serif" font-size="22" font-weight="700" fill="#0a5c42">La référence dans l'objet permet de transmettre votre candidature</text>
  <text x="176" y="1246" font-family="Arial, Helvetica, sans-serif" font-size="22" font-weight="400" fill="#4b5f57">à la bonne entreprise, sans délai et sans perte de pièce jointe.</text>
'''
    else:
        url_lines = _wrap(public_url, 46, max_lines=2)
        url_size = 38 if len(url_lines) == 1 else 30
        url_block = _text_block(
            url_lines, 150, 940, url_size, "#0a6b4c", weight=700, line_height=1.18
        )
        card_content = f'''
  <rect x="80" y="800" width="1040" height="530" rx="30" fill="#ffffff"/>
  <text x="150" y="875" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="400" fill="#4b5f57">Postulez directement depuis la fiche de l'offre</text>
  {url_block}

  <rect x="150" y="1015" width="900" height="2" fill="#dbe9e2"/>
  <text x="150" y="1055" font-family="Arial, Helvetica, sans-serif" font-size="25" font-weight="700" letter-spacing="1" fill="#6b7f76">CANDIDATURE EN LIGNE</text>
  <text x="150" y="1098" font-family="Arial, Helvetica, sans-serif" font-size="23" font-weight="400" fill="#4b5f57">Ouvrez le lien, vérifiez les détails de l'offre et envoyez</text>
  <text x="150" y="1132" font-family="Arial, Helvetica, sans-serif" font-size="23" font-weight="400" fill="#4b5f57">votre candidature en quelques minutes.</text>

  <rect x="150" y="1175" width="900" height="95" rx="14" fill="#f2faf6"/>
  <text x="176" y="1212" font-family="Arial, Helvetica, sans-serif" font-size="22" font-weight="700" fill="#0a5c42">Aucune adresse e-mail n'est nécessaire : la candidature est</text>
  <text x="176" y="1246" font-family="Arial, Helvetica, sans-serif" font-size="22" font-weight="400" fill="#4b5f57">enregistrée dans votre espace OrientSkill AI.</text>
'''

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="1500" viewBox="0 0 1200 1500">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#071f15"/>
      <stop offset="0.55" stop-color="#0c3927"/>
      <stop offset="1" stop-color="#0a6b4c"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#7ff0c4"/>
      <stop offset="1" stop-color="#f5c26b"/>
    </linearGradient>
  </defs>
  <rect width="1200" height="1500" fill="url(#bg)"/>
  <circle cx="1110" cy="120" r="230" fill="#7ff0c4" fill-opacity="0.06"/>
  <circle cx="1040" cy="1380" r="300" fill="#f5c26b" fill-opacity="0.05"/>
  <rect x="0" y="0" width="1200" height="12" fill="url(#accent)"/>

  <text x="100" y="120" font-family="Arial, Helvetica, sans-serif" font-size="54" font-weight="700" fill="#ffffff">OrientSkill AI</text>
  <text x="100" y="160" font-family="Arial, Helvetica, sans-serif" font-size="22" font-weight="400" fill="#bff3dd">Intelligence professionnelle</text>

  <rect x="100" y="220" width="{badge_width}" height="52" rx="26" fill="#7ff0c4"/>
  <text x="126" y="254" font-family="Arial, Helvetica, sans-serif" font-size="20" font-weight="700" letter-spacing="2" fill="#063d2b">{badge_text}</text>

  <text x="100" y="340" font-family="Arial, Helvetica, sans-serif" font-size="30" font-weight="400" fill="#bff3dd">Rejoignez</text>
  {_text_block(company_lines, 100, 400, 52, "#ffffff", weight=700, line_height=1.08)}
  {_text_block(title_lines, 100, title_y, 64, "#ffffff", weight=700, line_height=1.08)}
  {''.join(meta_pills)}

  {card_content}

  <text x="100" y="1370" font-family="Arial, Helvetica, sans-serif" font-size="24" font-weight="700" fill="#ffffff">OrientSkill AI</text>
  <text x="100" y="1406" font-family="Arial, Helvetica, sans-serif" font-size="20" font-weight="400" fill="#bff3dd">{escape(public_url)}</text>
  <text x="100" y="1450" font-family="Arial, Helvetica, sans-serif" font-size="18" font-weight="400" fill="#7fa99a">Visuel généré depuis la fiche de l'offre. Aucune donnée inventée.</text>
</svg>
'''
