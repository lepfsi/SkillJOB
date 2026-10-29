"""Schémas Pydantic v2 alignés sur docs/API_CONTRACT.md."""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

# ---------------------------------------------------------------- Auth

GENDERS = Literal["homme", "femme"]


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=4)
    full_name: str = Field(min_length=1)
    gender: Optional[GENDERS] = None
    region: Optional[str] = None
    department: Optional[str] = None
    arrondissement: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = Field(default=None, max_length=32)


class RecruiterRegisterIn(RegisterIn):
    """Inscription recruteur. Type ``company`` ou ``agency`` : le compte
    représente l'ENTREPRISE (aucun champ personnel requis : le nom affiché
    est celui de la structure). Type ``independent`` : recruteur
    indépendant, tous les champs personnels s'appliquent."""

    full_name: str = ""  # requis uniquement pour le type independent
    recruiter_type: Literal["company", "agency", "independent"] = "company"
    company_name: str = Field(min_length=1)
    company_sector: str = ""
    company_description: str = ""
    company_location: str = ""
    company_website: Optional[str] = None


class LoginIn(BaseModel):
    email: str
    password: str


class AppealIn(BaseModel):
    """Recours d'un compte suspendu : identité vérifiée par mot de passe."""

    email: str
    password: str
    message: str = Field(min_length=20, max_length=2000)


class AppealOut(BaseModel):
    id: int
    status: Literal["pending", "complement", "accepted", "rejected"]
    message: str
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    admin_note: Optional[str] = None


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    gender: Optional[str] = None
    region: Optional[str] = None
    department: Optional[str] = None
    arrondissement: Optional[str] = None
    city: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
    mfa_enabled: bool = False
    verification_status: str = "none"
    photo_path: Optional[str] = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class LoginResponse(BaseModel):
    """Login étape 1 : soit session directe, soit demande de code MFA."""

    token: Optional[str] = None
    user: Optional[UserOut] = None
    mfa_required: bool = False
    mfa_token: Optional[str] = None


class MfaLoginIn(BaseModel):
    mfa_token: str
    code: str


class MfaCodeIn(BaseModel):
    code: str


class MfaSetupOut(BaseModel):
    secret: str
    otpauth_uri: str
    qr_data_url: str = ""


class MfaEnabledOut(BaseModel):
    recovery_codes: list[str]
    message: str


# ---------------------------------------------------------------- Profil

EXPERIENCE_TYPES = Literal[
    "formal", "informal", "freelance", "volunteer", "apprenticeship", "project"
]
PROFICIENCIES = Literal["debutant", "intermediaire", "avance"]
SKILL_SOURCES = Literal["declared", "inferred", "evidence"]


class EducationItem(BaseModel):
    id: Optional[str] = None
    degree: str = ""
    institution: str = ""
    field: str = ""
    start_year: Optional[int] = None
    end_year: Optional[int] = None


class ExperienceItem(BaseModel):
    id: Optional[str] = None
    title: str = ""
    organization: str = ""
    type: EXPERIENCE_TYPES = "formal"
    description: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    skills: list[str] = Field(default_factory=list)


class CertificationItem(BaseModel):
    id: Optional[str] = None
    name: str = ""
    issuer: str = ""
    year: Optional[int] = None
    # Preuve : lien de vérification (badge, certificat en ligne) et
    # compétences couvertes, renseignés par les formations suivies (§19).
    url: Optional[str] = None
    skills: list[str] = Field(default_factory=list)


class LanguageItem(BaseModel):
    id: Optional[str] = None
    language: str = ""
    level: str = ""


class ProjectItem(BaseModel):
    id: Optional[str] = None
    name: str = ""
    description: str = ""
    url: Optional[str] = None
    skills: list[str] = Field(default_factory=list)


class ProfileSkill(BaseModel):
    skill: str
    category: str = ""
    proficiency: PROFICIENCIES = "debutant"
    source: SKILL_SOURCES = "declared"
    evidence_count: int = 0


class Preferences(BaseModel):
    # Référentiel commun (GET /api/domains) : un domaine principal et
    # plusieurs spécialités associées. ``sectors`` reste conservé pour les
    # profils anciens et la recherche libre.
    domain_id: Optional[int] = None
    specialty_ids: list[int] = Field(default_factory=list)
    domain_other: str = ""
    sectors: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    contract_types: list[str] = Field(default_factory=list)
    remote_ok: bool = False
    linkedin_url: Optional[str] = None


