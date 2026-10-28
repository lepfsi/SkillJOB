"""Espace recruteur (§20-21, version MVP volontairement sobre).

L'entreprise publie ses offres avec son branding, recherche des talents
par compétences et suit les candidatures reçues. Le matching recruteur
est explicable, comme côté candidat (§21).
"""
import unicodedata
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app import config, models, schemas, security
from app.database import get_db
from app.services import calendar as calendar_service
from app.services import cv_pdf, email_routing, job_media, notifications, uploads
from app.services import interviews as interview_service
from app.services.applications import (
    STATUS_LABELS,
    can_transition,
    timeline_entry,
    transition_detail,
)
from app.services.profile_store import profile_to_dict
from app.services.skills_taxonomy import load_taxonomy

router = APIRouter(prefix="/api/recruiter", tags=["recruiter"])


def _require_recruiter(user: models.User) -> models.User:
    if user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Accès réservé aux recruteurs")
    return user


def _get_company(db: Session, user: models.User) -> models.Company:
    company = db.query(models.Company).filter(
        models.Company.owner_user_id == user.id
    ).first()
    if company is None:
        raise HTTPException(status_code=404, detail="Aucune entreprise associée à ce compte")
    return company


def _company_out(company: models.Company) -> dict:
    return {
        "id": company.id,
        "name": company.name,
        "sector": company.sector,
        "description": company.description,
        "location": company.location,
        "website": company.website,
        "has_logo": bool(company.logo_path),
    }


