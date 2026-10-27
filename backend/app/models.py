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
    # Téléphone (candidature rapide / contact interne) : jamais exposé aux
    # recruteurs sans accord, voir la messagerie interne.
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
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
    verification_decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Photo de profil (chemin relatif sous backend/uploads/)
    photo_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # CV généraliste partagé avec les recruteurs. Le candidat active
    # explicitement l'option et choisit un de ses CV généralistes : le
    # recruteur ne voit que ce document, jamais les autres.
    cv_visible_to_recruiters: Mapped[bool] = mapped_column(default=False)
    shared_cv_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Préférences de notification : canaux + coordonnées (JSON)
    notification_prefs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # Dernière consultation de la rubrique Notifications : sert au badge
    # des événements non lus (le contenu reste calculé, jamais dupliqué).
    notifications_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Mode de travail de l'agent (accompagnement | preparation | veille).
    # Dans tous les cas, l'agent prépare des brouillons : la validation
    # humaine reste obligatoire avant tout envoi.
    agent_mode: Mapped[str] = mapped_column(String(20), default="preparation")

    # Historique de conversation avec l'agent : conservé par défaut 30
    # jours, ou en mode éphémère (aucune trace en base).
    agent_history_mode: Mapped[str] = mapped_column(String(12), default="persist")
    agent_history_retention_days: Mapped[int] = mapped_column(Integer, default=30)

    # Modération : compte suspendu par l'administration (raison conservée
    # et communiquée). Un compte banni ne peut plus se connecter.
    is_banned: Mapped[bool] = mapped_column(default=False)
    ban_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AgentConversation(Base):
    """Conversation distincte avec l'agent.

    L'utilisateur peut en ouvrir plusieurs, les empiler et les reprendre
    plus tard. Chaque conversation garde ses propres réglages d'historique.
    """

    __tablename__ = "agent_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(160), default="Nouvelle conversation")
    history_mode: Mapped[str] = mapped_column(String(12), default="persist")
    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class AssistantMessage(Base):
    """Message de conversation avec l'agent, conservé par utilisateur.

    Rétention par défaut : 30 jours. Le mode « éphémère » de l'utilisateur
    désactive l'écriture ; l'effacement reste possible à tout moment.
    """

    __tablename__ = "assistant_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(12))      # user | assistant
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


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


class Domain(Base):
    """Domaine professionnel de référence (Informatique, Santé...).

    Le référentiel est préchargé depuis ``data/domains.json`` puis éditable
    dans la console d'administration. Les profils et les offres le
    référencent par identifiant : les libellés restent ainsi homogènes dans
    la recherche, sans dépendre d'un texte libre.
    """

    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(90), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(default=True)
    source: Mapped[str] = mapped_column(String(20), default="referentiel")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Specialty(Base):
    """Spécialité rattachée à un domaine (Cybersécurité, Audit...)."""

    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id"), index=True)
    slug: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(Text, default="")
    aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(default=True)
    source: Mapped[str] = mapped_column(String(20), default="referentiel")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    company: Mapped[str] = mapped_column(String(255))
    company_id: Mapped[Optional[int]] = mapped_column(ForeignKey("companies.id"), nullable=True)
    location: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str] = mapped_column(String(120))
    # Référentiel commun de recherche : domaine principal et spécialité.
    # null = offre historique non encore qualifiée (secteur texte conservé).
    domain_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("domains.id"), nullable=True, index=True
    )
    specialty_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("specialties.id"), nullable=True, index=True
    )
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
    # Photo d'illustration de l'offre, FACULTATIVE : déposée par le
    # publieur (console admin ou espace recruteur) au moment de la
    # publication. Absente = l'offre s'affiche sans visuel.
    photo_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Comment postuler : "platform" (directement sur OrientSkill AI, le
    # recruteur a un compte), "external" (site de l'entreprise), "email".
    # Vide = déduit automatiquement de la source.
    apply_channel: Mapped[str] = mapped_column(String(20), default="")
    # Instructions de candidature externes (URL du formulaire, email RH).
    apply_instructions: Mapped[str] = mapped_column(Text, default="")
    # E-mail du publieur / RH : OrientSkill AI y transmet la candidature
    # automatiquement (CV + lettre en PDF, Reply-To vers le candidat pour
    # que la réponse lui parvienne directement).
    apply_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Mots-clés de routage des candidatures reçues par e-mail. La référence
    # OS-XXXX (calculée depuis l'identifiant) reste le canal prioritaire ;
    # ces mots-clés couvrent les anciens messages sans référence.
    apply_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)


