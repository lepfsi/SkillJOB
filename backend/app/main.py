"""OrientSkill AI : Backend MVP (FastAPI).

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
    interviews,
    jobs,
    learning,
    market,
    messages,
    profile,
    public,
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

    from app.services.domains import match_domain, match_specialty

    jobs = []
    for job in _load_json("jobs_seed.json"):
        domain = match_domain(db, job["sector"])
        specialty = None
        if domain is not None:
            specialty = match_specialty(
                db, domain.id,
                " ".join(filter(None, [
                    job["title"], job.get("description", ""),
                    job.get("requirements", ""),
                ])),
            )
        row = models.Job(
            title=job["title"],
            company=job["company"],
            location=job["location"],
            sector=job["sector"],
            domain_id=domain.id if domain else None,
            specialty_id=specialty.id if specialty else None,
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
        region="Littoral",
        department="Wouri",
        arrondissement="Douala I",
        city="Douala",
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
            {"name": "CCNA (en préparation)", "issuer": "Cisco Networking Academy",
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
    demo_domain = match_domain(db, "Informatique / IT")
    if demo_domain is not None:
        demo_profile["preferences"]["domain_id"] = demo_domain.id
        demo_specialties = [
            match_specialty(db, demo_domain.id, label)
            for label in ("Réseaux et systèmes", "Cybersécurité", "Support et helpdesk")
        ]
        demo_profile["preferences"]["specialty_ids"] = [
            specialty.id for specialty in demo_specialties if specialty is not None
        ]
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
            ("phone", "VARCHAR(32)"),
            ("mfa_secret", "VARCHAR(64)"),
            ("mfa_enabled", "BOOLEAN DEFAULT 0"),
            ("recovery_codes", "JSON"),
            ("verification_status", "VARCHAR(20) DEFAULT 'none'"),
            ("verification_note", "TEXT"),
            ("identity_doc_path", "TEXT"),
            ("verified_at", "DATETIME"),
            ("verification_decided_at", "DATETIME"),
            ("photo_path", "TEXT"),
            ("cv_visible_to_recruiters", "BOOLEAN DEFAULT 0"),
            ("shared_cv_id", "INTEGER"),
            ("notification_prefs", "JSON"),
            ("notifications_seen_at", "DATETIME"),
            ("agent_mode", "VARCHAR(20) DEFAULT 'preparation'"),
            ("agent_history_mode", "VARCHAR(12) DEFAULT 'persist'"),
            ("agent_history_retention_days", "INTEGER DEFAULT 30"),
            ("is_banned", "BOOLEAN DEFAULT 0"),
            ("ban_reason", "TEXT"),
        ],
        "jobs": [
            ("company_id", "INTEGER"),
            ("dedup_key", "VARCHAR(80)"),
            ("photo_path", "TEXT"),
            ("domain_id", "INTEGER"),
            ("specialty_id", "INTEGER"),
            ("apply_channel", "VARCHAR(20) DEFAULT ''"),
            ("apply_instructions", "TEXT"),
            ("apply_email", "VARCHAR(255)"),
            ("apply_keywords", "JSON"),
        ],
        "inbound_emails": [
            ("account_created", "BOOLEAN DEFAULT 0"),
        ],
        "documents": [
            ("template", "VARCHAR(20) DEFAULT 'classique'"),
            ("accent", "VARCHAR(16)"),
            ("source_profile", "JSON"),
        ],
        "applications": [
            ("apply_channel", "VARCHAR(20) DEFAULT ''"),
            ("submitted_at", "DATETIME"),
            ("submitted_documents", "JSON"),
            ("cover_note", "TEXT"),
        ],
        "institutional_offers": [
            ("subcategory", "VARCHAR(40)"),
            ("documents", "JSON"),
            ("source", "VARCHAR(20) DEFAULT 'referentiel'"),
        ],
        "learning_resources": [
            ("source", "VARCHAR(20) DEFAULT 'referentiel'"),
            ("hidden", "BOOLEAN DEFAULT 0"),
        ],
        "source_configs": [
            ("interval_minutes", "INTEGER DEFAULT 60"),
            ("last_error", "TEXT"),
            ("last_items", "INTEGER DEFAULT 0"),
            ("last_duration_ms", "INTEGER DEFAULT 0"),
            ("etag", "VARCHAR(255)"),
            ("last_modified", "VARCHAR(255)"),
        ],
        "assistant_messages": [
            ("conversation_id", "INTEGER"),
        ],
    }
    with engine.begin() as conn:
        for table, columns in additions.items():
            if table not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def purge_long_dashes() -> None:
    """Retire les tirets longs des données déjà enregistrées.

    Les sources du WebUI n'en contiennent plus, mais les anciennes bases
    (profils, offres, documents générés) peuvent encore en stocker. La
    normalisation est idempotente et couvre aussi les séquences JSON
    échappées (``\\u2014``) ainsi que les entités HTML courantes.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    replacements = [
        ("\u2013", "-"),
        ("\u2014", "-"),
        ("\u2015", "-"),
        ("\\u2013", "-"),
        ("\\u2014", "-"),
        ("\\u2015", "-"),
        ("&ndash;", "-"),
        ("&mdash;", "-"),
        ("&#8211;", "-"),
        ("&#8212;", "-"),
        ("&#x2013;", "-"),
        ("&#x2014;", "-"),
    ]
    text_markers = ("CHAR", "TEXT", "CLOB", "JSON")

    with engine.begin() as conn:
        for table in inspector.get_table_names():
            if table.startswith("sqlite_"):
                continue
            for column in inspector.get_columns(table):
                if not any(marker in str(column["type"]).upper() for marker in text_markers):
                    continue
                name = column["name"]
                expression = f'"{name}"'
                conditions = []
                params = {}
                for index, (old, new) in enumerate(replacements):
                    expression = f"replace({expression}, :old{index}, :new{index})"
                    conditions.append(f'instr("{name}", :old{index}) > 0')
                    params[f"old{index}"] = old
                    params[f"new{index}"] = new
                conn.execute(
                    text(
                        f'UPDATE "{table}" SET "{name}" = {expression} '
                        f'WHERE {" OR ".join(conditions)}'
                    ),
                    params,
                )