@router.get("/company", response_model=schemas.CompanyOut)
def my_company(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    _require_recruiter(user)
    return _company_out(_get_company(db, user))


@router.put("/company", response_model=schemas.CompanyOut)
def update_company(
    payload: schemas.CompanyUpdateIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    _require_recruiter(user)
    company = _get_company(db, user)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return _company_out(company)


@router.get("/jobs", response_model=list[dict])
def my_jobs(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    _require_recruiter(user)
    company = _get_company(db, user)
    jobs = db.query(models.Job).filter(models.Job.company_id == company.id).all()
    return [_job_dict(job) for job in jobs]


def _job_dict(job: models.Job) -> dict:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "sector": job.sector,
        "domain_id": job.domain_id,
        "specialty_id": job.specialty_id,
        "contract_type": job.contract_type,
        "description": job.description,
        "requirements": job.requirements,
        "required_skills": job.required_skills,
        "published_at": job.published_at,
        "deadline": job.deadline,
        "source_name": job.source_name,
        "source_url": job.source_url,
        "apply_channel": job.apply_channel or "",
        "apply_instructions": job.apply_instructions or "",
        "apply_email": job.apply_email or "",
        "apply_keywords": job.apply_keywords or [],
        "email_reference": email_routing.reference_for(job),
        "poster_url": email_routing.public_poster_path(job),
        "salary": job.salary,
        "photo_url": job_media.photo_url(job),
    }


@router.post("/jobs", status_code=201, response_model=dict)
def publish_job(
    payload: schemas.RecruiterJobCreate,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Publication d'une offre avec le branding de l'entreprise."""
    _require_recruiter(user)
    company = _get_company(db, user)
    domain = db.get(models.Domain, payload.domain_id) if payload.domain_id else None
    if payload.specialty_id:
        specialty = db.get(models.Specialty, payload.specialty_id)
        if specialty is None or (domain and specialty.domain_id != domain.id):
            raise HTTPException(status_code=422, detail="Spécialité incompatible avec le domaine")
    job = models.Job(
        title=payload.title.strip(),
        company=company.name,
        company_id=company.id,
        location=payload.location.strip() or company.location,
        sector=payload.sector.strip() or (domain.name if domain else "") or company.sector,
        domain_id=domain.id if domain else None,
        specialty_id=payload.specialty_id,
        contract_type=payload.contract_type,
        description=payload.description,
        requirements=payload.requirements,
        required_skills=[r.model_dump() for r in payload.required_skills],
        published_at=datetime.utcnow(),
        deadline=payload.deadline,
        source_name=f"Espace recruteur · {company.name}",
        source_url=payload.source_url,
        apply_channel=(payload.apply_channel or "").strip(),
        apply_instructions=(payload.apply_instructions or "").strip(),
        apply_email=(payload.apply_email or "").strip() or None,
        apply_keywords=[
            str(word).strip() for word in (payload.apply_keywords or [])
            if str(word).strip()
        ],
        salary=payload.salary,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    # Confirmation optionnelle : le recruteur choisit cette catégorie dans
    # ses préférences e-mail (catalogue recruteur).
    from app.services.notifications import dispatch

    dispatch(
        db,
        user,
        "OrientSkill AI : votre offre est publiée",
        "\n".join([
            f"Bonjour {(user.full_name or '').split(' ')[0]},",
            "",
            f"Votre offre « {job.title} » est désormais en ligne.",
            "Les candidatures reçues apparaîtront dans votre espace recruteur.",
            "",
            "L'équipe OrientSkill AI",
        ]),
        event="job_published",
    )
    return _job_dict(job)


@router.put("/jobs/{job_id}", response_model=dict)
def update_my_job(
    job_id: int,
    payload: schemas.AdminJobUpdate,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    _require_recruiter(user)
    company = _get_company(db, user)
    job = db.get(models.Job, job_id)
    if job is None or job.company_id != company.id:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    data = payload.model_dump(exclude_unset=True)
    if "domain_id" in data or "specialty_id" in data:
        domain_id = data.get("domain_id", job.domain_id)
        specialty_id = data.get("specialty_id", job.specialty_id)
        domain = db.get(models.Domain, domain_id) if domain_id else None
        specialty = db.get(models.Specialty, specialty_id) if specialty_id else None
        if specialty and (domain is None or specialty.domain_id != domain.id):
            raise HTTPException(status_code=422, detail="Spécialité incompatible avec le domaine")
        if domain and not (data.get("sector") or job.sector or "").strip():
            data["sector"] = domain.name
    for field, value in data.items():
        if field == "apply_keywords" and value is not None:
            value = [str(word).strip() for word in value if str(word).strip()]
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return _job_dict(job)


@router.delete("/jobs/{job_id}")
def delete_my_job(
    job_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    _require_recruiter(user)
    company = _get_company(db, user)
    job = db.get(models.Job, job_id)
    if job is None or job.company_id != company.id:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    db.query(models.Application).filter(models.Application.job_id == job_id).delete()
    db.query(models.Document).filter(models.Document.job_id == job_id).delete()
    job_media.remove(job)
    db.delete(job)
    db.commit()
    return {"ok": True}


@router.post("/jobs/{job_id}/photo", response_model=dict)
def upload_my_job_photo(
    job_id: int,
    file: UploadFile = File(...),
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Photo d'illustration FACULTATIVE de l'offre publiée par l'entreprise."""
    _require_recruiter(user)
    company = _get_company(db, user)
    job = db.get(models.Job, job_id)
    if job is None or job.company_id != company.id:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    job_media.save(job, file)
    db.commit()
    db.refresh(job)
    return {"ok": True, "photo_url": job_media.photo_url(job)}


@router.delete("/jobs/{job_id}/photo")
def delete_my_job_photo(
    job_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    _require_recruiter(user)
    company = _get_company(db, user)
    job = db.get(models.Job, job_id)
    if job is None or job.company_id != company.id:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    job_media.remove(job)
    db.commit()
    return {"ok": True}


def _shared_cv_for_candidate(
    db: Session, candidate: models.User
) -> Optional[dict]:
    """CV généraliste que le talent a explicitement rendu visible.

    Le contrôle est refait à chaque lecture : un document supprimé, ciblé
    ou appartenant à un autre compte ne fuit jamais.
    """
    if not candidate.cv_visible_to_recruiters or not candidate.shared_cv_id:
        return None
    document = db.get(models.Document, candidate.shared_cv_id)
    if document is None or document.user_id != candidate.id:
        return None
    if document.kind != "cv" or document.job_id is not None:
        return None
    return {
        "id": document.id,
        "title": document.title,
        "template": document.template or "classique",
        "accent": document.accent,
        "created_at": document.created_at,
        "download_url": f"/api/recruiter/candidates/{candidate.id}/cv",
    }


def _candidate_payload(
    candidate: models.User,
    profile: models.Profile,
    db: Session,
    match: Optional[dict] = None,
    summary_limit: Optional[int] = None,
) -> dict:
    """Faits du profil validé visibles du recruteur, sans coordonnée."""
    certifications = profile.certifications or []
    experiences = profile.experiences or []
    education = profile.education or []
    summary = profile.summary or ""
    if summary_limit:
        summary = summary[:summary_limit]
    skills = profile.skills or []
    return {
        "user_id": candidate.id,
        "full_name": candidate.full_name,
        "title": profile.title,
        "location": profile.location,
        "verified": candidate.verification_status == "verified",
        "summary": summary,
        "photo_url": (
            f"/api/recruiter/candidates/{candidate.id}/photo"
            if candidate.photo_path else None
        ),
        "skills": [s.get("skill") for s in skills if s.get("skill")][:24],
        "skill_details": [
            {
                "skill": s.get("skill"),
                "proficiency": s.get("proficiency"),
                "source": s.get("source"),
            }
            for s in skills if s.get("skill")
        ][:24],
        "match": match or {"score": 0, "covered": [], "partial": [], "missing": []},
        "mobility": profile.mobility,
        "availability": profile.availability,
        "education": education,
        "experiences": experiences,
        "certifications": certifications,
        "languages": profile.languages or [],
        "projects": profile.projects or [],
        "preferences": profile.preferences or {},
        "experience_count": len(experiences),
        "education_count": len(education),
        "certification_count": len(certifications),
        "top_certifications": [
            c.get("name") for c in certifications if c.get("name")
        ][:4],
        "cv": _shared_cv_for_candidate(db, candidate),
        "updated_at": profile.updated_at,
    }


@router.get("/candidates", response_model=list[schemas.RecruiterCandidateOut])
def search_candidates(
    skills: Optional[str] = None,
    q: str = "",
    region: str = "",
    sector: str = "",
    domain_id: Optional[int] = None,
    specialty_id: Optional[int] = None,
    verified_only: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(security.get_current_user),
):
    """Talent search : filtres compétences, métier/titre, région, secteur
    d'activité visé, profils vérifiés, avec matching explicable (§21)."""
    _require_recruiter(user)
    taxonomy = load_taxonomy()
    wanted = [
        taxonomy.canonical(s.strip()) for s in (skills or "").split(",") if s.strip()
    ]
    needle = q.strip().lower()
    sector_needle = sector.strip().lower()

    profiles = db.query(models.Profile).all()
    out = []
    for profile in profiles:
        candidate = db.get(models.User, profile.user_id)
        if candidate is None or candidate.role != "candidate":
            continue
        if verified_only and candidate.verification_status != "verified":
            continue
        if region and candidate.region != region:
            continue
        prefs = profile.preferences or {}
        if domain_id is not None and prefs.get("domain_id") != domain_id:
            continue
        if specialty_id is not None and specialty_id not in (prefs.get("specialty_ids") or []):
            continue
        # Filtres métier / secteur : titre du profil, secteurs visés,
        # filière, compétences.
        hay = " ".join(filter(None, [
            profile.title or "",
            " ".join((profile.preferences or {}).get("sectors", [])),
            " ".join(ed.get("field", "") for ed in profile.education or []),
        ])).lower()
        if needle and needle not in hay and needle not in candidate.full_name.lower():
            continue
        if sector_needle and sector_needle not in hay:
            continue
        p_skills = profile.skills or []
        covered, partial, missing = [], [], []
        for name in wanted:
            entry = next((s for s in p_skills if s.get("skill") == name), None)
            if entry and entry.get("proficiency") in ("intermediaire", "avance"):
                covered.append(name)
            elif entry:
                partial.append(name)
            else:
                missing.append(name)
        score = 0
        if wanted:
            score = round(
                (len(covered) + 0.5 * len(partial)) / len(wanted) * 100
            )
        # Classement : correspondance aux critères, puis profils vérifiés
        if wanted and score == 0:
            continue
        out.append(_candidate_payload(
            candidate, profile, db,
            match={"score": score, "covered": covered, "partial": partial,
                   "missing": missing},
            summary_limit=220,
        ))
    out.sort(key=lambda c: (-c["match"]["score"], not c["verified"]))
    return out[:50]


@router.get("/candidates/{candidate_id}", response_model=schemas.RecruiterCandidateOut)
def candidate_card(
    candidate_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Carte de profil complète d'un talent : c'est TOUT ce que voit le
    recruteur (aucune coordonnée ; contact via la messagerie interne)."""
    _require_recruiter(user)
    candidate = db.get(models.User, candidate_id)
    if candidate is None or candidate.role != "candidate":
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    profile = db.query(models.Profile).filter(
        models.Profile.user_id == candidate_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Ce candidat n'a pas encore de profil")
    geo = " · ".join(filter(None, [
        candidate.city, candidate.arrondissement, candidate.department, candidate.region,
    ]))
    payload = _candidate_payload(candidate, profile, db)
    payload["location"] = profile.location or geo or None
    return payload


@router.get("/candidates/{candidate_id}/cv")
def candidate_cv(
    candidate_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Télécharge le CV généraliste partagé, uniquement sur opt-in du talent.

    Le PDF est régénéré depuis le profil validé, avec le modèle et la
    couleur du document choisi. Aucun autre document n'est accessible.
    """
    _require_recruiter(user)
    candidate = db.get(models.User, candidate_id)
    if candidate is None or candidate.role != "candidate":
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    cv = _shared_cv_for_candidate(db, candidate)
    if cv is None:
        raise HTTPException(
            status_code=404,
            detail="Ce talent n'a pas partagé de CV généraliste avec les recruteurs.",
        )
    profile = db.query(models.Profile).filter(
        models.Profile.user_id == candidate_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profil introuvable")
    profile_dict = profile_to_dict(profile, candidate_id)
    document = db.get(models.Document, cv["id"])
    if document is None:
        raise HTTPException(status_code=404, detail="CV introuvable")

    content = cv_pdf.build_cv_pdf(
        profile_dict, None, candidate, load_taxonomy(),
        template=document.template or "classique",
        accent=document.accent,
    )
    safe_name = unicodedata.normalize("NFKD", candidate.full_name)
    safe_name = "".join(c for c in safe_name if not unicodedata.combining(c))
    safe_name = "".join(
        c if c.isascii() and (c.isalnum() or c in " -_") else "_"
        for c in safe_name
    ).strip("_") or f"candidat-{candidate.id}"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="CV-{safe_name}.pdf"'
        },
    )


@router.get("/applications", response_model=list[schemas.RecruiterApplicationOut])
def received_applications(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Candidatures reçues sur les offres de l'entreprise."""
    _require_recruiter(user)
    company = _get_company(db, user)
    job_ids = [j.id for j in db.query(models.Job).filter(
        models.Job.company_id == company.id).all()]
    if not job_ids:
        return []
    apps = (
        db.query(models.Application)
        .filter(models.Application.job_id.in_(job_ids))
        .order_by(models.Application.created_at.desc())
        .all()
    )
    out = []
    for app in apps:
        candidate = db.get(models.User, app.user_id)
        out.append({
            "id": app.id,
            "job_id": app.job_id,
            "job_title": app.job.title,
            "candidate_id": app.user_id,
            "candidate_name": candidate.full_name if candidate else "?",
            "candidate_verified": (candidate.verification_status == "verified") if candidate else False,
            "candidate_photo_url": (
                f"/api/recruiter/candidates/{candidate.id}/photo"
                if candidate and candidate.photo_path else ""
            ),
            "status": app.status,
            "timeline": app.timeline or [],
            "created_at": app.created_at,
            "apply_channel": app.apply_channel or "",
            "apply_url": app.job.source_url or "",
            "apply_email": app.job.apply_email or "",
            "apply_instructions": app.job.apply_instructions or "",
        })
    return out


@router.get("/candidates/{candidate_id}/photo")
def candidate_photo(
    candidate_id: int,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Photo du candidat, réservée aux recruteurs (profil visible en recherche)."""
    _require_recruiter(user)
    candidate = db.get(models.User, candidate_id)
    if candidate is None or candidate.role != "candidate" or not candidate.photo_path:
        raise HTTPException(status_code=404, detail="Photo introuvable")
    full = uploads.resolve(candidate.photo_path)
    if not full.exists():
        raise HTTPException(status_code=404, detail="Photo introuvable")
    return FileResponse(full)


@router.patch("/applications/{application_id}", response_model=dict)
def update_application_status(
    application_id: int,
    payload: schemas.ApplicationStatusIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Statut PARTAGÉ : le recruteur instruit la candidature.

    Le recruteur peut mettre en attente, convoquer à un entretien,
    transmettre une offre ou refuser. Il ne peut ni accepter une offre à
    la place du candidat, ni retirer une candidature. Le changement est
    journalisé avec l'auteur et le motif éventuel.
    """
    _require_recruiter(user)
    company = _get_company(db, user)
    app = db.get(models.Application, application_id)
    if app is None or app.job.company_id != company.id:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    if payload.status not in schemas.APPLICATION_STATUSES:
        raise HTTPException(status_code=422, detail="Statut invalide")
    if not can_transition("recruiter", app.status, payload.status):
        raise HTTPException(
            status_code=403,
            detail=transition_detail("recruiter", app.status, payload.status),
        )

    reason = (payload.reason or "").strip()
    label = STATUS_LABELS[payload.status]
    app.status = payload.status
    timeline = list(app.timeline or [])
    timeline.append(
        timeline_entry(
            f"Mise à jour par {company.name} : {label}",
            by=company.name,
            reason=reason,
        )
    )
    app.timeline = timeline
    db.commit()

    # Notification du candidat (best effort)
    from app.services.notifications import dispatch

    candidate = db.get(models.User, app.user_id)
    if candidate:
        detail = (
            f"{company.name} a mis à jour votre candidature au poste "
            f"« {app.job.title} » : {label.lower()}."
        )
        if reason:
            detail += f" Motif : {reason}."
        dispatch(
            db, candidate,
            "OrientSkill AI : votre candidature a évolué",
            detail,
            event="application",
        )
    return {"ok": True, "status": app.status}


# ----------------------------------------------- Shortlists (§20, V2)

@router.get("/shortlists", response_model=list[schemas.ShortlistOut])
def my_shortlists(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    _require_recruiter(user)
    out = []
    for sl in db.query(models.Shortlist).filter(
        models.Shortlist.owner_user_id == user.id
    ).order_by(models.Shortlist.created_at.desc()).all():
        items = []
        for item in db.query(models.ShortlistItem).filter(
            models.ShortlistItem.shortlist_id == sl.id
        ).all():
            candidate = db.get(models.User, item.candidate_id)
            if candidate is None:
                continue
            items.append({
                "candidate_id": candidate.id,
                "name": candidate.full_name,
                "verified": candidate.verification_status == "verified",
                "added_at": item.added_at,
            })
        out.append({
            "id": sl.id, "name": sl.name, "note": sl.note,
            "created_at": sl.created_at, "items": items,
        })
    return out


@router.post("/shortlists", status_code=201, response_model=schemas.ShortlistOut)
def create_shortlist(
    payload: schemas.ShortlistCreateIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    _require_recruiter(user)
    sl = models.Shortlist(
        owner_user_id=user.id,
        name=payload.name.strip(),
        note=payload.note.strip(),
    )
    db.add(sl)
    db.commit()
    db.refresh(sl)
    return {"id": sl.id, "name": sl.name, "note": sl.note,
            "created_at": sl.created_at, "items": []}


@router.delete("/shortlists/{shortlist_id}")
def delete_shortlist(shortlist_id: int,
                     user: models.User = Depends(security.get_current_user),
                     db: Session = Depends(get_db)):
    _require_recruiter(user)
    sl = db.get(models.Shortlist, shortlist_id)
    if sl is None or sl.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Shortlist introuvable")
    db.query(models.ShortlistItem).filter(
        models.ShortlistItem.shortlist_id == sl.id).delete()
    db.delete(sl)
    db.commit()
    return {"ok": True}


@router.post("/shortlists/{shortlist_id}/items", response_model=dict)
def add_to_shortlist(shortlist_id: int,
                     payload: schemas.ShortlistItemIn,
                     user: models.User = Depends(security.get_current_user),
                     db: Session = Depends(get_db)):
    _require_recruiter(user)
    sl = db.get(models.Shortlist, shortlist_id)
    if sl is None or sl.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Shortlist introuvable")
    candidate = db.get(models.User, payload.candidate_id)
    if candidate is None or candidate.role != "candidate":
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    exists = db.query(models.ShortlistItem).filter(
        models.ShortlistItem.shortlist_id == sl.id,
        models.ShortlistItem.candidate_id == candidate.id,
    ).first()
    if exists:
        return {"ok": True, "detail": "Déjà dans cette shortlist."}
    db.add(models.ShortlistItem(shortlist_id=sl.id, candidate_id=candidate.id))
    db.commit()
    return {"ok": True}


@router.delete("/shortlists/{shortlist_id}/items/{candidate_id}")
def remove_from_shortlist(shortlist_id: int, candidate_id: int,
                          user: models.User = Depends(security.get_current_user),
                          db: Session = Depends(get_db)):
    _require_recruiter(user)
    sl = db.get(models.Shortlist, shortlist_id)
    if sl is None or sl.owner_user_id != user.id:
        raise HTTPException(status_code=404, detail="Shortlist introuvable")
    db.query(models.ShortlistItem).filter(
        models.ShortlistItem.shortlist_id == sl.id,
        models.ShortlistItem.candidate_id == candidate_id,
    ).delete()
    db.commit()
    return {"ok": True}


# ------------------------------------------- Invitations à un entretien

@router.get("/interviews", response_model=list[schemas.InterviewInviteOut])
def my_interview_invites(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Invitations envoyées par ce recruteur, avec la réponse du candidat."""
    _require_recruiter(user)
    rows = (
        db.query(models.InterviewInvite)
        .filter(models.InterviewInvite.recruiter_id == user.id)
        .order_by(models.InterviewInvite.created_at.desc())
        .all()
    )
    return [interview_service.invite_dict(db, row) for row in rows]


@router.get("/interviews/requests",
            response_model=list[schemas.InterviewInviteOut])
def interview_requests(
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """File dédiée des demandes d'autre créneau, avec l'historique."""
    _require_recruiter(user)
    rows = (
        db.query(models.InterviewInvite)
        .filter(
            models.InterviewInvite.recruiter_id == user.id,
            models.InterviewInvite.status == "declined",
        )
        .order_by(models.InterviewInvite.responded_at.desc())
        .all()
    )
    return [interview_service.invite_dict(db, row) for row in rows]


@router.post("/interviews/{invite_id}/respond",
             response_model=schemas.InterviewInviteOut)
def respond_to_interview_request(
    invite_id: int,
    payload: schemas.InterviewRecruiterRespondIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Accepte un créneau proposé, propose un autre créneau ou refuse.

    La décision est tracée dans l'historique et le candidat est notifié
    dans sa rubrique Notifications (e-mail si son canal est activé).
    """
    _require_recruiter(user)
    invite = db.get(models.InterviewInvite, invite_id)
    if invite is None or invite.recruiter_id != user.id:
        raise HTTPException(status_code=404, detail="Demande introuvable")
    if invite.status != "declined":
        raise HTTPException(
            status_code=400,
            detail="Cette demande de créneau n'est plus en attente.",
        )
    note = (payload.note or "").strip()[:1000]
    job = db.get(models.Job, invite.job_id)
    candidate = db.get(models.User, invite.candidate_id)
    chosen_slot = None

    if payload.action == "accept_requested":
        if payload.slot_at is None:
            raise HTTPException(
                status_code=422,
                detail="Choisissez un des créneaux proposés par le candidat.",
            )
        requested = interview_service.requested_slot_values(invite)
        chosen_slot = next(
            (slot for slot in requested if slot == payload.slot_at), None
        )
        if chosen_slot is None:
            raise HTTPException(
                status_code=422,
                detail="Ce créneau ne figure pas dans la proposition du candidat.",
            )
        invite.slot_at = chosen_slot
        invite.status = "accepted"
        invite.recruiter_responded_at = models.utcnow()
        interview_service.append_history(
            invite, "recruiter", "request_accepted",
            slot_at=chosen_slot, note=note,
        )
    elif payload.action == "propose":
        if payload.slot_at is None:
            raise HTTPException(
                status_code=422,
                detail="Choisissez une date et une heure pour le nouveau créneau.",
            )
        if payload.slot_at < models.utcnow() - timedelta(hours=1):
            raise HTTPException(
                status_code=422,
                detail="Le nouveau créneau est déjà passé.",
            )
        invite.slot_at = payload.slot_at
        invite.status = "pending"
        invite.responded_at = None
        invite.recruiter_responded_at = models.utcnow()
        invite.requested_slots = []
        invite.candidate_note = None
        interview_service.append_history(
            invite, "recruiter", "slot_proposed",
            slot_at=payload.slot_at, note=note,
        )
    else:
        invite.status = "refused"
        invite.recruiter_responded_at = models.utcnow()
        interview_service.append_history(
            invite, "recruiter", "request_refused", note=note,
        )

    db.commit()
    db.refresh(invite)

    if job and candidate:
        subject, body = interview_service.compose_candidate_decision_body(
            invite, job, payload.action, slot_at=chosen_slot or payload.slot_at,
            note=note,
        )
        notifications.dispatch(
            db, candidate, subject, body, event="interview"
        )
    return interview_service.invite_dict(db, invite)


@router.post("/interviews", status_code=201,
             response_model=schemas.InterviewInviteOut)
def invite_to_interview(
    payload: schemas.InterviewInviteIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Invite un candidat de SES shortlists à un entretien daté.

    L'e-mail reprend l'identité réelle du poste et de l'entreprise, le
    créneau lisible et deux liens profonds (accepter / autre créneau).
    Si le service e-mail n'est pas configuré, l'invitation reste disponible
    dans l'espace du candidat : la réponse indique `email_sent: false`.
    """
    _require_recruiter(user)
    job = db.get(models.Job, payload.job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Offre introuvable")
    company = db.get(models.Company, job.company_id) if job.company_id else None
    if company is None or company.owner_user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Vous ne pouvez inviter que pour une de vos propres offres.",
        )
    candidate = db.get(models.User, payload.candidate_id)
    if candidate is None or candidate.role != "candidate":
        raise HTTPException(status_code=404, detail="Candidat introuvable")
    in_shortlist = (
        db.query(models.ShortlistItem)
        .join(models.Shortlist, models.Shortlist.id == models.ShortlistItem.shortlist_id)
        .filter(
            models.Shortlist.owner_user_id == user.id,
            models.ShortlistItem.candidate_id == candidate.id,
        )
        .first()
    )
    if in_shortlist is None:
        raise HTTPException(
            status_code=400,
            detail="Ce candidat n'est pas dans une de vos shortlists.",
        )
    if payload.slot_at < models.utcnow() - timedelta(hours=1):
        raise HTTPException(
            status_code=400,
            detail="Le créneau proposé est déjà passé : choisissez une date à venir.",
        )

    invite = models.InterviewInvite(
        token=interview_service.new_token(),
        recruiter_id=user.id,
        candidate_id=candidate.id,
        job_id=job.id,
        slot_at=payload.slot_at,
        duration_min=payload.duration_min,
        subject=payload.subject.strip(),
        message=payload.message.strip(),
        status="pending",
        requested_slots=[],
        history=[],
    )
    db.add(invite)
    interview_service.append_history(
        invite,
        actor="recruiter",
        action="invited",
        slot_at=payload.slot_at,
        note=payload.message.strip(),
    )
    db.commit()
    db.refresh(invite)

    body = interview_service.compose_body(invite, job)
    ics = calendar_service.attachment(invite, job, candidate, user, status="pending")
    email_sent, _detail = notifications.send_email(
        db, candidate.email, invite.subject, body, attachments=[ics]
    )
    return interview_service.invite_dict(db, invite, email_sent=email_sent)
