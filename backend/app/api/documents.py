"""Documents : CV ciblé, lettre, préparation entretien, export (§15-18).

Garantie « pas d'invention » (§47) : les documents sont construits
exclusivement à partir du profil validé via PUT /api/profile.
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
from app.services import cv_builder
from app.services.document_pdf import build_document_pdf
from app.services.document_pdf import with_domains as _with_domains
from app.services.profile_store import get_profile_row, profile_to_dict
from app.services.skills_taxonomy import load_taxonomy

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
    return _with_domains(profile, db), job


def _validate_accent(accent: Optional[str]) -> Optional[str]:
    """Couleur d'accent du candidat ; inconnue -> 422 explicite.

    Accepte le catalogue nommé et une couleur personnalisée ``#RRGGBB``.
    """
    if accent is None or str(accent).strip() == "":
        return None
    value = str(accent).strip()
    if cv_builder.is_custom_accent(value):
        return value.upper()
    key = value.lower()
    if key in cv_builder.ACCENTS:
        return key
    raise HTTPException(
        status_code=422,
        detail=(
            "Couleur d'accent inconnue : "
            + ", ".join(cv_builder.ACCENTS)
            + " ou une couleur #RRGGBB."
        ),
    )


@router.post("/api/jobs/{job_id}/cv", response_model=schemas.DocumentOut)
def generate_cv(
    job_id: int,
    payload: schemas.CvGenerateIn | None = None,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """CV ciblé, modèle et couleur au choix (§16). Six modèles :
    classique, ats, moderne, deux_colonnes, elegant, compact."""
    profile, job = _load_context(user, job_id, db)
    template = payload.template if payload else "classique"
    if template not in schemas.CV_TEMPLATES:
        raise HTTPException(status_code=422, detail="Modèle de CV inconnu")
    accent = _validate_accent(payload.accent if payload else None)
    content = cv_builder.build_targeted_cv(
        profile, job, user, load_taxonomy(), template=template
    )
    label = cv_builder.TEMPLATE_LABELS.get(template, "")
    document = models.Document(
        user_id=user.id,
        job_id=job.id,
        kind="cv",
        title=f"CV {label}ciblé · {job.title} · {job.company}",
        content_markdown=content,
        source_profile=profile,
        template=template,
        accent=accent,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("/api/cv-templates", response_model=list[schemas.CvTemplateInfo])
def cv_templates():
    """Catalogue des modèles de CV proposés à la génération."""
    return cv_builder.list_templates()


@router.get("/api/letter-templates", response_model=list[schemas.LetterTemplateInfo])
def letter_templates():
    """Catalogue des modèles de lettre de motivation."""
    return cv_builder.list_letter_templates()


@router.post("/api/cv", response_model=schemas.DocumentOut)
def generate_general_cv(
    payload: schemas.CvGenerateIn | None = None,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """CV GÉNÉRALISTE (aucune offre ciblée) : le profil complet, honnête.

    Compétences triées par preuves, expériences chronologiques, aucune
    réorganisation « pour une offre » puisqu'il n'y en a pas (§47).
    """
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    if profile is None:
        raise HTTPException(
            status_code=400,
            detail="Profil requis : complétez votre profil (import CV ou "
                   "questionnaire) avant de générer un document.",
        )
    profile = _with_domains(profile, db)
    template = payload.template if payload else "classique"
    if template not in schemas.CV_TEMPLATES:
        raise HTTPException(status_code=422, detail="Modèle de CV inconnu")
    accent = _validate_accent(payload.accent if payload else None)
    content = cv_builder.build_general_cv(profile, user, load_taxonomy(), template)
    name = next((t["name"] for t in cv_builder.list_templates() if t["id"] == template), template)
    document = models.Document(
        user_id=user.id,
        kind="cv",
        title=f"CV généraliste · {name}",
        content_markdown=content,
        source_profile=profile,
        template=template,
        accent=accent,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.post("/api/letter", response_model=schemas.DocumentOut)
def generate_general_letter(
    payload: schemas.CoverLetterIn | None = None,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """LETTRE GÉNÉRALISTE (aucune offre ciblée) : le destinataire reste à
    compléter ([Nom de l'entreprise], [Ville]), aucune coordonnée inventée.
    Le corps ne contient que les faits du profil validé (§47)."""
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    if profile is None:
        raise HTTPException(
            status_code=400,
            detail="Profil requis : complétez votre profil (import CV ou "
                   "questionnaire) avant de générer un document.",
        )
    template = payload.template if payload else "classique"
    if template not in schemas.LETTER_TEMPLATES:
        raise HTTPException(status_code=422, detail="Modèle de lettre inconnu")
    accent = _validate_accent(payload.accent if payload else None)
    content = cv_builder.build_general_letter(profile, user, load_taxonomy(), template)
    name = next(
        (t["name"] for t in cv_builder.list_letter_templates() if t["id"] == template),
        template,
    )
    document = models.Document(
        user_id=user.id,
        kind="cover_letter",
        title=f"Lettre généraliste · {name}",
        content_markdown=content,
        template=template,
        accent=accent,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.post("/api/jobs/{job_id}/cover-letter", response_model=schemas.DocumentOut)
def generate_cover_letter(
    job_id: int,
    payload: schemas.CoverLetterIn | None = None,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Lettre de motivation, modèle au choix : classique / moderne /
    email (§17). Mêmes faits, autre mise en page."""
    profile, job = _load_context(user, job_id, db)
    template = payload.template if payload else "classique"
    if template not in schemas.LETTER_TEMPLATES:
        raise HTTPException(status_code=422, detail="Modèle de lettre inconnu")
    accent = _validate_accent(payload.accent if payload else None)
    content = cv_builder.build_cover_letter(
        profile, job, user, load_taxonomy(), template=template
    )
    document = models.Document(
        user_id=user.id,
        job_id=job.id,
        kind="cover_letter",
        title=f"Lettre de motivation · {job.title} · {job.company}",
        content_markdown=content,
        template=template,
        accent=accent,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.post("/api/documents/{document_id}/refresh", response_model=schemas.DocumentOut)
def refresh_document(
    document_id: int,
    payload: schemas.CvGenerateIn | None = None,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Met à jour un document : régénéré depuis le profil VALIDÉ au moment
    de l'appel, avec le modèle et la couleur demandés (par défaut : les
    mêmes que le document existant). Rien n'est jamais inventé (§47)."""
    document = _get_owned_document(document_id, user, db)
    profile = profile_to_dict(get_profile_row(db, user.id), user.id)
    if profile is None:
        raise HTTPException(
            status_code=400,
            detail="Profil requis : complétez votre profil avant de "
                   "régénérer un document.",
        )
    profile = _with_domains(profile, db)
    if document.kind not in ("cv", "cover_letter"):
        raise HTTPException(
            status_code=400,
            detail="Ce document ne se régénère pas : seul un CV ou une lettre "
                   "se met à jour depuis le profil.",
        )
    taxonomy = load_taxonomy()
    template = (payload.template if payload and payload.template else None) \
        or document.template or "classique"
    accent = _validate_accent(payload.accent) if payload and payload.accent else document.accent

    if document.kind == "cv":
        if template not in schemas.CV_TEMPLATES:
            raise HTTPException(status_code=422, detail="Modèle de CV inconnu")
        job = db.get(models.Job, document.job_id) if document.job_id else None
        if job is not None:
            content = cv_builder.build_targeted_cv(
                profile, job, user, taxonomy, template=template
            )
            label = cv_builder.TEMPLATE_LABELS.get(template, "")
            document.title = f"CV {label}ciblé · {job.title} · {job.company}"
        else:
            content = cv_builder.build_general_cv(profile, user, taxonomy, template)
            name = next(
                (t["name"] for t in cv_builder.list_templates() if t["id"] == template),
                template,
            )
            document.title = f"CV généraliste · {name}"
    else:
        if template not in schemas.LETTER_TEMPLATES:
            raise HTTPException(status_code=422, detail="Modèle de lettre inconnu")
        job = db.get(models.Job, document.job_id) if document.job_id else None
        content = cv_builder.build_cover_letter(
            profile, job, user, taxonomy, template=template
        )
        if job is not None:
            document.title = f"Lettre de motivation · {job.title} · {job.company}"
        else:
            name = next(
                (t["name"] for t in cv_builder.list_letter_templates()
                 if t["id"] == template),
                template,
            )
            document.title = f"Lettre généraliste · {name}"

    document.content_markdown = content
    if document.kind == "cv":
        # L'instantané suit la régénération : réimporter ce CV restitue
        # exactement le profil validé qui a servi à le produire.
        document.source_profile = profile
    document.template = template
    document.accent = accent
    db.commit()
    db.refresh(document)
    return document


@router.delete("/api/documents/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Supprime définitivement un document de l'utilisateur (204)."""
    document = _get_owned_document(document_id, user, db)
    # Un CV partagé qui disparaît ne doit jamais laisser un lien mort côté
    # recruteur : le partage est désactivé en même temps.
    if user.shared_cv_id == document.id:
        user.shared_cv_id = None
        user.cv_visible_to_recruiters = False
    db.delete(document)
    db.commit()
    return Response(status_code=204)


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
    from app.services.document_pdf import safe_pdf_filename

    safe_title = safe_pdf_filename(document.title)[:-4]

    if format == "pdf":
        # Rendu dédié A4 (CV / lettre) depuis le profil validé ; sinon
        # rendu générique du markdown. Source unique : document_pdf.
        content_bytes = build_document_pdf(db, document, user)
        if content_bytes is not None:
            return Response(
                content=content_bytes,
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
