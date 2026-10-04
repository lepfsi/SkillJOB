"""Espace recruteur (§20-21, version MVP volontairement sobre).

L'entreprise publie ses offres avec son branding, recherche des talents
par compétences et suit les candidatures reçues. Le matching recruteur
est explicable, comme côté candidat (§21).
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas, security
from app.database import get_db
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
        "contract_type": job.contract_type,
        "description": job.description,
        "requirements": job.requirements,
        "required_skills": job.required_skills,
        "published_at": job.published_at,
        "deadline": job.deadline,
        "source_name": job.source_name,
        "source_url": job.source_url,
        "salary": job.salary,
    }


@router.post("/jobs", status_code=201, response_model=dict)
def publish_job(
    payload: schemas.AdminJobCreate,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Publication d'une offre avec le branding de l'entreprise."""
    _require_recruiter(user)
    company = _get_company(db, user)
    job = models.Job(
        title=payload.title.strip(),
        company=company.name,
        company_id=company.id,
        location=payload.location.strip() or company.location,
        sector=payload.sector.strip() or company.sector,
        contract_type=payload.contract_type,
        description=payload.description,
        requirements=payload.requirements,
        required_skills=[r.model_dump() for r in payload.required_skills],
        published_at=datetime.utcnow(),
        deadline=payload.deadline,
        source_name=f"Espace recruteur · {company.name}",
        source_url=payload.source_url,
        salary=payload.salary,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
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
    for field, value in payload.model_dump(exclude_unset=True).items():
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
    db.delete(job)
    db.commit()
    return {"ok": True}


@router.get("/candidates", response_model=list[schemas.RecruiterCandidateOut])
def search_candidates(
    skills: Optional[str] = None,
    q: str = "",
    region: str = "",
    sector: str = "",
    verified_only: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(security.get_current_user),
):
    """Talent search : filtres compétences, métier/titre, région, secteur
    d'activité visé, profils vérifiés — avec matching explicable (§21)."""
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
        out.append({
            "user_id": candidate.id,
            "full_name": candidate.full_name,
            "title": profile.title,
            "location": profile.location,
            "verified": candidate.verification_status == "verified",
            "summary": (profile.summary or "")[:220],
            "skills": [s.get("skill") for s in p_skills][:12],
            "match": {"score": score, "covered": covered, "partial": partial,
                      "missing": missing},
        })
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
    p_skills = profile.skills or []
    geo = " · ".join(filter(None, [
        candidate.city, candidate.arrondissement, candidate.department, candidate.region,
    ]))
    return {
        "user_id": candidate.id,
        "full_name": candidate.full_name,
        "title": profile.title,
        "location": profile.location or geo or None,
        "verified": candidate.verification_status == "verified",
        "summary": profile.summary or "",
        "skills": [s.get("skill") for s in p_skills][:20],
        "match": {"score": 0, "covered": [], "partial": [], "missing": []},
    }


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
            "status": app.status,
            "timeline": app.timeline or [],
            "created_at": app.created_at,
        })
    return out


@router.patch("/applications/{application_id}", response_model=dict)
def update_application_status(
    application_id: int,
    payload: schemas.ApplicationStatusIn,
    user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db),
):
    """Statut PARTAGÉ : le recruteur fait avancer le pipeline côté
    candidat (entretien, offre…). Le changement est journalisé dans la
    timeline, visible du candidat."""
    _require_recruiter(user)
    company = _get_company(db, user)
    app = db.get(models.Application, application_id)
    if app is None or app.job.company_id != company.id:
        raise HTTPException(status_code=404, detail="Candidature introuvable")
    if payload.status not in schemas.APPLICATION_STATUSES:
        raise HTTPException(status_code=422, detail="Statut invalide")
    app.status = payload.status
    timeline = list(app.timeline or [])
    timeline.append({
        "at": datetime.utcnow().isoformat(timespec="seconds"),
        "event": f"Mise à jour par {company.name} : {payload.status}",
    })
    app.timeline = timeline
    db.commit()

    # Notification du candidat (best effort)
    from app.services.notifications import dispatch

    candidate = db.get(models.User, app.user_id)
    if candidate:
        dispatch(
            db, candidate,
            f"OrientSkill AI : votre candidature a évolué",
            f"{company.name} a mis à jour votre candidature au poste "
            f"« {app.job.title} » : nouveau statut « {payload.status} ».",
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
