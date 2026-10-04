"""Documents : CV ciblé, lettre, préparation entretien, export (§15-18).

Garantie « pas d'invention » (§47) : les documents sont construits
exclusivement à partir du profil validé via PUT /api/profile.
"""
import io
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services import cv_builder
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

router = APIRouter(tags=["documents"])


def _load_context(user: models.User, job_id: int, db: Session):
    """Profil validé + offre, avec erreurs métier explicites."""
    job = db.get(models.Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    if profile is None:
        raise HTTPException(
            status_code=400,
            detail="Profil requis : complétez votre profil (import CV ou "
                   "questionnaire) avant de générer un document.",
        )
    return profile, job


@router.post("/api/jobs/{job_id}/cv", response_model=schemas.DocumentOut)
def generate_cv(
    job_id: int,
    payload: schemas.CvGenerateIn | None = None,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """CV ciblé, modèle au choix : classique / ats / moderne (§16)."""
    profile, job = _load_context(user, job_id, db)
    template = payload.template if payload else "classique"
    if template not in schemas.CV_TEMPLATES:
        raise HTTPException(status_code=422, detail="Modèle de CV inconnu")
    content = cv_builder.build_targeted_cv(
        profile, job, user, load_taxonomy(), template=template
    )
    label = {"classique": "", "ats": "ATS · ", "moderne": "moderne · "}[template]
    document = models.Document(
        user_id=user.id,
        job_id=job.id,
        kind="cv",
        title=f"CV {label}ciblé · {job.title} · {job.company}",
        content_markdown=content,
        template=template,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/api/cv-templates", response_model=list[schemas.CvTemplateInfo])
def cv_templates():
    """Catalogue des modèles de CV proposés à la génération."""
    return cv_builder.list_templates()


@router.post("/api/jobs/{job_id}/cover-letter", response_model=schemas.DocumentOut)
def generate_cover_letter(
    job_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    profile, job = _load_context(user, job_id, db)
    content = cv_builder.build_cover_letter(profile, job, user, load_taxonomy())
    document = models.Document(
        user_id=user.id,
        job_id=job.id,
        kind="cover_letter",
        title=f"Lettre de motivation · {job.title} · {job.company}",
        content_markdown=content,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.post("/api/jobs/{job_id}/interview-prep", response_model=schemas.InterviewPrepOut)
def generate_interview_prep(
    job_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    profile, job = _load_context(user, job_id, db)
    return cv_builder.build_interview_prep(profile, job, load_taxonomy())


@router.get("/api/documents", response_model=list[schemas.DocumentOut])
def list_documents(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(models.Document)
        .filter(models.Document.user_id == user.id)
        .order_by(models.Document.created_at.desc())
        .all()
    )


@router.get("/api/documents/{document_id}", response_model=schemas.DocumentOut)
def get_document(
    document_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    return _get_owned_document(document_id, user, db)


@router.get("/api/documents/{document_id}/export")
def export_document(
    document_id: int,
    format: Literal["md", "pdf"] = "md",
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    document = _get_owned_document(document_id, user, db)
    import unicodedata

    ascii_title = unicodedata.normalize("NFKD", document.title)
    ascii_title = "".join(c for c in ascii_title if not unicodedata.combining(c))
    safe_title = "".join(c if c.isascii() and (c.isalnum() or c in " -_") else "_"
                         for c in ascii_title).strip("_") or "document"

    if format == "pdf":
        # Rendu dédié A4 (CV / lettre) depuis le profil validé ; sinon
        # rendu générique du markdown.
        content_bytes = None
        if document.job_id:
            job = db.get(models.Job, document.job_id)
            profile = profile_to_dict(get_profile_row(db, user.id), user.id)
            if job is not None and profile:
                taxonomy = load_taxonomy()
                if document.kind == "cv":
                    content_bytes = cv_pdf.build_cv_pdf(
                        profile, job, user, taxonomy, template=document.template or "classique"
                    )
                else:
                    content_bytes = cv_pdf.build_letter_pdf(profile, job, user, taxonomy)
        if content_bytes is not None:
            return Response(
                content=content_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
            )
        if HAS_REPORTLAB:
            return Response(
                content=_render_pdf(document.title, document.content_markdown),
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
            )
    # PDF demandé sans reportlab -> markdown (contrat §7)
    return Response(
        content=document.content_markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
    )


def _get_owned_document(document_id: int, user: models.User, db: Session) -> models.Document:
    document = db.get(models.Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable")
    if document.user_id != user.id:
        raise HTTPException(status_code=403, detail="Accès interdit")
    return document


def _render_pdf(title: str, markdown: str) -> bytes:
    """Rendu PDF simple depuis le markdown (titres, listes, paragraphes)."""
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=title)
    story = []
    for line in markdown.split("\n"):
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