class ProfileOut(BaseModel):
    """Profil maître tel qu'exposé par l'API (contrat §2)."""

    user_id: int = 0
    summary: str = ""
    title: Optional[str] = None
    location: Optional[str] = None
    mobility: Optional[str] = None
    availability: Optional[str] = None
    education: list[EducationItem] = Field(default_factory=list)
    experiences: list[ExperienceItem] = Field(default_factory=list)
    certifications: list[CertificationItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    skills: list[ProfileSkill] = Field(default_factory=list)
    preferences: Preferences = Field(default_factory=Preferences)


class ProfileUpdate(BaseModel):
    """Mise à jour partielle : seuls les champs fournis sont remplacés."""

    summary: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    mobility: Optional[str] = None
    availability: Optional[str] = None
    education: Optional[list[EducationItem]] = None
    experiences: Optional[list[ExperienceItem]] = None
    certifications: Optional[list[CertificationItem]] = None
    languages: Optional[list[LanguageItem]] = None
    projects: Optional[list[ProjectItem]] = None
    skills: Optional[list[ProfileSkill]] = None
    preferences: Optional[Preferences] = None


class ImportReport(BaseModel):
    skills_found: int = 0
    experiences_found: int = 0
    certifications_found: int = 0
    degrees_found: int = 0
    career_fields: list[str] = Field(default_factory=list)


class DraftResponse(BaseModel):
    """Réponse d'import CV / questionnaire : brouillon NON enregistré (§47)."""

    draft: ProfileOut
    report: ImportReport


class ImportTextIn(BaseModel):
    text: str


class CvLibraryImportIn(BaseModel):
    """Réimport d'un CV déjà présent dans la bibliothèque du candidat."""

    document_id: int


# ------------------------------------------------------------ Questionnaire


class Question(BaseModel):
    id: str
    label: str
    type: Literal["text", "textarea", "multi_choice", "choice", "list"]
    options: Optional[list[str]] = None


class QuestionnaireStep(BaseModel):
    id: str
    title: str
    questions: list[Question]


class QuestionnaireOut(BaseModel):
    steps: list[QuestionnaireStep]


class QuestionnaireSubmitIn(BaseModel):
    answers: dict[str, Any]


# ---------------------------------------------------------------- Compétences


class SkillTaxonomyEntry(BaseModel):
    name: str
    category: str
    aliases: list[str]


class SkillMarketEntry(BaseModel):
    name: str
    demand_count: int
    trend: Literal["up", "stable", "down"]
    pct_change: int


# ---------------------------------------------------------------- Carrières


class RequiredSkill(BaseModel):
    name: str
    importance: Literal["core", "preferred"] = "core"
    level: Optional[str] = None


class CareerMatch(BaseModel):
    """Score explicable (§12), aligné sur le matching d'offres (MatchOut)."""

    score: int
    level: Literal["forte", "moyenne", "faible"] = "moyenne"
    covered: list[str]
    partial: list[str] = Field(default_factory=list)
    missing: list[str]
    strengths: list[str] = Field(default_factory=list)
    accessibility: Literal["immediate", "with_upskilling", "long_term"]
    recommended_actions: list[str]
    explanation: str = ""


class RelatedJob(BaseModel):
    id: int
    title: str
    company: str
    location: str
    contract_type: str


class CareerOut(BaseModel):
    id: int
    title: str
    family: str
    description: str
    required_skills: list[RequiredSkill]
    match: CareerMatch
    related_jobs: list[RelatedJob] = Field(default_factory=list)


# ---------------------------------------------------------------- Offres


class JobSource(BaseModel):
    name: str
    url: str


class JobSummary(BaseModel):
    id: int
    title: str
    company: str
    location: str
    sector: str
    domain_id: Optional[int] = None
    specialty_id: Optional[int] = None
    contract_type: str
    published_at: datetime
    deadline: Optional[datetime] = None
    source: JobSource
    match_score: Optional[int] = None
    required_skills: list[RequiredSkill] = Field(default_factory=list)
    company_branding: Optional[JobCompanyOut] = None
    # Photo d'illustration FACULTATIVE de l'offre (déposée à la
    # publication) ; null = offre sans visuel.
    photo_url: Optional[str] = None


class JobDetail(BaseModel):
    id: int
    title: str
    company: str
    location: str
    sector: str
    domain_id: Optional[int] = None
    specialty_id: Optional[int] = None
    contract_type: str
    description: str
    requirements: str
    required_skills: list[RequiredSkill]
    published_at: datetime
    deadline: Optional[datetime] = None
    source: JobSource
    salary: Optional[str] = None
    company_branding: Optional[JobCompanyOut] = None
    photo_url: Optional[str] = None
    # Candidature par e-mail : référence stable à mettre dans l'objet,
    # adresse interne de réception et visuel public téléchargeable.
    apply_channel: str = ""
    apply_email: Optional[str] = None
    apply_keywords: list[str] = Field(default_factory=list)
    email_reference: str = ""
    email_apply_address: str = ""
    poster_url: str = ""


class MatchOut(BaseModel):
    """Score explicable (§12) : jamais un simple pourcentage opaque."""

    score: int
    level: Literal["forte", "moyenne", "faible"]
    covered: list[str]
    partial: list[str]
    missing: list[str]
    strengths: list[str]
    explanation: str
    recommended_actions: list[str]


# ------------------------------------------------------- Signalements d'offre

REPORT_REASONS = {
    "arnaque": "Offre frauduleuse ou demande d'argent",
    "contenu_trompeur": "Contenu trompeur ou incohérent",
    "offre_expiree": "Offre expirée ou déjà pourvue",
    "discrimination": "Discrimination ou propos inapproprié",
    "doublon": "Doublon d'une autre offre",
    "autre": "Autre problème",
}
REPORT_STATUSES = {
    "nouveau": "Nouveau",
    "en_cours": "En cours de traitement",
    "traite": "Traité",
    "rejete": "Rejeté",
}


class JobReportIn(BaseModel):
    reason: str
    details: str = ""


class JobReportUpdateIn(BaseModel):
    status: str
    admin_note: str = ""


class JobReportOut(BaseModel):
    id: int
    job_id: int
    reason: str
    details: str = ""
    status: str
    admin_note: str = ""
    created_at: datetime
    updated_at: datetime
    job_title: Optional[str] = None
    company: Optional[str] = None


class JobReportAdminOut(JobReportOut):
    user_id: int
    user_name: str = ""
    user_email: str = ""


class JobDetailResponse(BaseModel):
    job: JobDetail
    match: Optional[MatchOut] = None
    my_report: Optional[JobReportOut] = None


# ------------------------------------------------------------- Candidatures

APPLICATION_STATUSES = {
    "identifiee", "cv_prepare", "envoyee", "en_attente",
    "entretien", "offre", "acceptee", "refusee",
    "retiree", "declinee",
}


class AgentModeIn(BaseModel):
    mode: Literal["accompagnement", "preparation", "veille", "autonome"]


class AgentModeOut(BaseModel):
    mode: str
    modes: list[dict[str, str]] = Field(default_factory=list)


class AgentPreferencesIn(BaseModel):
    """Mise à jour partielle des réglages de l'agent."""

    mode: Optional[
        Literal["accompagnement", "preparation", "veille", "autonome"]
    ] = None
    scope: Optional[str] = None
    frequency: Optional[str] = None
    validation: Optional[str] = None
    actions: Optional[dict[str, bool]] = None


class AgentPreferencesOut(BaseModel):
    mode: str
    prefs: dict[str, Any]
    modes: list[dict[str, str]] = Field(default_factory=list)
    scopes: list[dict[str, str]] = Field(default_factory=list)
    frequencies: list[dict[str, str]] = Field(default_factory=list)
    validations: list[dict[str, str]] = Field(default_factory=list)
    actions: list[dict[str, str]] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    channels_href: str = "/notifications"


class TimelineEvent(BaseModel):
    at: datetime
    event: str
    by: Optional[str] = None
    reason: Optional[str] = None


class DocumentRef(BaseModel):
    id: int
    kind: str
    title: str


class ApplicationOut(BaseModel):
    id: int
    user_id: int
    job_id: int
    job: JobSummary
    status: str
    timeline: list[TimelineEvent]
    documents: list[DocumentRef]
    # Canal de soumission réel (vide = seulement suivie)
    apply_channel: str = ""
    submitted_at: Optional[datetime] = None
    cover_note: str = ""
    # Comment postuler à cette offre (affiché au candidat)
    apply_instructions: Optional[str] = None
    apply_url: Optional[str] = None
    # E-mail de candidature du publieur (transfert automatique)
    apply_email: Optional[str] = None


class ApplicationCreateIn(BaseModel):
    job_id: int


class PublicApplyIn(BaseModel):
    """Candidature rapide depuis le lien public d'une offre.

    Le compte est créé automatiquement : le candidat complète son profil
    ensuite. Le téléphone reste privé (contact interne).
    """

    full_name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=5, max_length=255)
    phone: str = Field(min_length=6, max_length=32)
    motivation: str = Field(default="", max_length=1000)


