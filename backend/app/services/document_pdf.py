"""Rendu PDF des documents du candidat (CV, lettre, générique).

Source unique de vérité du rendu : la console de documents et la
transmission automatique des candidatures produisent exactement le même
PDF. Le contenu vient toujours du profil validé (aucune invention, §47).
"""
import io
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.services.profile_store import get_profile_row, profile_to_dict
from app.services.skills_taxonomy import load_taxonomy

try:  # reportlab requis pour l'export PDF (cf. requirements.txt)
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from app.services import cv_pdf
    HAS_REPORTLAB = True
except ImportError:  # pragma: no cover
    HAS_REPORTLAB = False


def with_domains(profile: dict, db: Session) -> dict:
    """Ajoute les libellés du référentiel au profil transmis aux documents.

    L'instantané conserve ``domain_id`` / ``specialty_ids`` ; les libellés
    ne servent qu'à l'en-tête ATS et au PDF. Aucune donnée inventée : les
    identifiants absents ou inconnus restent sans libellé.
    """
    from app.services.domains import resolve_names

    prefs = dict(profile.get("preferences") or {})
    domain_name, specialty_names = resolve_names(
        db, prefs.get("domain_id"), prefs.get("specialty_ids")
    )
    if not domain_name and not specialty_names:
        return profile
    prefs["domain_name"] = domain_name
    prefs["specialty_names"] = specialty_names
    return {**profile, "preferences": prefs}


def build_document_pdf(
    db: Session, document: models.Document, user: models.User
) -> Optional[bytes]:
    """PDF du document ; None si reportlab est indisponible.

    CV et lettre sont rendus depuis le profil validé, avec le modèle et
    la couleur d'accent choisis par le candidat. Les autres documents
    (préparation d'entretien...) passent par le rendu markdown générique.
    """
    if not HAS_REPORTLAB:
        return None
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    if profile:
        profile = with_domains(profile, db)
        taxonomy = load_taxonomy()
        job = db.get(models.Job, document.job_id) if document.job_id else None
        if document.kind == "cv" and (job is not None or not document.job_id):
            # CV ciblé (offre liée) ou GÉNÉRALISTE (sans offre).
            return cv_pdf.build_cv_pdf(
                profile, job, user, taxonomy,
                template=document.template or "classique",
                accent=document.accent,
            )
        if document.kind == "cover_letter" and (job is not None or not document.job_id):
            # Lettre ciblée, ou GÉNÉRALISTE (destinataire à compléter).
            return cv_pdf.build_letter_pdf(
                profile, job, user, taxonomy,
                template=document.template or "classique",
                accent=document.accent,
            )
    return render_pdf(document.title, document.content_markdown)


def safe_pdf_filename(title: str) -> str:
    """Nom de fichier ASCII sûr pour une pièce jointe PDF."""
    import unicodedata

    ascii_title = unicodedata.normalize("NFKD", title or "document")
    ascii_title = "".join(c for c in ascii_title if not unicodedata.combining(c))
    clean = "".join(
        c if c.isascii() and (c.isalnum() or c in " -_") else "_"
        for c in ascii_title
    ).strip("_")
    return (clean or "document") + ".pdf"


def render_pdf(title: str, markdown: str) -> bytes:
    """Rendu PDF simple depuis le markdown (titres, listes, paragraphes)."""
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=title)
    story = []
    for line in (markdown or "").split("\n"):
        text = line.strip()
        if not text:
            story.append(Spacer(1, 6))
            continue
        style = styles["BodyText"]
        if text.startswith("### "):
            text, style = text[4:], styles["Heading3"]
        elif text.startswith("## "):
            text, style = text[3:], styles["Heading2"]
        elif text.startswith("# "):
            text, style = text[2:], styles["Heading1"]
        elif text.startswith("- "):
            text = "• " + text[2:]
        text = text.replace("**", "").replace("*", "")
        story.append(Paragraph(text, style))
    doc.build(story)
    return buffer.getvalue()
