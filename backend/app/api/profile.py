"""Profile Engine : profil maître, import CV, questionnaire, photo et
vérification de profil (§7.1, §9ter).
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import config, models, schemas, security
from app.database import get_db
from app.services import cv_extractor, profile_store, questionnaire

router = APIRouter(prefix="/api/profile", tags=["profile"])
questionnaire_router = APIRouter(prefix="/api/questionnaire", tags=["questionnaire"])

UPLOAD_DIR = config.BASE_DIR / "uploads"
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
    user.photo_path = str(path.relative_to(config.BASE_DIR)).replace("\\", "/")
    db.commit()
    db.refresh(user)
    return user


@router.get("/photo")
def get_photo(user: models.User = Depends(security.get_current_user)):
    """Sert la photo de l'utilisateur connecté (avec en-tête d'autorisation)."""
    if not user.photo_path:
        raise HTTPException(status_code=404, detail="Aucune photo")
    full = config.BASE_DIR / user.photo_path
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
    user.identity_doc_path = str(path.relative_to(config.BASE_DIR)).replace("\\", "/")
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


# ------------------------------------------------ Notifications (§25)

def _prefs_out(user: models.User) -> dict:
    from app.services.notifications import normalize_prefs

    return normalize_prefs(getattr(user, "notification_prefs", None) or {})


@router.get("/notifications", response_model=dict)
def get_notifications(user: models.User = Depends(security.get_current_user)):
    return _prefs_out(user)


@router.put("/notifications", response_model=dict)
def update_notifications(
    payload: schemas.NotificationPrefsIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Canaux et coordonnées de notification de l'utilisateur.
    Les identifiants des services (SMTP, bots) restent côté admin."""
    prefs = _prefs_out(user)
    incoming = payload.model_dump()
    for key, value in incoming.items():
        if value is not None:
            prefs[key] = value
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