class PublicApplyOut(BaseModel):
    token: str
    user: UserOut
    application_id: int
    email_sent: bool = False


class InboundAttachmentIn(BaseModel):
    filename: str = Field(default="piece-jointe", max_length=255)
    content_type: str = Field(default="application/octet-stream", max_length=120)
    content_base64: str = ""


class InboundEmailIn(BaseModel):
    """Message normalisé envoyé par un fournisseur de boîte mail.

    Les fournisseurs utilisent des noms différents : ``from`` reste accepté
    comme alias de ``sender``. Les pièces jointes sont en base64.
    """

    model_config = ConfigDict(populate_by_name=True)

    sender: str = Field(
        default="",
        validation_alias=AliasChoices("sender", "from", "from_email"),
        max_length=500,
    )
    sender_name: str = Field(default="", max_length=255)
    to: str = Field(default="", max_length=500)
    subject: str = Field(default="", max_length=500)
    text: str = Field(default="", max_length=200_000)
    html: str = Field(default="", max_length=200_000)
    message_id: str = Field(default="", max_length=255)
    attachments: list[InboundAttachmentIn] = Field(default_factory=list)


class ApplicationStatusIn(BaseModel):
    status: str
    reason: str = Field(default="", max_length=1000)


class ApplicationAdminStatusIn(BaseModel):
    """Arbitrage admin : toute transition est possible, avec motif."""

    status: str
    reason: str = Field(min_length=3, max_length=1000)


class ApplicationSubmitIn(BaseModel):
    """Soumission réelle d'une candidature : documents + message."""
    cv_document_id: int
    cover_letter_document_id: Optional[int] = None
    cover_note: str = ""


# ---------------------------------------------------------------- Documents

