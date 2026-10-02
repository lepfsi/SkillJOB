"""Tables SQLAlchemy 2.x (cf. modèle de données §44 du cahier des charges).

Le profil est stocké comme un document JSON structuré (contract API, §2),
ce qui simplifie la mise à jour partielle et conserve un « profil maître »
unique par utilisateur.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

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


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    status: Mapped[str] = mapped_column(String(40), default="identifiee")
    timeline: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # "cv" | "cover_letter"
    title: Mapped[str] = mapped_column(String(255))
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(120), default="")
    type: Mapped[str] = mapped_column(String(30))  # course|certification|project|free
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