def sync_learning_resources(db: Session) -> None:
    """Aligne la table de référence des formations sur le référentiel.

    ``data/learning_resources.json`` fait foi pour les entrées
    « referentiel » : il est relu à chaque démarrage pour que les
    formations proposées (et leur nature de lien) restent celles
    réellement vérifiées. Les entrées « admin » (ajoutées ou corrigées
    dans la console) ne sont NI écrasées NI supprimées, pas plus que les
    lignes masquées par l'administrateur. Il s'agit de données de
    référence uniquement : aucun profil ni suivi d'utilisateur n'est
    touché.
    """
    referential = _load_json("learning_resources.json")
    all_rows = db.query(models.LearningResource).all()
    existing = {(row.skill, row.title): row for row in all_rows}
    wanted: set[tuple[str, str]] = set()
    changed = False
    for skill, items in referential.items():
        for item in items:
            title = item.get("title", "")
            if not title:
                continue
            wanted.add((skill, title))
            provider = item.get("provider", "")
            kind = item.get("type", "free")
            url = item.get("url")
            row = existing.get((skill, title))
            if row is None:
                db.add(models.LearningResource(
                    skill=skill, title=title, provider=provider,
                    type=kind, url=url, source="referentiel",
                ))
                changed = True
            elif (row.source or "referentiel") == "referentiel":
                # Les lignes « admin » et les lignes masquées ne sont
                # JAMAIS écrasées : la console garde la main.
                if (row.url, row.provider, row.type) != (url, provider, kind):
                    row.url, row.provider, row.type = url, provider, kind
                    changed = True
    for key, row in existing.items():
        if key not in wanted and (row.source or "referentiel") == "referentiel":
            db.delete(row)
            changed = True
    if changed:
        db.commit()