class NotificationLog(Base):
    """Journal des alertes e-mail envoyées (déduplication).

    Un même événement pour un même destinataire et une même offre n'est
    envoyé qu'une fois : les passes planifiées (échéances proches, alertes
    de l'agent) consultent ce journal avant d'écrire.
    """

    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # Type d'événement (expiring, agent, new_match, message, application,
    # verification_decision)
    event: Mapped[str] = mapped_column(String(40), index=True)
    # Offre concernée ; null pour les alertes sans offre (bilan agent).
    job_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class JobReport(Base):
    """Signalement d'une offre par un candidat.

    Le signalement est persistant : il reste visible dans la console
    d'administration jusqu'à son traitement, avec une décision et une note
    conservées pour la traçabilité. Un candidat peut suivre l'état de son
    propre signalement depuis la fiche de l'offre.
    """

    __tablename__ = "job_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    reason: Mapped[str] = mapped_column(String(40))
    details: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="nouveau")
    admin_note: Mapped[str] = mapped_column(Text, default="")
    handled_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )

    job: Mapped["Job"] = relationship()


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    status: Mapped[str] = mapped_column(String(40), default="identifiee")
    timeline: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Canal de soumission réel : "platform" (recruteur sur OrientSkill AI)
    # ou "external" (site/email de l'entreprise). Vide = seulement suivie.
    apply_channel: Mapped[str] = mapped_column(String(20), default="")
    # Horodatage de l'envoi réel. null = candidature identifiée, pas envoyée.
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Identifiants des documents transmis au recruteur (CV, lettre).
    submitted_documents: Mapped[list[int]] = mapped_column(JSON, default=list)
    # Message d'accompagnement écrit par le candidat.
    cover_note: Mapped[str] = mapped_column(Text, default="")
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
    # Instantané du profil validé au moment de la génération. Il permet de
    # réimporter un CV de la bibliothèque sans réinterpréter sa mise en page.
    source_profile: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    template: Mapped[str] = mapped_column(String(20), default="classique")  # cf. CV_TEMPLATES / LETTER_TEMPLATES
    # Couleur d'accent personnelle (vert|bleu|orange|bordeaux|ardoise),
    # null = couleur par défaut du modèle. Ignorée par le modèle ATS.
    accent: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LearningResource(Base):
    __tablename__ = "learning_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skill: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(120), default="")
    type: Mapped[str] = mapped_column(String(30))  # course|certification|project|free
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Origine : "referentiel" (alignée au démarrage sur
    # data/learning_resources.json) ou "admin" (ajoutée dans la console :
    # ni écrasée ni supprimée par la synchronisation).
    source: Mapped[str] = mapped_column(String(20), default="referentiel")
    # Masquage admin : la ligne reste en base (pour ne pas ressusciter au
    # prochain démarrage), mais n'est plus proposée aux candidats.
    hidden: Mapped[bool] = mapped_column(default=False)


class LearningEnrollment(Base):
    """Formation suivie par un candidat et sa preuve (§19).

    Le suivi naît d'une action réelle : le candidat ouvre une formation
    suggérée depuis la page Learning. La preuve (certificat, attestation,
    badge, portfolio) est ensuite DÉCLARÉE par le candidat avec sa
    référence : elle reste vérifiable au lien fourni, et ne devient une
    preuve de profil qu'après validation humaine (§47).
    """

    __tablename__ = "learning_enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    skill: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255))
    provider: Mapped[str] = mapped_column(String(120), default="")
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(30), default="course")
    # Nature du lien : exact | catalogue | search | local (transparence sur
    # ce que le candidat va trouver derrière le bouton).
    link_kind: Mapped[str] = mapped_column(String(20), default="exact")
    status: Mapped[str] = mapped_column(String(20), default="commencee")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    proof_kind: Mapped[str] = mapped_column(String(20), default="aucune")
    proof_reference: Mapped[str] = mapped_column(Text, default="")
    proof_note: Mapped[str] = mapped_column(Text, default="")
    added_to_profile: Mapped[bool] = mapped_column(default=False)


