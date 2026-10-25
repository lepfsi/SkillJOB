"""Profile Engine : profil maître, import CV, questionnaire, photo et
vérification de profil (§7.1, §9ter).
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import config, models, schemas, security
from app.database import get_db
from app.services import uploads
from app.services import cv_extractor, profile_store, questionnaire

router = APIRouter(prefix="/api/profile", tags=["profile"])
questionnaire_router = APIRouter(prefix="/api/questionnaire", tags=["questionnaire"])

UPLOAD_DIR = config.UPLOAD_DIR
PHOTO_DIR = UPLOAD_DIR / "photos"
VERIFY_DIR = UPLOAD_DIR / "verification"

_ALLOWED_PHOTO = {".jpg", ".jpeg", ".png", ".webp"}
_MAX_BYTES = 5 * 1024 * 1024


def _save_upload(file: UploadFile, target_dir: Path, stem: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_PHOTO:
        raise HTTPException(status_code=400, detail="Format accepté : JPG, PNG ou WebP")
    data = file.file.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=400, detail="Fichier trop volumineux (5 Mo maximum)")
    if not data:
        raise HTTPException(status_code=400, detail="Fichier vide")
    # Remplace tout fichier précédent du même utilisateur
    for old in target_dir.glob(f"{stem}.*"):
        old.unlink(missing_ok=True)
    path = target_dir / f"{stem}{ext}"
    path.write_bytes(data)
    return path


@router.post("/photo", response_model=schemas.UserOut)
async def upload_photo(
    file: UploadFile,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Photo de profil : affichée sur le profil et intégrée aux CV PDF."""
    path = _save_upload(file, PHOTO_DIR, f"user_{user.id}")
    user.photo_path = uploads.store(path)
    db.commit()
    db.refresh(user)
    return user


@router.get("/photo")
def get_photo(user: models.User = Depends(security.get_current_user)):
    """Sert la photo de l'utilisateur connecté (avec en-tête d'autorisation)."""
    if not user.photo_path:
        raise HTTPException(status_code=404, detail="Aucune photo")
    full = uploads.resolve(user.photo_path)
    if not full.exists():
        raise HTTPException(status_code=404, detail="Photo introuvable")
    return FileResponse(full)


