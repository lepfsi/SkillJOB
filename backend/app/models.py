"""Tables SQLAlchemy 2.x (cf. modèle de données §44 du cahier des charges).

Le profil est stocké comme un document JSON structuré (contract API, §2),
ce qui simplifie la mise à jour partielle et conserve un « profil maître »
unique par utilisateur.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    """Horodatage UTC naïf (compatible avec SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="candidate")
    gender: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # homme | femme
    # Localisation structurée Cameroun (région -> département -> arrondissement -> ville)
    region: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    arrondissement: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Sécurité MFA (TOTP RFC 6238)
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(default=False)
    recovery_codes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    # Vérification de profil (lutte contre les faux comptes)
    verification_status: Mapped[Optional[str]] = mapped_column(String(20), default="none")  # none|pending|verified|rejected
    verification_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    identity_doc_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Photo de profil (chemin relatif sous backend/uploads/)
    photo_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Préférences de notification : canaux + coordonnées (JSON)
    notification_prefs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Company(Base):
    """Espace recruteur : entreprise liée à un compte recruteur (branding)."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str] = mapped_column(String(255), default="")
    website: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Profile(Base):
    __tablename__ = "profiles"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mobility: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    availability: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    education: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    experiences: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    certifications: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    languages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    projects: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    skills: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    preferences: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Skill(Base):
    """Copie en base de la taxonomie (trace) ; le moteur lit le fichier JSON."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(80), default="Autre")
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)


class Career(Base):
    __tablename__ = "careers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    family: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    required_skills: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    education_types: Mapped[list[str]] = mapped_column(JSON, default=list)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255))
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"), nullable=True)
    location: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(120))
    contract_type: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[str] = mapped_column(Text, default="")
    required_skills: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    published_at: Mapped[datetime] = mapped_column(DateTime)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    source_name: Mapped[str] = mapped_column(String(120), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    salary: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    # Déduplication multi-source (§50) : même offre sur plusieurs sources
    dedup_key: Mapped[Optional[str]] = mapped_column(String(80), index=True, nullable=True)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    status: Mapped[str] = mapped_column(String(40), default="identifiee")
    timeline: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    job: Mapped["Job"] = relationship()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # "cv" | "cover_letter"
    title: Mapped[str] = mapped_column(String(255))
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    template: Mapped[str] = mapped_column(String(20), default="classique")  # classique | ats | moderne
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(120), default="")
    type: Mapped[str] = mapped_column(String(30))  # course|certification|project|free
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Setting(Base):
    """Paramètres d'administration (SMTP, LLM, agrégateurs…), un rang par groupe."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Message(Base):
    """Messagerie interne recruteur ↔ talent (contact direct, plateforme)."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class InstitutionalOffer(Base):
    """Programmes publics camerounais : concours (fonction publique,
    grandes écoles, ministères techniques), FNE, MINFOP, MINPME (§61)."""

    __tablename__ = "institutional_offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(20), index=True)  # fne|minfop|minpme|concours
    subcategory: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    eligibility: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deadline: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)


class SourceConfig(Base):
    """Connecteur de collecte multi-source (§50) : flux RSS, API JSON.
    Chaque source est traçable et scorée en fiabilité (succès/échecs)."""

    __tablename__ = "source_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(20))       # rss | json
    url: Mapped[str] = mapped_column(Text)
    sector: Mapped[str] = mapped_column(String(120), default="")
    enabled: Mapped[bool] = mapped_column(default=True)
    # Fiabilité (§51) : suivi des exécutions
    runs: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    offers_imported: Mapped[int] = mapped_column(Integer, default=0)
    offers_skipped: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Shortlist(Base):
    """Shortlist recruteur (§20) : listes de candidats présélectionnés."""

    __tablename__ = "shortlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ShortlistItem(Base):
    __tablename__ = "shortlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shortlist_id: Mapped[int] = mapped_column(ForeignKey("shortlists.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    added_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EntrepreneurResource(Base):
    """Espace entrepreneuriat (§11bis) : concours, accompagnements,
    financements, préparation bancaire."""

    __tablename__ = "entrepreneur_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)  # concours|accompagnement|financement|formation
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    organizer: Mapped[str] = mapped_column(String(160), default="")
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sectors: Mapped[list[str]] = mapped_column(JSON, default=list)