def sync_institutional_offers(db: Session) -> None:
    """Aligne les programmes publics sur le référentiel éditorial.

    ``data/institutional_offers.json`` fait foi : structuration par
    institution (MINFOPRA, MINESUP, MINEFOP, ONG, MINDEF, DGSN, appels à
    projets des ministères). Relu à chaque démarrage pour que la page
    « Programmes publics » reste conforme au référentiel.

    Les fiches CRÉÉES OU MODIFIÉES par l'administration (``source =
    "admin"``) sont laissées intactes : leurs ajouts, leurs corrections et
    leurs documents joints ne sont jamais écrasés par le référentiel.
    """
    referential = _load_json("institutional_offers.json")
    existing = {
        (row.category, row.subcategory or "", row.title): row
        for row in db.query(models.InstitutionalOffer)
    }
    wanted: set[tuple[str, str, str]] = set()
    changed = False
    for item in referential:
        key = (item["category"], item.get("subcategory") or "", item["title"])
        wanted.add(key)
        fields = {
            "description": item.get("description", ""),
            "eligibility": item.get("eligibility", ""),
            "url": item.get("url"),
            "deadline": item.get("deadline"),
        }
        row = existing.get(key)
        if row is None:
            db.add(models.InstitutionalOffer(
                category=item["category"],
                subcategory=item.get("subcategory"),
                title=item["title"],
                source="referentiel",
                **fields,
            ))
            changed = True
        elif row.source == "admin":
            # Fiche reprise en main par l'administration : on ne touche à rien.
            continue
        elif (row.description, row.eligibility, row.url, row.deadline) != (
            fields["description"], fields["eligibility"],
            fields["url"], fields["deadline"],
        ):
            for name, value in fields.items():
                setattr(row, name, value)
            changed = True
    # Seules les fiches ISSUES du référentiel disparaissent quand elles en
    # sortent : les ajouts de l'administration restent en base.
    for key, row in existing.items():
        if key not in wanted and (row.source or "referentiel") != "admin":
            db.delete(row)
            changed = True
    if changed:
        db.commit()


def seed_minesup_catalogue(db: Session) -> None:
    """Amorce l'explorateur MINESUP quand le catalogue est vide.

    Les universités et écoles sont ensuite gérées dans la console
    d'administration. On n'écrase jamais une correction admin : ce seed ne
    s'exécute que sur une table entièrement vide.
    """
    if db.query(models.MinesupUniversity).count() > 0:
        return
    for university in _load_json("minesup_universities.json"):
        schools = university.get("schools", [])
        row = models.MinesupUniversity(
            slug=university["slug"],
            name=university["name"],
            short_name=university.get("short_name", ""),
            city=university.get("city", ""),
            region=university.get("region", ""),
            description=university.get("description", ""),
            website=university.get("website"),
            source_url=university.get("source_url"),
            sort_order=university.get("sort_order", 0),
            source="referentiel",
        )
        db.add(row)
        db.flush()
        for school in schools:
            db.add(models.MinesupSchool(
                university_id=row.id,
                name=school["name"],
                short_name=school.get("short_name", ""),
                kind=school.get("kind", "Grande école"),
                admission=school.get("admission", ""),
                eligibility=school.get("eligibility", ""),
                url=school.get("url"),
                deadline=school.get("deadline"),
                sort_order=school.get("sort_order", 0),
                source="referentiel",
            ))
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_columns()
    db = SessionLocal()
    try:
        from app.services.domains import backfill_job_domains, seed_domains, sync_new_specialties

        # Le référentiel des domaines est disponible avant le profil démo
        # et avant toute création d'offre. Le resync additif enrichit le
        # référentiel existant sans écraser les corrections de l'admin.
        seed_domains(db)
        sync_new_specialties(db)
        if db.query(models.User).count() == 0:
            seed_database(db)
        backfill_job_domains(db)
        sync_learning_resources(db)
        sync_institutional_offers(db)
        seed_minesup_catalogue(db)
    finally:
        db.close()
    purge_long_dashes()
    # Services d'arrière-plan V2 : bot Telegram, digest quotidien et
    # relève IMAP des candidatures. Démarrage conditionnel (config admin)
    # et arrêt propre.
    from app.services.digest import digest_service
    from app.services.inbound_email import inbound_service
    from app.services.source_scheduler import source_scheduler
    from app.services.telegram_bot import bot_service
    try:
        bot_service.start_if_configured()
    except Exception as exc:  # pragma: no cover
        print(f"Bot Telegram non démarré : {exc}")
    try:
        digest_service.start()
    except Exception as exc:  # pragma: no cover
        print(f"Planificateur de digest non démarré : {exc}")
    try:
        inbound_service.start_if_configured()
    except Exception as exc:  # pragma: no cover
        print(f"Relève IMAP non démarrée : {exc}")
    try:
        source_scheduler.start()
    except Exception as exc:  # pragma: no cover
        print(f"Planificateur de sources non démarré : {exc}")
    yield
    source_scheduler.stop()
    inbound_service.stop()
    bot_service.stop()
    digest_service.stop()


app = FastAPI(
    title="OrientSkill AI : Backend MVP",
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
    interviews.router,
    documents.router,
    public.router,
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

    uvicorn.run("app.main:app", host="127.0.0.1", port=8110)