@router.post("/verification/request", response_model=schemas.VerificationStatusOut)
async def request_verification(
    file: UploadFile,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Vérification de profil « à notre manière » : dépôt d'une pièce
    d'identité (CNI / passeport) examinée par un administrateur. L'objectif :
    lutter contre les faux comptes et valoriser les profils authentiques.
    Le document est conservé uniquement le temps de l'examen."""
    if user.verification_status == "verified":
        raise HTTPException(status_code=400, detail="Profil déjà vérifié")
    path = _save_upload(file, VERIFY_DIR, f"idcheck_user_{user.id}")
    user.identity_doc_path = uploads.store(path)
    user.verification_status = "pending"
    db.commit()
    return {
        "status": user.verification_status,
        "requested_at": None,
        "note": user.verification_note,
    }


@router.get("/verification", response_model=schemas.VerificationStatusOut)
def verification_status(user: models.User = Depends(security.get_current_user)):
    return {
        "status": user.verification_status or "none",
        "requested_at": user.verified_at,
        "note": user.verification_note,
    }


# ------------------------------------- CV généraliste partagé (recruteurs)

def _shared_cv_or_none(
    db: Session, user: models.User
) -> models.Document | None:
    """CV réellement partageable : document du candidat, CV généraliste."""
    if not user.cv_visible_to_recruiters or not user.shared_cv_id:
        return None
    document = db.get(models.Document, user.shared_cv_id)
    if document is None:
        return None
    if document.user_id != user.id:
        return None
    if document.kind != "cv" or document.job_id is not None:
        return None
    return document


def _cv_visibility_payload(
    db: Session, user: models.User, requested: bool | None = None
) -> dict:
    document = _shared_cv_or_none(db, user)
    visible = bool(document is not None)
    return {
        "visible": visible if requested is None else requested,
        "document_id": document.id if document else None,
        "document": (
            schemas.DocumentOut.model_validate(document) if document else None
        ),
    }


@router.get("/cv-visibility", response_model=schemas.CvVisibilityOut)
def get_cv_visibility(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """État du partage du CV généraliste avec les recruteurs.

    Le recruteur ne verra que le document explicitement choisi ici ; un CV
    ciblé sur une offre ne peut pas être partagé par ce canal.
    """
    return _cv_visibility_payload(db, user)


@router.put("/cv-visibility", response_model=schemas.CvVisibilityOut)
def set_cv_visibility(
    payload: schemas.CvVisibilityIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.visible:
        user.cv_visible_to_recruiters = False
        user.shared_cv_id = None
        db.commit()
        return _cv_visibility_payload(db, user)

    if payload.document_id is None:
        raise HTTPException(
            status_code=422,
            detail="Choisissez un CV généraliste à partager avec les recruteurs.",
        )
    document = db.get(models.Document, payload.document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable")
    if document.user_id != user.id:
        raise HTTPException(status_code=403, detail="Ce document ne vous appartient pas")
    if document.kind != "cv" or document.job_id is not None:
        raise HTTPException(
            status_code=422,
            detail="Seul un CV généraliste peut être partagé avec les recruteurs.",
        )
    user.cv_visible_to_recruiters = True
    user.shared_cv_id = document.id
    db.commit()
    db.refresh(user)
    return _cv_visibility_payload(db, user, requested=True)


# ------------------------------------------------ Notifications (§25)

def _prefs_out(user: models.User) -> dict:
    from app.services.notifications import normalize_prefs

    prefs = normalize_prefs(getattr(user, "notification_prefs", None) or {})
    # Catalogue des événements : libellés pour l'interface de réglage.
    from app.services.notifications import EVENT_TYPES

    prefs["event_types"] = EVENT_TYPES
    return prefs


@router.get("/notifications", response_model=dict)
def get_notifications(user: models.User = Depends(security.get_current_user)):
    return _prefs_out(user)


@router.put("/notifications", response_model=dict)
def update_notifications(
    payload: schemas.NotificationPrefsIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Canaux, coordonnées et choix PAR ÉVÉNEMENT de l'utilisateur :
    sans opt-in e-mail pour un événement, la notification reste dans
    l'application. Les identifiants des services (SMTP, bots) restent
    côté admin."""
    prefs = _prefs_out(user)
    incoming = payload.model_dump()
    events_incoming = incoming.pop("events", None) or {}
    for key, value in incoming.items():
        if value is not None:
            prefs[key] = value
    if events_incoming:
        merged = dict(prefs.get("events") or {})
        for key, value in events_incoming.items():
            if value is not None:
                merged[key] = bool(value)
        prefs["events"] = merged
    prefs.pop("event_types", None)  # jamais persisté
    user.notification_prefs = prefs
    db.commit()
    return _prefs_out(user)


@router.post("/notifications/test", response_model=list[dict])
def test_notifications(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Test d'envoi réel sur les canaux activés (détails retournés)."""
    from app.services.notifications import dispatch

    return dispatch(
        db, user,
        "OrientSkill AI : test de notification",
        "Ceci est un test de vos canaux de notification. Si vous le "
        "recevez, le canal concerné fonctionne.",
    )


@router.get("/telegram-chats", response_model=list[dict])
def telegram_chats(user: models.User = Depends(security.get_current_user)):
    """Chats récemment vus par le bot : aide l'utilisateur à retrouver
    son chat ID (il doit d'abord avoir envoyé /start au bot)."""
    from app.services.telegram_bot import SEEN_CHATS

    chats = [
        {"chat_id": c["chat_id"], "name": c["name"], "username": c["username"]}
        for c in SEEN_CHATS.values()
    ]
    chats.sort(key=lambda c: str(c["name"]))
    return chats


@router.get("", response_model=schemas.ProfileOut | None)
def get_profile(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    row = profile_store.get_profile_row(db, user.id)
    return profile_store.profile_to_dict(row, user.id)


@router.put("", response_model=schemas.ProfileOut)
def put_profile(
    payload: schemas.ProfileUpdate,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Validation humaine : seul ce endpoint enregistre le profil (§47)."""
    data = payload.model_dump(exclude_unset=True)
    row = profile_store.save_profile(db, user.id, data)
    return profile_store.profile_to_dict(row, user.id)


@router.post("/import-cv", response_model=schemas.DraftResponse)
async def import_cv(
    request: Request,
    user: models.User = Depends(security.get_current_user),
):
    """Extraction d'un brouillon de profil (NON enregistré, validation §47).

    Accepte JSON ``{"text": ...}`` ou multipart ``file`` (.pdf / .txt).
    """
    content_type = request.headers.get("content-type", "")
    text = ""
    if content_type.startswith("application/json"):
        body = await request.json()
        text = str((body or {}).get("text", ""))
    elif content_type.startswith(("multipart/form-data", "application/octet-stream")):
        form = await request.form()
        upload = form.get("file")
        if upload is None:
            raise HTTPException(status_code=422, detail="Champ 'file' manquant")
        data = await upload.read()
        filename = (getattr(upload, "filename", "") or "").lower()
        if filename.endswith(".pdf"):
            try:
                text = cv_extractor.extract_text_from_pdf(data)
            except Exception as exc:  # pypdf peut lever diverses erreurs
                raise HTTPException(status_code=400, detail=f"PDF illisible : {exc}")
        else:
            text = data.decode("utf-8", errors="ignore")
    else:
        # Corps brut texte accepté aussi (POST text/plain)
        text = (await request.body()).decode("utf-8", errors="ignore")

    if not text.strip():
        raise HTTPException(status_code=400, detail="Aucun texte exploitable fourni")

    draft, report = cv_extractor.extract_profile(text)
    draft["user_id"] = user.id
    return {"draft": draft, "report": report}


def _report_from_profile(profile: dict) -> dict:
    """Rapport d'import cohérent avec le profil restitué (aucun fait ajouté)."""
    skills = profile.get("skills") or []
    return {
        "skills_found": len(skills),
        "experiences_found": len(profile.get("experiences") or []),
        "certifications_found": len(profile.get("certifications") or []),
        "degrees_found": len(profile.get("education") or []),
        "career_fields": sorted({
            str(item.get("category") or "").strip()
            for item in skills
            if str(item.get("category") or "").strip()
        }),
    }


@router.post("/import-cv/library", response_model=schemas.DraftResponse)
def import_library_cv(
    payload: schemas.CvLibraryImportIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Réimporte un CV de la bibliothèque comme brouillon de profil.

    Le CV doit appartenir au candidat. Si l'instantané du profil validé est
    disponible (documents générés après la V19), il est restitué tel quel.
    Sinon, le markdown structuré produit par cv_builder est relu section par
    section, sans heuristique approximative. Un document non reconnaissable
    est refusé plutôt que d'inventer un profil. Rien n'est enregistré : la
    validation humaine reste obligatoire (§47).
    """
    document = db.get(models.Document, payload.document_id)
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="CV introuvable")
    if document.kind != "cv":
        raise HTTPException(
            status_code=422,
            detail="Seuls les CV de votre bibliothèque peuvent être importés.",
        )

    snapshot = document.source_profile
    if snapshot:
        draft = schemas.ProfileOut.model_validate({
            **snapshot,
            "user_id": user.id,
        }).model_dump()
        return {"draft": draft, "report": _report_from_profile(draft)}

    parsed = cv_extractor.extract_generated_cv_profile(document.content_markdown)
    if parsed is None:
        raise HTTPException(
            status_code=422,
            detail="Ce CV ne peut pas être relu automatiquement. Régénérez-le "
                   "depuis votre profil, puis réessayez.",
        )
    draft, report = parsed
    draft["user_id"] = user.id
    return {"draft": draft, "report": report}


@questionnaire_router.get("", response_model=schemas.QuestionnaireOut)
def get_questionnaire():
    return questionnaire.get_steps()


@questionnaire_router.post("/submit", response_model=schemas.DraftResponse)
def submit_questionnaire(
    payload: schemas.QuestionnaireSubmitIn,
    user: models.User = Depends(security.get_current_user),
):
    draft, report = questionnaire.build_draft(payload.answers)
    draft["user_id"] = user.id
    return {"draft": draft, "report": report}