CV_TEMPLATES = (
    "classique", "ats", "moderne", "deux_colonnes", "elegant", "compact",
)
LETTER_TEMPLATES = ("classique", "moderne", "email")
ACCENT_KEYS = (
    "vert", "bleu", "orange", "bordeaux", "ardoise", "violet",
    "turquoise", "rouge", "rose", "indigo", "ambre", "menthe", "brun",
)


class CvTemplateInfo(BaseModel):
    id: str
    name: str
    description: str
    ats_friendly: bool
    # Aperçu côté interface : 1 ou 2 colonnes de mise en page.
    columns: int = 1


class LetterTemplateInfo(BaseModel):
    id: str
    name: str
    description: str


class CvGenerateIn(BaseModel):
    template: str = "classique"
    # Couleur d'accent personnelle (ignorée par le modèle ATS).
    accent: Optional[str] = None


class CoverLetterIn(BaseModel):
    template: str = "classique"
    accent: Optional[str] = None


class JobParseIn(BaseModel):
    description: str = Field(min_length=10)


class BusinessPlanIn(BaseModel):
    activity: str = Field(min_length=3)
    target: str = ""
    capital: str = ""
    location: str = ""


class NotificationPrefsIn(BaseModel):
    email_enabled: Optional[bool] = None
    email: Optional[str] = None
    # Fréquence des alertes emploi : immédiate (au fil de l'eau, plafonnée
    # à un e-mail par jour) ou résumé quotidien.
    email_frequency: Optional[Literal["immediate", "daily"]] = None
    # Seuil minimum de correspondance pour les alertes emploi par e-mail.
    # 61 = strictement plus de 60 %. Entre 45 % et 60 %, l'offre reste
    # visible dans l'application sans e-mail.
    email_min_match: Optional[int] = Field(default=None, ge=61, le=100)
    whatsapp_enabled: Optional[bool] = None
    whatsapp_number: Optional[str] = None
    telegram_enabled: Optional[bool] = None
    telegram_username: Optional[str] = None
    # Opt-in e-mail PAR ÉVÉNEMENT (false = reste in-app uniquement).
    # Les clés autorisées dépendent du rôle : voir EVENT_CATALOGS.
    events: Optional[dict[str, bool]] = None


class BanIn(BaseModel):
    """Suspension d'un compte par l'administration : motif communiqué."""
    reason: str = Field(min_length=5, max_length=500)


class LearningResourceIn(BaseModel):
    """Formation ajoutée à la console : compétence ciblée + lien réel."""
    skill: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=3, max_length=255)
    provider: str = Field(default="", max_length=120)
    type: Literal["course", "certification", "project", "free"] = "course"
    url: str = Field(default="", max_length=600)


class LearningResourceUpdateIn(BaseModel):
    skill: Optional[str] = None
    title: Optional[str] = None
    provider: Optional[str] = None
    type: Optional[Literal["course", "certification", "project", "free"]] = None
    url: Optional[str] = None
    hidden: Optional[bool] = None


# ------------------------------------------------- Sources & collecte

class SourceCreateIn(BaseModel):
    name: str = Field(min_length=1)
    kind: Literal["rss", "json"]
    url: str = Field(min_length=8)
    sector: str = ""
    enabled: bool = True
    interval_minutes: int = Field(default=60, ge=5, le=1440)


class SourceUpdateIn(BaseModel):
    name: Optional[str] = None
    kind: Optional[Literal["rss", "json"]] = None
    url: Optional[str] = None
    sector: Optional[str] = None
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = Field(default=None, ge=5, le=1440)


class SourceTestIn(BaseModel):
    kind: Literal["rss", "json"]
    url: str = Field(min_length=8)


class ImportUrlIn(BaseModel):
    url: str = Field(min_length=8)


# --------------------------------------------------- Shortlists (V2)

class ShortlistOut(BaseModel):
    id: int
    name: str
    note: str = ""
    created_at: datetime
    items: list[dict[str, Any]] = Field(default_factory=list)


# ------------------------------------------- Invitations à un entretien

class InterviewInviteIn(BaseModel):
    candidate_id: int
    job_id: int
    slot_at: datetime
    duration_min: int = Field(default=45, ge=15, le=240)
    subject: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=20, max_length=4000)


class InterviewInviteOut(BaseModel):
    id: int
    token: str
    candidate_id: int
    candidate_name: str = ""
    job_id: int
    job_title: str = ""
    company: str = ""
    recruiter_name: str = ""
    slot_at: datetime
    duration_min: int = 45
    subject: str
    message: str
    status: Literal["pending", "accepted", "declined", "refused"]
    candidate_note: Optional[str] = None
    requested_slots: list[datetime] = Field(default_factory=list)
    history: list[dict[str, Any]] = Field(default_factory=list)
    awaiting_recruiter: bool = False
    created_at: datetime
    responded_at: Optional[datetime] = None
    recruiter_responded_at: Optional[datetime] = None
    email_sent: bool = False
    # Téléchargement .ics public (le jeton fait office de secret).
    calendar_url: str = ""


class InterviewRespondIn(BaseModel):
    decision: Literal["accepted", "declined", "refused"]
    note: str = Field(default="", max_length=1000)
    # Obligatoire pour « declined » : une demande d'autre créneau doit
    # toujours porter une proposition explicite.
    requested_slots: list[datetime] = Field(default_factory=list)


