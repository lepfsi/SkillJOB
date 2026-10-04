"""Auth : register / login (+ MFA TOTP en deux étapes) / me / sécurité.

Flow MFA : le login retourne un jeton MFA éphémère si le compte a le MFA
actif ; l'utilisateur confirme avec un code TOTP ou un code de
récupération pour obtenir le jeton de session.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import config, models, schemas, security
from app.database import get_db
from app.services import mfa as mfa_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=schemas.AuthResponse)
def register(payload: schemas.RegisterIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    user = models.User(
        email=email,
        full_name=payload.full_name.strip(),
        password_hash=security.hash_password(payload.password),
        role="candidate",
        gender=payload.gender,
        region=payload.region,
        department=payload.department,
        arrondissement=payload.arrondissement,
        city=payload.city,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"token": security.create_token(user.id), "user": user}


@router.post("/register/recruiter", status_code=201, response_model=schemas.AuthResponse)
def register_recruiter(payload: schemas.RecruiterRegisterIn, db: Session = Depends(get_db)):
    """Crée un compte recruteur lié à son entreprise (branding).

    - type entreprise / cabinet RH : le compte EST la structure, aucune
      donnée personnelle n'est demandée (nom affiché = nom de la structure) ;
    - recruteur indépendant : inscription complète avec nom et genre.
    """
    email = payload.email.strip().lower()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    independent = payload.recruiter_type == "independent"
    display_name = (
        payload.full_name.strip() if independent and payload.full_name.strip()
        else payload.company_name.strip()
    )
    user = models.User(
        email=email,
        full_name=display_name,
        password_hash=security.hash_password(payload.password),
        role="recruiter",
        gender=payload.gender if independent else None,
        region=payload.region if independent else None,
        department=payload.department if independent else None,
        arrondissement=payload.arrondissement if independent else None,
        city=payload.city if independent else None,
    )
    db.add(user)
    db.flush()
    suffix = " · Cabinet RH" if payload.recruiter_type == "agency" else ""
    company = models.Company(
        owner_user_id=user.id,
        name=payload.company_name.strip(),
        sector=payload.company_sector.strip(),
        description=(payload.company_description.strip() + suffix).strip(" ·"),
        location=payload.company_location.strip(),
        website=payload.company_website,
    )
    db.add(company)
    db.commit()
    db.refresh(user)
    return {"token": security.create_token(user.id), "user": user}


@router.post("/login", response_model=schemas.LoginResponse)
def login(payload: schemas.LoginIn, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None or not security.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")
    if user.mfa_enabled and user.mfa_secret:
        # Étape 1 validée : jeton MFA éphémère (5 minutes)
        return {
            "mfa_required": True,
            "mfa_token": security.create_token(user.id, minutes=5),
        }
    return {"token": security.create_token(user.id), "user": user}


@router.post("/login/mfa", response_model=schemas.AuthResponse)
def login_mfa(payload: schemas.MfaLoginIn, db: Session = Depends(get_db)):
    """Étape 2 : code TOTP ou code de récupération → jeton de session."""
    user_id = security.decode_token(payload.mfa_token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Session MFA expirée, reconnectez-vous")
    user = db.get(models.User, user_id)
    if user is None or not user.mfa_enabled:
        raise HTTPException(status_code=401, detail="Compte introuvable ou MFA désactivé")

    code = (payload.code or "").strip()
    used_hash = None
    if mfa_service.verify_totp(user.mfa_secret, code):
        pass
    else:
        used_hash = mfa_service.find_recovery_code(user.recovery_codes or [], code)
        if used_hash is None:
            raise HTTPException(status_code=401, detail="Code MFA incorrect")

    if used_hash:
        # Consomme le code de récupération
        remaining = [
            item if item.get("hash") != used_hash else {**item, "used": True}
            for item in (user.recovery_codes or [])
        ]
        user.recovery_codes = remaining
        db.commit()
    return {"token": security.create_token(user.id), "user": user}


@router.post("/mfa/setup", response_model=schemas.MfaSetupOut)
def mfa_setup(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Génère un secret TOTP (non actif tant que /mfa/enable n'est pas appelé)."""
    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA déjà activé sur ce compte")
    secret = mfa_service.generate_secret()
    user.mfa_secret = secret
    db.commit()
    return {
        "secret": secret,
        "otpauth_uri": mfa_service.otpauth_uri(secret, user.email),
        "qr_data_url": _qr_data_url(mfa_service.otpauth_uri(secret, user.email)),
    }


@router.post("/mfa/enable", response_model=schemas.MfaEnabledOut)
def mfa_enable(
    payload: schemas.MfaCodeIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Active le MFA : vérifie le code puis retourne les codes de récupération
    (montrés UNE SEULE fois)."""
    if user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=400, detail="Lancez d'abord la configuration MFA")
    if not mfa_service.verify_totp(user.mfa_secret, payload.code):
        raise HTTPException(status_code=400, detail="Code incorrect, réessayez")
    codes = mfa_service.generate_recovery_codes()
    user.mfa_enabled = True
    user.recovery_codes = [
        {"hash": mfa_service.hash_recovery_code(c), "used": False} for c in codes
    ]
    db.commit()
    return {
        "recovery_codes": codes,
        "message": "Conservez ces codes : ils permettent d'accéder à votre "
                    "compte si vous perdez votre application d'authentification.",
    }


@router.post("/mfa/disable")
def mfa_disable(
    payload: schemas.MfaCodeIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Désactive le MFA : exige un code valide (TOTP ou récupération)."""
    if not user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA non activé")
    code = (payload.code or "").strip()
    ok = mfa_service.verify_totp(user.mfa_secret, code)
    if not ok:
        ok = mfa_service.find_recovery_code(user.recovery_codes or [], code) is not None
    if not ok:
        raise HTTPException(status_code=400, detail="Code incorrect")
    user.mfa_enabled = False
    user.mfa_secret = None
    user.recovery_codes = []
    db.commit()
    return {"ok": True}


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(security.get_current_user)):
    return user


def _qr_data_url(uri: str) -> str:
    """QR code PNG en data URL (qrcode + pillow déjà présents)."""
    try:
        import base64 as _b64
        import io

        import qrcode
        img = qrcode.make(uri)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return "data:image/png;base64," + _b64.b64encode(buffer.getvalue()).decode("ascii")
    except ImportError:  # qrcode absent : l'utilisateur saisit le secret manuellement
        return ""
