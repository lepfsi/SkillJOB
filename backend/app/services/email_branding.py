"""Charte visuelle commune des e-mails OrientSkill AI.

Un seul gabarit HTML, compatible Gmail, Outlook et mobile : tableaux,
styles en ligne, aucune image externe, largeur maximale de 640 px. Le
texte brut reste la version de repli. Deux couleurs d'accent seulement :
le vert institutionnel et l'orange brûlé. Les gris et blancs sont des
neutres de structure.
"""
from __future__ import annotations

import html
import re
from typing import Optional

from app import config

BRAND_NAME = "OrientSkill AI"
BRAND_TAGLINE = "Intelligence professionnelle"
BRAND_GREEN = "#0a6b4c"
BRAND_GREEN_DARK = "#073d2b"
BRAND_ORANGE = "#b45309"
BRAND_BG = "#f4f7f5"
BRAND_BORDER = "#dbe3df"
BRAND_TEXT = "#16211c"
BRAND_MUTED = "#5b6a63"
SIGNATURE_MARKER = f"{BRAND_NAME} · {BRAND_TAGLINE}"

_LINK_RE = re.compile(
    r"(https?://[^\s<]+)"
    r"|([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})"
)
_SIGNATURE_RE = re.compile(
    r"\n\n--\n" + re.escape(SIGNATURE_MARKER) + r"\n\S+\s*$"
)


def base_url() -> str:
    """URL publique utilisée dans la signature et les liens de pied."""
    return config.PUBLIC_BASE_URL.rstrip("/")


def ensure_signature(body: str) -> str:
    """Ajoute la signature commune au texte brut, sans doublon."""
    text = (body or "").replace("\r\n", "\n").rstrip()
    if SIGNATURE_MARKER in text:
        return text
    return f"{text}\n\n--\n{SIGNATURE_MARKER}\n{base_url()}"


def _linkify(text: str) -> str:
    """Transforme les URL et adresses e-mail en liens accessibles."""

    def replace(match: re.Match[str]) -> str:
        url, email = match.group(1), match.group(2)
        if url:
            return (
                f'<a href="{url}" style="color:{BRAND_GREEN};'
                f'text-decoration:underline;">{url}</a>'
            )
        return (
            f'<a href="mailto:{email}" style="color:{BRAND_GREEN};'
            f'text-decoration:underline;">{email}</a>'
        )

    return _LINK_RE.sub(replace, text)


def _inline(text: str) -> str:
    """Échappe le texte, lie les URL et conserve les retours à la ligne."""
    escaped = html.escape(text, quote=True)
    return _linkify(escaped).replace("\n", "<br>")


def _footer_html(text: str) -> str:
    """Pied de page : libellés courts pour les liens longs.

    Les lignes du type ``Gérer mes préférences : https://...`` deviennent
    un lien dont le texte est le libellé, ce qui évite les URL brutes qui
    débordent sur mobile.
    """
    lines: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        label, separator, url = line.partition(" : ")
        if separator and url.startswith("http"):
            lines.append(
                f'<a href="{html.escape(url, quote=True)}" '
                f'style="color:{BRAND_GREEN};text-decoration:underline;">'
                f"{html.escape(label, quote=True)}</a>"
            )
        else:
            lines.append(_inline(line))
    return "<br>".join(lines)


def _paragraphs(text: str) -> str:
    blocks = [
        block.strip()
        for block in re.split(r"\n\s*\n", text or "")
        if block.strip()
    ]
    if not blocks:
        return ""
    return "".join(
        '<p style="margin:0 0 14px;font-family:Arial,Helvetica,sans-serif;'
        f'font-size:15px;line-height:1.65;color:{BRAND_TEXT};">'
        f"{_inline(block)}</p>"
        for block in blocks
    )


def _split_footer(body: str) -> tuple[str, str]:
    marker = "\n---\n"
    if marker in body:
        content, footer = body.split(marker, 1)
        return content, footer.strip()
    return body, ""


def _strip_signature(text: str) -> str:
    return _SIGNATURE_RE.sub("", text).strip()


def render_html(
    subject: str,
    body: str,
    footer: Optional[str] = None,
) -> str:
    """Rend un e-mail HTML complet à partir du corps texte.

    Le corps peut contenir un pied de page après ``---`` (préférences,
    désabonnement). La signature texte est retirée du contenu HTML : le
    gabarit affiche sa propre signature de marque.
    """
    text = (body or "").replace("\r\n", "\n")
    content, detected_footer = _split_footer(text)
    content = _strip_signature(content)
    footer_text = (
        detected_footer if footer is None else (footer or "").strip()
    )
    if not footer_text:
        footer_text = (
            "Cet e-mail concerne votre compte ou une candidature sur "
            "OrientSkill AI."
        )
    subject_text = subject or BRAND_NAME
    subject_html = html.escape(subject_text, quote=True)
    first_line = next(
        (line.strip() for line in content.splitlines() if line.strip()),
        subject_text,
    )
    preheader = html.escape(first_line[:140], quote=True)
    base = base_url()
    base_html = html.escape(base, quote=True)
    content_html = _paragraphs(content)
    footer_html = _footer_html(footer_text)

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="x-apple-disable-message-reformatting">
<title>{subject_html}</title>
</head>
<body style="margin:0;padding:0;background:{BRAND_BG};">
<div style="display:none;font-size:1px;color:{BRAND_BG};line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">{preheader}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BRAND_BG};">
<tr>
<td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;max-width:640px;background:#ffffff;border:1px solid {BRAND_BORDER};border-radius:8px;overflow:hidden;">
<tr>
<td style="background:{BRAND_GREEN_DARK};padding:20px 28px;border-bottom:3px solid {BRAND_ORANGE};">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:20px;font-weight:700;color:#ffffff;letter-spacing:0.2px;">{BRAND_NAME}</div>
<div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#d7efe4;margin-top:3px;">{BRAND_TAGLINE}</div>
</td>
</tr>
<tr>
<td style="padding:28px 28px 8px;">
<div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;font-weight:700;color:{BRAND_GREEN};text-transform:uppercase;letter-spacing:1.2px;margin-bottom:8px;">Notification</div>
<h1 style="font-family:Arial,Helvetica,sans-serif;font-size:22px;line-height:1.3;color:{BRAND_TEXT};margin:0 0 18px;word-break:break-word;overflow-wrap:anywhere;">{subject_html}</h1>
<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.65;color:{BRAND_TEXT};word-break:break-word;overflow-wrap:anywhere;">{content_html}</div>
</td>
</tr>
<tr>
<td style="padding:0 28px 24px;">
<div style="border-top:1px solid {BRAND_BORDER};padding-top:18px;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.6;color:{BRAND_MUTED};word-break:break-word;overflow-wrap:anywhere;">{footer_html}</div>
<div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.6;color:{BRAND_MUTED};margin-top:12px;">
<strong style="color:{BRAND_TEXT};">{BRAND_NAME}</strong> · {BRAND_TAGLINE}<br>
<a href="{base_html}" style="color:{BRAND_GREEN};text-decoration:none;">{base_html}</a>
</div>
</td>
</tr>
</table>
<div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;line-height:1.5;color:#7a8a82;margin-top:12px;">E-mail envoyé automatiquement par {BRAND_NAME}.</div>
</td>
</tr>
</table>
</body>
</html>"""