class InterviewRecruiterRespondIn(BaseModel):
    action: Literal["accept_requested", "propose", "refuse"]
    slot_at: Optional[datetime] = None
    note: str = Field(default="", max_length=1000)


class ShortlistCreateIn(BaseModel):
    name: str = Field(min_length=1)
    note: str = ""


class ShortlistItemIn(BaseModel):
    candidate_id: int


class DocumentOut(BaseModel):
    id: int
    kind: str
    title: str
    content_markdown: str
    job_id: Optional[int] = None
    template: str = "classique"
    # Couleur d'accent choisie (null = couleur du modèle).
    accent: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CvVisibilityIn(BaseModel):
    """Choix explicite du candidat : partager UN CV généraliste.

    ``document_id`` doit appartenir au candidat, être de type CV et ne pas
    être rattaché à une offre. Un CV ciblé reste privé.
    """

    visible: bool = False
    document_id: Optional[int] = None


class CvSharedOut(BaseModel):
    id: int
    title: str
    template: str = "classique"
    accent: Optional[str] = None
    created_at: datetime
    download_url: str


class CvVisibilityOut(BaseModel):
    visible: bool = False
    document_id: Optional[int] = None
    document: Optional[DocumentOut] = None


class InterviewPrepOut(BaseModel):
    likely_questions: list[str]
    technical: list[str]
    behavioral: list[str]
    pitch: str
    prep_tips: list[str]


# ---------------------------------------------------------- Dashboard / etc.


class MarketTrendEntry(BaseModel):
    name: str
    trend: Literal["up", "stable", "down"]
    pct_change: int
    count: int = 0
    # Nombre réel d'offres qui demandent la compétence sur la période
    # (distinct de `count`, pondéré par l'importance core/preferred).
    offers: int = 0


class MarketWeek(BaseModel):
    """Indicateurs réels de la semaine : chaque chiffre est traçable."""

    offers_in_period: int
    previous_period_offers: int = 0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    period_label: str = ""
    sectors: list[dict[str, Any]] = Field(default_factory=list)


class NextAction(BaseModel):
    label: str
    type: Literal["adapt_cv", "learn", "apply", "prepare_interview"]
    job_id: Optional[int] = None
    skill: Optional[str] = None
    href: Optional[str] = None


class ProfileCompleteness(BaseModel):
    """État de complétude du profil : chaque case vérifiable."""

    score: int
    checked: list[dict[str, Any]] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class TopMatchEntry(BaseModel):
    id: int
    title: str
    company: str
    location: str
    contract_type: str
    score: int


class SkillGapEntry(BaseModel):
    """Écart de compétence expliqué et rattaché à sa source réelle."""

    skill: str
    reason: str
    source: Literal["career", "job"]
    source_label: str
    score: int


class DashboardOut(BaseModel):
    name: str
    verified: bool = False
    new_opportunities: int
    strong_matches: int
    skills_to_improve: list[str]
    skill_gaps: list[SkillGapEntry] = Field(default_factory=list)
    ongoing_applications: int
    interviews_to_prepare: int
    market_trends: list[MarketTrendEntry]
    market_week: MarketWeek
    next_action: NextAction
    ai_briefing: str = ""
    ai_label: str = ""
    profile_completeness: Optional[ProfileCompleteness] = None
    top_matches: list[TopMatchEntry] = Field(default_factory=list)
    # Première ressource de formation réelle pour l'écart prioritaire, avec
    # son lien profond stable. null si aucune ressource n'est disponible.
    learning_focus: Optional[dict[str, Any]] = None
    # Mode autonome : ce que l'agent vient de préparer automatiquement.
    # null si le mode autonome est inactif ou que rien n'était à préparer.
    autonomous_prepared: Optional[dict[str, Any]] = None


class InboxEvent(BaseModel):
    id: int
    at: datetime
    kind: Literal[
        "new_job", "strong_match", "trend", "learning", "application",
        "expiring", "report", "appeal", "interview", "verification",
    ]
    message: str
    job_id: Optional[int] = None
    unread: bool = False


class NotificationSummary(BaseModel):
    count: int = 0
    seen_at: Optional[datetime] = None


class MarketTrendsOut(BaseModel):
    top_skills: list[dict[str, Any]]
    trending_up: list[str]
    trending_down: list[str]
    sectors: list[dict[str, Any]]
    emerging: list[str]


class LearningResourceOut(BaseModel):
    # Clé publique stable : permet un lien profond vers LA ressource exacte
    # depuis l'assistant, le tableau de bord ou une offre.
    key: str
    title: str
    provider: str
    type: Literal["course", "certification", "project", "free"]
    url: Optional[str] = None
    # Nature du lien : la formation exacte, un catalogue, une recherche, un
    # organisme de formation sur place ou une activité guidée (§19).
    link_kind: Literal["exact", "catalogue", "search", "local", "interne"] = "exact"
    link_kind_label: str = ""


class LearningItem(BaseModel):
    skill: str
    reason: str
    resources: list[LearningResourceOut]


