"""Schémas Pydantic v2 alignés sur docs/API_CONTRACT.md."""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- Auth


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=4)
    full_name: str = Field(min_length=1)


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    token: str
    user: UserOut


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


class CareerOut(BaseModel):
    id: int
    title: str
    family: str
    description: str
    required_skills: list[RequiredSkill]
    match: CareerMatch


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


class DocumentOut(BaseModel):
    id: int
    kind: str
    title: str
    content_markdown: str
    job_id: Optional[int] = None
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


class NextAction(BaseModel):
    label: str
    type: Literal["adapt_cv", "learn", "apply", "prepare_interview"]
    job_id: Optional[int] = None
    skill: Optional[str] = None


class DashboardOut(BaseModel):
    name: str
    new_opportunities: int
    strong_matches: int
    skills_to_improve: list[str]
    ongoing_applications: int
    interviews_to_prepare: int
    market_trends: list[MarketTrendEntry]
    next_action: NextAction


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


class LearningOut(BaseModel):
    learn_now: list[LearningItem]
    learn_next: list[LearningItem]
    progress: list[dict[str, str]]


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
