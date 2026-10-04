"""Schémas Pydantic v2 alignés sur docs/API_CONTRACT.md."""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

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


class RecruiterRegisterIn(RegisterIn):
    """Inscription recruteur. Type ``company`` ou ``agency`` : le compte
    représente l'ENTREPRISE (aucun champ personnel requis — le nom affiché
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
    score: int
    covered: list[str]
    missing: list[str]
    accessibility: Literal["immediate", "with_upskilling", "long_term"]
    recommended_actions: list[str]


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
    contract_type: str
    published_at: datetime
    source: JobSource
    match_score: Optional[int] = None
    company_branding: Optional[JobCompanyOut] = None


class JobDetail(BaseModel):
    id: int
    title: str
    company: str
    location: str
    sector: str
    contract_type: str
    description: str
    requirements: str
    required_skills: list[RequiredSkill]
    published_at: datetime
    deadline: Optional[datetime] = None
    source: JobSource
    salary: Optional[str] = None
    company_branding: Optional[JobCompanyOut] = None


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


class JobDetailResponse(BaseModel):
    job: JobDetail
    match: Optional[MatchOut] = None


# ------------------------------------------------------------- Candidatures

APPLICATION_STATUSES = {
    "identifiee", "cv_prepare", "envoyee", "en_attente",
    "entretien", "offre", "acceptee", "refusee",
}


class TimelineEvent(BaseModel):
    at: datetime
    event: str


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


class ApplicationCreateIn(BaseModel):
    job_id: int


class ApplicationStatusIn(BaseModel):
    status: str


# ---------------------------------------------------------------- Documents

CV_TEMPLATES = ("classique", "ats", "moderne")


class CvTemplateInfo(BaseModel):
    id: str
    name: str
    description: str
    ats_friendly: bool


class CvGenerateIn(BaseModel):
    template: str = "classique"


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
    whatsapp_enabled: Optional[bool] = None
    whatsapp_number: Optional[str] = None
    telegram_enabled: Optional[bool] = None
    telegram_username: Optional[str] = None


# ------------------------------------------------- Sources & collecte

class SourceCreateIn(BaseModel):
    name: str = Field(min_length=1)
    kind: Literal["rss", "json"]
    url: str = Field(min_length=8)
    sector: str = ""
    enabled: bool = True


class SourceUpdateIn(BaseModel):
    name: Optional[str] = None
    kind: Optional[Literal["rss", "json"]] = None
    url: Optional[str] = None
    sector: Optional[str] = None
    enabled: Optional[bool] = None


class ImportUrlIn(BaseModel):
    url: str = Field(min_length=8)


# --------------------------------------------------- Shortlists (V2)

class ShortlistOut(BaseModel):
    id: int
    name: str
    note: str = ""
    created_at: datetime
    items: list[dict[str, Any]] = Field(default_factory=list)


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
    created_at: datetime

    model_config = {"from_attributes": True}


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


class DashboardOut(BaseModel):
    name: str
    new_opportunities: int
    strong_matches: int
    skills_to_improve: list[str]
    ongoing_applications: int
    interviews_to_prepare: int
    market_trends: list[MarketTrendEntry]
    market_week: MarketWeek
    next_action: NextAction
    ai_briefing: str = ""
    profile_completeness: Optional[ProfileCompleteness] = None
    top_matches: list[TopMatchEntry] = Field(default_factory=list)


class InboxEvent(BaseModel):
    id: int
    at: datetime
    kind: Literal["new_job", "strong_match", "trend", "learning", "application"]
    message: str
    job_id: Optional[int] = None


class MarketTrendsOut(BaseModel):
    top_skills: list[dict[str, Any]]
    trending_up: list[str]
    trending_down: list[str]
    sectors: list[dict[str, Any]]
    emerging: list[str]


class LearningResourceOut(BaseModel):
    title: str
    provider: str
    type: Literal["course", "certification", "project", "free"]
    url: Optional[str] = None


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


class LearningOut(BaseModel):
    learn_now: list[LearningItem]
    improve: list[LearningItem] = Field(default_factory=list)
    learn_next: list[LearningItem]
    progress: list[ProgressItem]


# ---------------------------------------------------------------- Assistant


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AssistantIn(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class AssistantLink(BaseModel):
    label: str
    href: str


class AssistantOut(BaseModel):
    reply: str
    suggestions: list[str]
    links: list[AssistantLink]


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
    skills: list[str] = []
    match: dict[str, Any] = Field(default_factory=dict)


class RecruiterApplicationOut(BaseModel):
    id: int
    job_id: int
    job_title: str
    candidate_id: int
    candidate_name: str
    candidate_verified: bool = False
    status: str
    timeline: list[TimelineEvent] = Field(default_factory=list)
    created_at: datetime


class JobCompanyOut(BaseModel):
    id: int
    name: str
    sector: str = ""
    description: str = ""
    has_logo: bool = False


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
    created_at: datetime
    has_profile: bool = False
    applications_count: int = 0
    documents_count: int = 0


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
    category: Literal["fne", "minfop", "minpme", "concours"]
    subcategory: Optional[str] = None
    title: str = Field(min_length=1)
    description: str = ""
    eligibility: str = ""
    url: Optional[str] = None
    deadline: Optional[str] = None


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
    llm_enabled: bool
    smtp_enabled: bool


class AdminSettingsOut(BaseModel):
    smtp: dict[str, Any]
    llm: dict[str, Any]
    aggregators: dict[str, Any]


class AdminSettingsUpdate(BaseModel):
    """Mise à jour d'un groupe (fusion) ; secrets vides = inchangés."""

    data: dict[str, Any]


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
    contract_type: str = "CDI"
    description: str = ""
    requirements: str = ""
    required_skills: list[RequiredSkill] = Field(default_factory=list)
    source_name: str = "Saisie manuelle"
    source_url: str = ""
    salary: Optional[str] = None
    deadline: Optional[datetime] = None


class AdminJobUpdate(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    sector: Optional[str] = None
    contract_type: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    required_skills: Optional[list[RequiredSkill]] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    salary: Optional[str] = None
    deadline: Optional[datetime] = None