class SkillEvidence(BaseModel):
    kind: Literal["experience", "project", "certification", "education"]
    label: str


class ProgressItem(BaseModel):
    """Progression vérifiable par compétence (evidences + prochaine étape)."""

    skill: str
    level: str
    status: str                       # "verifiee" | "a_confirmer" | "en_progression"
    status_label: str
    demand: int                       # offres actives demandant la compétence
    evidences: list[SkillEvidence]
    next_step: str


# ------------------------------------------------ Formations suivies (§19)

class EnrollmentIn(BaseModel):
    """Ouverture d'une formation recommandée (le lien est réel)."""

    skill: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=255)
    provider: str = ""
    url: Optional[str] = None
    kind: Literal["course", "certification", "project", "free"] = "course"
    link_kind: Literal["exact", "catalogue", "search", "local", "interne"] = "exact"


class EnrollmentPatch(BaseModel):
    """Avancement et preuve déclarés par le candidat."""

    status: Optional[Literal["commencee", "en_cours", "terminee"]] = None
    proof_kind: Optional[
        Literal["aucune", "certificat", "attestation", "badge", "portfolio", "autre"]
    ] = None
    proof_reference: Optional[str] = None
    proof_note: Optional[str] = None


class EnrollmentOut(BaseModel):
    id: int
    skill: str
    title: str
    provider: str = ""
    url: Optional[str] = None
    kind: str
    link_kind: str
    link_kind_label: str = ""
    status: str
    status_label: str = ""
    started_at: datetime
    completed_at: Optional[datetime] = None
    proof_kind: str = "aucune"
    proof_label: str = ""
    proof_reference: str = ""
    proof_note: str = ""
    verifiable: bool = False
    added_to_profile: bool = False


class EnrollmentStats(BaseModel):
    total: int = 0
    in_progress: int = 0
    completed: int = 0
    verifiable: int = 0
    added_to_profile: int = 0


class EnrollmentToProfileOut(BaseModel):
    enrollment: EnrollmentOut
    profile: ProfileOut


class LearningOut(BaseModel):
    learn_now: list[LearningItem]
    improve: list[LearningItem] = Field(default_factory=list)
    learn_next: list[LearningItem]
    progress: list[ProgressItem]
    enrollments: list[EnrollmentOut] = Field(default_factory=list)
    stats: EnrollmentStats = Field(default_factory=EnrollmentStats)
    proof_kinds: list[dict[str, str]] = Field(default_factory=list)
    link_kinds: list[dict[str, str]] = Field(default_factory=list)
    statuses: list[dict[str, str]] = Field(default_factory=list)


