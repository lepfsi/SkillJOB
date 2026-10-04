"""OrientSkill AI — Backend MVP (FastAPI).

Lancement : ``python -m app.main`` (création des tables + seed si base vide).
"""
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app import config, models, security
from app.database import Base, SessionLocal, engine
from app.api import (
    admin,
    applications,
    assistant,
    auth,
    careers,
    dashboard,
    documents,
    jobs,
    learning,
    market,
    messages,
    profile,
    recruiter,
    referentiels,
    skills,
    v3_intelligence,
)


def _load_json(name: str):
    with open(config.DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def seed_database(db: Session) -> None:
    """Seed initial (MVP, §55) : taxonomie, métiers, offres, ressources,
    utilisateur démo avec profil rempli et 2 candidatures."""
    # Taxonomie des compétences (copie en base pour traçabilité)
    for entry in _load_json("skills_taxonomy.json"):
        db.add(models.Skill(
            name=entry["name"],
            category=entry.get("category", "Autre"),
            aliases=entry.get("aliases", []),
        ))

    # Métiers (Career Intelligence)
    for career in _load_json("careers.json"):
        db.add(models.Career(
            title=career["title"],
            family=career.get("family", ""),
            description=career.get("description", ""),
            required_skills=career.get("required_skills", []),
            education_types=career.get("education_types", []),
        ))

    # Offres (Job Intelligence : source + date toujours tracées)
    from datetime import datetime

    jobs = []
    for job in _load_json("jobs_seed.json"):
        row = models.Job(
            title=job["title"],
            company=job["company"],
            location=job["location"],
            sector=job["sector"],
            contract_type=job["contract_type"],
            description=job.get("description", ""),
            requirements=job.get("requirements", ""),
            required_skills=job.get("required_skills", []),
            published_at=datetime.fromisoformat(job["published_at"]),
            deadline=datetime.fromisoformat(job["deadline"]) if job.get("deadline") else None,
            source_name=job.get("source", {}).get("name", ""),
            source_url=job.get("source", {}).get("url", ""),
            salary=job.get("salary"),
        )
        db.add(row)
        jobs.append(row)

    # Ressources d'apprentissage
    resources = _load_json("learning_resources.json")
    for skill_name, items in resources.items():
        for item in items:
            db.add(models.LearningResource(
                skill=skill_name,
                title=item.get("title", ""),
                provider=item.get("provider", ""),
                type=item.get("type", "free"),
                url=item.get("url"),
            ))

    # Programmes publics (FNE, MINFOP, MINPME, concours)
    for item in _load_json("institutional_offers.json"):
        db.add(models.InstitutionalOffer(
            category=item["category"],
            subcategory=item.get("subcategory"),
            title=item["title"],
            description=item.get("description", ""),
            eligibility=item.get("eligibility", ""),
            url=item.get("url"),
            deadline=item.get("deadline"),
        ))

    # Espace entrepreneuriat (§11bis)
    for item in _load_json("entrepreneur_resources.json"):
        db.add(models.EntrepreneurResource(
            kind=item["kind"],
            title=item["title"],
            description=item.get("description", ""),
            organizer=item.get("organizer", ""),
            url=item.get("url"),
            sectors=item.get("sectors", []),
        ))

    # Utilisateur démo (concours) : profil « junior IT support / réseau »
    demo = models.User(
        email="demo@orientskill.cm",
        full_name="Steve Demo",
        password_hash=security.hash_password("demo1234"),
        role="candidate",
        gender="homme",
    )
    db.add(demo)
    db.flush()

    from app.services.profile_store import save_profile

    demo_profile = {
        "summary": (
            "Technicien support IT et réseaux junior, formé en installation, "
            "configuration et maintenance de réseaux pour cybercafés et PME. "
            "Expériences informelles et missions freelance sur le terrain."
        ),
        "title": "Technicien Support IT / Réseaux Junior",
        "location": "Douala, Cameroun",
        "mobility": "National",
        "availability": "Immédiate",
        "education": [{
            "degree": "BTS Informatique, option Systèmes et Réseaux",
            "institution": "Institut Universitaire de la Côte, Douala",
            "field": "Informatique / Systèmes et réseaux",
            "start_year": 2022,
            "end_year": 2024,
        }],
        "experiences": [
            {
                "title": "Technicien support informatique",
                "organization": "Cybercafé NK, Douala (activité informelle)",
                "type": "informal",
                "description": (
                    "Dépannage de postes clients, installation de Windows, "
                    "configuration du réseau local, assistance des utilisateurs."
                ),
                "start_date": "2023-01",
                "end_date": "2024-06",
                "skills": ["Support informatique", "Windows Server", "TCP/IP",
                           "Relation client"],
            },
            {
                "title": "Installation et configuration de réseaux (missions)",
                "organization": "Clients particuliers et PME, Douala",
                "type": "freelance",
                "description": (
                    "Câblage, configuration de routeurs et pare-feu Fortinet "
                    "pour des petites entreprises."
                ),
                "start_date": "2024-01",
                "end_date": "2025-01",
                "skills": ["TCP/IP", "Routage et commutation", "Fortinet",
                           "Administration de pare-feu"],
            },
            {
                "title": "Stage en administration système",
                "organization": "LogisPro, Douala",
                "type": "apprenticeship",
                "description": (
                    "Administration Windows Server, sauvegardes, gestion des "
                    "incidents niveau 1."
                ),
                "start_date": "2024-03",
                "end_date": "2024-09",
                "skills": ["Windows Server", "Sauvegarde et restauration",
                           "Gestion des incidents", "Linux"],
            },
        ],
        "certifications": [
            {"name": "CCNA — en préparation", "issuer": "Cisco Networking Academy",
             "year": 2024},
        ],
        "languages": [
            {"language": "Français", "level": "courant"},
            {"language": "Anglais", "level": "intermediaire"},
        ],
        "projects": [{
            "name": "Lab réseau personnel",
            "description": (
                "Mise en place d'un lab avec VLANs, routage inter-VLAN et "
                "pare-feu (Fortinet / pfSense)."
            ),
            "skills": ["Routage et commutation", "Administration de pare-feu",
                       "Fortinet", "Linux"],
        }],
        "skills": [
            {"skill": "TCP/IP", "proficiency": "intermediaire",
             "source": "evidence", "evidence_count": 2},
            {"skill": "Windows Server", "proficiency": "intermediaire",
             "source": "evidence", "evidence_count": 2},
            {"skill": "Administration de pare-feu", "proficiency": "intermediaire",
             "source": "evidence", "evidence_count": 2},
            {"skill": "Fortinet", "proficiency": "debutant",
             "source": "evidence", "evidence_count": 2},
            {"skill": "Linux", "proficiency": "debutant",
             "source": "evidence", "evidence_count": 1},
            {"skill": "Support informatique", "proficiency": "avance",
             "source": "evidence", "evidence_count": 1},
            {"skill": "Routage et commutation", "proficiency": "intermediaire",
             "source": "evidence", "evidence_count": 2},
            {"skill": "Sauvegarde et restauration", "proficiency": "debutant",
             "source": "evidence", "evidence_count": 1},
            {"skill": "Gestion des incidents", "proficiency": "intermediaire",
             "source": "evidence", "evidence_count": 1},
            {"skill": "Réseaux informatiques", "proficiency": "intermediaire",
             "source": "evidence", "evidence_count": 2},
            {"skill": "Communication", "proficiency": "intermediaire",
             "source": "declared", "evidence_count": 0},
            {"skill": "Travail en équipe", "proficiency": "intermediaire",
             "source": "declared", "evidence_count": 0},
            {"skill": "Relation client", "proficiency": "intermediaire",
             "source": "declared", "evidence_count": 0},
        ],
        "preferences": {
            "sectors": ["Informatique / IT"],
            "target_roles": ["Administrateur réseaux et systèmes",
                             "Technicien support informatique"],
            "contract_types": ["CDI", "CDD"],
            "remote_ok": False,
        },
    }
    save_profile(db, demo.id, demo_profile)

    # Candidatures de démonstration
    def find_job(title_part: str) -> models.Job | None:
        return next((j for j in jobs if title_part.lower() in j.title.lower()), None)

    from app.models import utcnow

    job1 = find_job("Administrateur Systèmes et Réseaux")
    if job1:
        db.add(models.Application(
            user_id=demo.id, job_id=job1.id, status="en_attente",
            timeline=[
                {"at": utcnow().isoformat(timespec="seconds"),
                 "event": "Candidature envoyée"},
                {"at": utcnow().isoformat(timespec="seconds"),
                 "event": "En attente de réponse"},
            ],
        ))
    job2 = find_job("Technicien support IT")
    if job2:
        db.add(models.Application(
            user_id=demo.id, job_id=job2.id, status="entretien",
            timeline=[
                {"at": utcnow().isoformat(timespec="seconds"),
                 "event": "Candidature envoyée"},
                {"at": utcnow().isoformat(timespec="seconds"),
                 "event": "Entretien à préparer"},
            ],
        ))
    db.commit()

    # Compte administrateur (console /api/admin)
    db.add(models.User(
        email="admin@orientskill.cm",
        full_name="Administrateur",
        password_hash=security.hash_password("admin1234"),
        role="admin",
    ))

    # Compte recruteur de démonstration (espace entreprise)
    recruiter = models.User(
        email="recruteur@orientskill.cm",
        full_name="Directrice RH",
        password_hash=security.hash_password("recruteur1234"),
        role="recruiter",
        gender="femme",
        region="Littoral",
        department="Wouri",
        arrondissement="Douala I",
        city="Douala",
    )
    db.add(recruiter)
    db.flush()
    db.add(models.Company(
        owner_user_id=recruiter.id,
        name="Numérik Services CM",
        sector="Informatique / IT",
        description=(
            "ESN de Douala : installation réseaux, maintenance et "
            "support informatique pour PME."
        ),
        location="Douala",
    ))
    db.commit()


def _ensure_columns() -> None:
    """Migration légère : ajoute les colonnes apparues après la création
    initiale d'une base existante (SQLite ne gère pas ça via create_all)."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    additions = {
        "users": [
            ("gender", "VARCHAR(16)"),
            ("region", "VARCHAR(80)"),
            ("department", "VARCHAR(80)"),
            ("arrondissement", "VARCHAR(80)"),
            ("city", "VARCHAR(120)"),
            ("mfa_secret", "VARCHAR(64)"),
            ("mfa_enabled", "BOOLEAN DEFAULT 0"),
            ("recovery_codes", "JSON"),
            ("verification_status", "VARCHAR(20) DEFAULT 'none'"),
            ("verification_note", "TEXT"),
            ("identity_doc_path", "TEXT"),
            ("verified_at", "DATETIME"),
            ("photo_path", "TEXT"),
            ("notification_prefs", "JSON"),
        ],
        "jobs": [("company_id", "INTEGER"), ("dedup_key", "VARCHAR(80)")],
        "documents": [("template", "VARCHAR(20) DEFAULT 'classique'")],
        "institutional_offers": [("subcategory", "VARCHAR(40)")],
    }
    with engine.begin() as conn:
        for table, columns in additions.items():
            if table not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            seed_database(db)
    finally:
        db.close()
    # Services d'arrière-plan V2 : bot Telegram + digest quotidien.
    # Démarrage conditionnel (config admin) et arrêt propre.
    from app.services.digest import digest_service
    from app.services.telegram_bot import bot_service
    try:
        bot_service.start_if_configured()
    except Exception as exc:  # pragma: no cover
        print(f"Bot Telegram non démarré : {exc}")
    try:
        digest_service.start()
    except Exception as exc:  # pragma: no cover
        print(f"Planificateur de digest non démarré : {exc}")
    yield
    bot_service.stop()
    digest_service.stop()


app = FastAPI(
    title="OrientSkill AI — Backend MVP",
    description="Plateforme d'intelligence professionnelle pour jeunes Camerounais.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if config.CORS_ORIGINS == "*" else config.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    admin.router,
    auth.router,
    profile.router,
    profile.questionnaire_router,
    skills.router,
    careers.router,
    jobs.router,
    applications.router,
    documents.router,
    dashboard.router,
    market.router,
    learning.router,
    assistant.router,
    recruiter.router,
    messages.router,
    referentiels.router,
    v3_intelligence.router,
):
    app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "orientskill-backend"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)