class Setting(Base):
    """Paramètres d'administration (SMTP, LLM, agrégateurs…), un rang par groupe."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AdminNotificationLog(Base):
    """Journal des alertes envoyées à l'équipe d'administration.

    Chaque alerte conserve sa catégorie, ses destinataires et le résultat
    des envois. Le journal est consultable dans la console admin, même
    lorsque le service e-mail est désactivé.
    """

    __tablename__ = "admin_notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    recipients: Mapped[list[str]] = mapped_column(JSON, default=list)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


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
    # Documents joints (PDF) : [{"key", "label", "file"}]. Déposés par
    # l'administration, jamais inventés par la plateforme.
    documents: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # Origine de la fiche : "referentiel" (alignée au démarrage sur
    # data/institutional_offers.json) ou "admin" (créée ou modifiée dans
    # la console : ni écrasée ni supprimée par la synchronisation).
    source: Mapped[str] = mapped_column(String(20), default="referentiel")


class MinesupUniversity(Base):
    """Université d'État du Cameroun, pour l'explorateur MINESUP.

    Le catalogue est éditable dans la console d'administration. Les
    écoles y sont rattachées explicitement : la page publique peut donc
    afficher « université puis grandes écoles et concours » sans deviner
    un rattachement.
    """

    __tablename__ = "minesup_universities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    short_name: Mapped[str] = mapped_column(String(80), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    region: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    website: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(20), default="referentiel")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class MinesupSchool(Base):
    """Grande école ou institut rattaché à une université MINESUP."""

    __tablename__ = "minesup_schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    university_id: Mapped[int] = mapped_column(
        ForeignKey("minesup_universities.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    short_name: Mapped[str] = mapped_column(String(80), default="")
    kind: Mapped[str] = mapped_column(String(80), default="Grande école")
    admission: Mapped[str] = mapped_column(String(255), default="")
    eligibility: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deadline: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(20), default="referentiel")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


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
    # Planification autonome : chaque source activée est interrogée à
    # cet intervalle par le planificateur de collecte.
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    # Fiabilité (§51) : suivi des exécutions
    runs: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    offers_imported: Mapped[int] = mapped_column(Integer, default=0)
    offers_skipped: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str] = mapped_column(String(120), default="")
    last_error: Mapped[str] = mapped_column(Text, default="")
    last_items: Mapped[int] = mapped_column(Integer, default=0)
    last_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    # Requêtes conditionnelles : un flux inchangé répond 304 et n'est
    # ni téléchargé ni reparsé.
    etag: Mapped[str] = mapped_column(String(255), default="")
    last_modified: Mapped[str] = mapped_column(String(255), default="")
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


class BanAppeal(Base):
    """Recours d'un compte suspendu (modération).

    Le compte n'est pas supprimé : la personne peut contester la
    suspension, l'administration garde la trace et peut lever le ban."""

    __tablename__ = "ban_appeals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|accepted|rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)



class InterviewInvite(Base):
    """Invitation à un entretien (shortlist recruteur).

    Le recruiteur propose une date et une heure ; le candidat accepte ou
    demande un autre créneau depuis un lien profond à jeton."""

    __tablename__ = "interview_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    recruiter_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    slot_at: Mapped[datetime] = mapped_column(DateTime)
    duration_min: Mapped[int] = mapped_column(Integer, default=45)
    subject: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    # pending | accepted | declined (autre créneau demandé) | refused
    status: Mapped[str] = mapped_column(String(20), default="pending")
    candidate_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Créneaux proposés par le candidat (dates ISO, heure du Cameroun).
    requested_slots: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Historique lisible des propositions et réponses.
    history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Dernière décision du recruteur sur une demande de créneau.
    recruiter_responded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )


class InboundEmail(Base):
    """Candidature reçue sur la boîte interne puis routée vers l'entreprise.

    Le message brut n'est pas conservé : seuls les métadonnées utiles, le
    corps texte et les pièces jointes déposées sont gardés pour la
    traçabilité et le support. Aucune donnée de profil n'est inventée.
    """

    __tablename__ = "inbound_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(20), default="webhook")  # imap|webhook
    sender_email: Mapped[str] = mapped_column(String(255), index=True)
    sender_name: Mapped[str] = mapped_column(String(255), default="")
    subject: Mapped[str] = mapped_column(String(500), default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    job_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("jobs.id"), nullable=True, index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    application_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("applications.id"), nullable=True
    )
    # Liste de dictionnaires : filename, content_type, path, size.
    attachments: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    routing: Mapped[str] = mapped_column(String(40), default="")  # reference|keywords|titre
    status: Mapped[str] = mapped_column(String(24), default="received")
    detail: Mapped[str] = mapped_column(Text, default="")
    forwarded_to: Mapped[str] = mapped_column(String(255), default="")
    account_created: Mapped[bool] = mapped_column(default=False)
    access_email_sent: Mapped[bool] = mapped_column(default=False)
    forward_email_sent: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