# ---------------------------------------------------------------- Assistant


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AssistantIn(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    # Conversation ciblée : si absente, la plus récente est reprise.
    conversation_id: Optional[int] = None
    # Page depuis laquelle l'assistant est ouvert (libellé court en
    # français, ex. « Entrepreneuriat ») : l'agent y ancre ses conseils.
    context: Optional[str] = Field(default=None, max_length=120)


class AssistantLink(BaseModel):
    label: str
    href: str


class AssistantOut(BaseModel):
    reply: str
    suggestions: list[str]
    links: list[AssistantLink]
    actions: list[dict[str, Any]] = Field(default_factory=list)
    mode: str = "local"  # "llm" (modèle connecté) | "local" (moteur de règles)


class AssistantHistoryItem(ChatMessage):
    created_at: datetime


class AssistantHistoryOut(BaseModel):
    messages: list[AssistantHistoryItem]
    mode: Literal["persist", "ephemeral"]
    retention_days: int


class AssistantHistorySettingsIn(BaseModel):
    mode: Literal["persist", "ephemeral"]


class AssistantConversationOut(BaseModel):
    id: int
    title: str
    history_mode: Literal["persist", "ephemeral"]
    retention_days: int
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    last_message: Optional[str] = None


class AssistantConversationCreateIn(BaseModel):
    title: str = Field(default="Nouvelle conversation", max_length=160)


class AssistantConversationUpdateIn(BaseModel):
    title: Optional[str] = Field(default=None, max_length=160)
    history_mode: Optional[Literal["persist", "ephemeral"]] = None
    retention_days: Optional[int] = Field(default=None, ge=1, le=365)


class AssistantConversationHistoryOut(BaseModel):
    conversation: AssistantConversationOut
    messages: list[AssistantHistoryItem]


# ---------------------------------------------- Vérification de profil

class VerificationStatusOut(BaseModel):
    status: Literal["none", "pending", "verified", "rejected"]
    requested_at: Optional[datetime] = None
    note: Optional[str] = None


# ------------------------------------------------------------- Recruteur

class CompanyOut(BaseModel):
    id: int
    name: str
    sector: str = ""
    description: str = ""
    location: str = ""
    website: Optional[str] = None
    has_logo: bool = False


class CompanyUpdateIn(BaseModel):
    name: Optional[str] = None
    sector: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None


class RecruiterCandidateOut(BaseModel):
    user_id: int
    full_name: str
    title: Optional[str] = None
    location: Optional[str] = None
    verified: bool = False
    summary: str = ""
    photo_url: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    skill_details: list[dict[str, Any]] = Field(default_factory=list)
    match: dict[str, Any] = Field(default_factory=dict)
    # Faits du profil validé, exposés au recruteur sans coordonnée.
    mobility: Optional[str] = None
    availability: Optional[str] = None
    education: list[dict[str, Any]] = Field(default_factory=list)
    experiences: list[dict[str, Any]] = Field(default_factory=list)
    certifications: list[dict[str, Any]] = Field(default_factory=list)
    languages: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[dict[str, Any]] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    experience_count: int = 0
    education_count: int = 0
    certification_count: int = 0
    top_certifications: list[str] = Field(default_factory=list)
    cv: Optional[CvSharedOut] = None
    updated_at: Optional[datetime] = None


class RecruiterApplicationOut(BaseModel):
    id: int
    job_id: int
    job_title: str
    job_location: str = ""
    job_contract_type: str = ""
    job_deadline: Optional[datetime] = None
    candidate_id: int
    candidate_name: str
    candidate_title: str = ""
    candidate_verified: bool = False
    candidate_photo_url: str = ""
    status: str
    status_label: str = ""
    is_new: bool = False
    match_score: Optional[int] = None
    match_level: str = ""
    timeline: list[TimelineEvent] = Field(default_factory=list)
    created_at: datetime
    submitted_at: Optional[datetime] = None
    cover_note: str = ""
    apply_channel: str = ""
    apply_url: str = ""
    apply_email: str = ""
    apply_instructions: str = ""


class RecruiterApplicationGroupOut(BaseModel):
    job_id: int
    job_title: str
    job_location: str = ""
    job_contract_type: str = ""
    job_deadline: Optional[datetime] = None
    total: int = 0
    new_count: int = 0
    latest_at: Optional[datetime] = None
    applications: list[RecruiterApplicationOut] = Field(default_factory=list)


class RecruiterApplicationsGroupedOut(BaseModel):
    items: list[RecruiterApplicationGroupOut] = Field(default_factory=list)
    page: int = 1
    page_size: int = 10
    total_groups: int = 0
    total_applications: int = 0
    total_new: int = 0
    has_more: bool = False


class JobCompanyOut(BaseModel):
    id: int
    name: str
    sector: str = ""
    description: str = ""
    has_logo: bool = False


# ------------------------------------------------- Domaines et spécialités

class SpecialtyOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    sort_order: int = 0
    active: bool = True


class DomainOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    sort_order: int = 0
    active: bool = True
    specialties: list[SpecialtyOut] = Field(default_factory=list)


class SpecialtyIn(BaseModel):
    slug: Optional[str] = None
    name: str = Field(min_length=1)
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    sort_order: int = 0
    active: bool = True


class DomainIn(BaseModel):
    slug: Optional[str] = None
    name: str = Field(min_length=1)
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    sort_order: int = 0
    active: bool = True


# ---------------------------------------------------------------- Admin

class MessageOut(BaseModel):
    id: int
    sender_id: int
    recipient_id: int
    body: str
    job_id: Optional[int] = None
    read: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreateIn(BaseModel):
    recipient_id: int
    body: str = Field(min_length=1)
    job_id: Optional[int] = None


class ThreadOut(BaseModel):
    other_user_id: int
    other_name: str
    other_role: str
    other_company: Optional[dict[str, Any]] = None
    last_body: str
    last_at: Optional[datetime] = None
    unread: int


class ThreadViewOut(BaseModel):
    messages: list[MessageOut]
    identity: dict[str, Any]

class AdminUserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    gender: Optional[str] = None
    mfa_enabled: bool = False
    verification_status: str = "none"
    # Modération : suspension du compte (motif communiqué à la connexion).
    is_banned: bool = False
    ban_reason: str = ""
    created_at: datetime
    has_profile: bool = False
    applications_count: int = 0
    documents_count: int = 0


class AdminAppealOut(BaseModel):
    id: int
    user_id: int
    user_name: str
    user_email: str
    user_role: str = "candidate"
    user_created_at: Optional[datetime] = None
    is_banned: bool = True
    applications_count: int = 0
    documents_count: int = 0
    ban_reason: str = ""
    kind: str = "suspension"
    status: Literal["pending", "complement", "accepted", "rejected"]
    message: str
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    reviewed_by_name: Optional[str] = None
    admin_note: Optional[str] = None
    age_hours: float = 0
    is_open: bool = False
    history: list[dict] = Field(default_factory=list)


class AppealDecisionIn(BaseModel):
    decision: Literal["accepted", "rejected", "complement"]
    note: str = Field(default="", max_length=1000)


class AdminVerificationOut(BaseModel):
    user_id: int
    full_name: str
    email: str
    requested_at: Optional[datetime] = None
    status: str
    note: Optional[str] = None
    doc_url: str
    profile: Optional[dict[str, Any]] = None


class VerificationDecisionIn(BaseModel):
    """Décision de vérification : le motif est OBLIGATOIRE pour un refus
    (visible du candidat) et optionnel pour une approbation."""
    note: str = ""


# ---------------- Contenus publics (Programmes, Entrepreneuriat)

class InstitutionalCreateIn(BaseModel):
    # La taxonomie des institutions vit dans le référentiel
    # (data/institutional_offers.json) et dans la console admin : on
    # accepte la clé telle quelle pour ne jamais bloquer un ajout futur.
    category: str = Field(min_length=1)
    subcategory: Optional[str] = None
    title: str = Field(min_length=1)
    description: str = ""
    eligibility: str = ""
    url: Optional[str] = None
    deadline: Optional[str] = None


class MinesupUniversityIn(BaseModel):
    slug: Optional[str] = None
    name: str = Field(min_length=1)
    short_name: str = ""
    city: str = ""
    region: str = ""
    description: str = ""
    website: Optional[str] = None
    source_url: Optional[str] = None
    sort_order: int = 0


class MinesupSchoolIn(BaseModel):
    name: str = Field(min_length=1)
    short_name: str = ""
    kind: str = "Grande école"
    admission: str = ""
    eligibility: str = ""
    url: Optional[str] = None
    deadline: Optional[str] = None
    sort_order: int = 0


class EntrepreneurCreateIn(BaseModel):
    kind: Literal["concours", "accompagnement", "financement", "formation"]
    title: str = Field(min_length=1)
    description: str = ""
    organizer: str = ""
    url: Optional[str] = None
    sectors: list[str] = Field(default_factory=list)


class AdminStats(BaseModel):
    users: int
    profiles: int
    jobs: int
    applications: int
    documents: int
    learning_resources: int
    open_reports: int = 0
    llm_enabled: bool
    smtp_enabled: bool


class AdminSettingsOut(BaseModel):
    smtp: dict[str, Any]
    inbound: dict[str, Any] = Field(default_factory=dict)
    llm: dict[str, Any]
    aggregators: dict[str, Any]
    notifications: dict[str, Any] = Field(default_factory=dict)


class AdminSettingsUpdate(BaseModel):
    """Mise à jour d'un groupe (fusion) ; secrets vides = inchangés."""

    data: dict[str, Any]


class AdminAlertRecipientIn(BaseModel):
    name: str = ""
    email: str = Field(min_length=3, max_length=255)
    categories: list[str] = Field(default_factory=list)


class AdminAlertSettingsIn(BaseModel):
    enabled: bool = True
    categories: dict[str, bool] = Field(default_factory=dict)
    recipients: list[AdminAlertRecipientIn] = Field(default_factory=list)


class AdminAlertTestIn(BaseModel):
    category: str = "critical"


class TestResult(BaseModel):
    ok: bool
    detail: str


class ConnectorStatus(BaseModel):
    id: str
    name: str
    kind: str            # llm | smtp | messaging | jobs | credentials | data
    status: str          # operationnel | configure | roadmap
    phase: str           # V1 | V2 | V3
    description: str
    configurable: bool


class AdminJobCreate(BaseModel):
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    location: str = ""
    sector: str = ""
    domain_id: Optional[int] = None
    specialty_id: Optional[int] = None
    contract_type: str = "CDI"
    description: str = ""
    requirements: str = ""
    required_skills: list[RequiredSkill] = Field(default_factory=list)
    source_name: str = "Saisie manuelle"
    source_url: str = ""
    # Candidature : "platform" (compte recruteur lié), "external"
    # (site/e-mail du publieur). Vide = déduit automatiquement.
    apply_channel: str = ""
    apply_instructions: str = ""
    apply_email: Optional[str] = None
    apply_keywords: list[str] = Field(default_factory=list)
    salary: Optional[str] = None
    deadline: Optional[datetime] = None


class RecruiterJobCreate(AdminJobCreate):
    """Publication depuis l'espace recruteur.

    L'entreprise est celle du compte : le champ `company` du formulaire
    n'est pas demandé à l'utilisateur et peut rester vide.
    """
    company: str = ""


class AdminJobUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    sector: Optional[str] = None
    domain_id: Optional[int] = None
    specialty_id: Optional[int] = None
    contract_type: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    required_skills: Optional[list[RequiredSkill]] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    apply_channel: Optional[str] = None
    apply_instructions: Optional[str] = None
    apply_email: Optional[str] = None
    apply_keywords: Optional[list[str]] = None
    salary: Optional[str] = None
    deadline: Optional[datetime] = None


# ------------------------------------------------- Notifications admin (§21)

class AdminNotificationOut(BaseModel):
    id: int
    category: str
    category_label: str
    subject: str
    body: str
    detail: str
    recipients: list[str]
    status: str
    sent_count: int
    failed_count: int
    is_unread: bool
    marked_read_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    created_at: datetime
    href: Optional[str] = None

    model_config = {"from_attributes": True}


class AdminNotificationPage(BaseModel):
    total: int
    unread: int
    per_category: dict[str, dict[str, int]]
    items: list[AdminNotificationOut]
    limit: int
    offset: int
    retention_days: int
    categories: list[dict[str, str]]

    model_config = {"from_attributes": True}


class AdminNotificationStats(BaseModel):
    total: int
    unread: int
    per_category: dict[str, dict[str, int]]

    model_config = {"from_attributes": True}


class AdminNotificationAction(BaseModel):
    ok: bool
    log_id: int
    action: str

    model_config = {"from_attributes": True}

