from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    RECRUITER = "recruiter"
    RESEARCHER = "researcher"
    VIEWER = "viewer"

class CandidateStatus(str, Enum):
    NEW = "new"
    REVIEWED = "reviewed"
    CONTACTED = "contacted"
    IN_PROCESS = "in_process"
    PLACED = "placed"
    ARCHIVED = "archived"

class SeniorityLevel(str, Enum):
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    DIRECTOR = "director"
    VP = "vp"
    C_LEVEL = "c_level"

class ParseStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: EmailStr
    name: str
    role: UserRole
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole = UserRole.RECRUITER

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: User

class PreviousCompany(BaseModel):
    company_name: str
    title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None

class ResumeFile(BaseModel):
    file_name: str
    file_path: str
    file_type: str
    upload_date: datetime

class RecruiterNote(BaseModel):
    note: str
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AIClassification(BaseModel):
    industry: Optional[str] = None
    functional_area: Optional[str] = None
    seniority: Optional[SeniorityLevel] = None
    confidence_score: float = 0.0
    suggested_tags: List[str] = []
    classified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_by_recruiter: bool = False

class Candidate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "México"
    linkedin_url: Optional[str] = None
    current_company: Optional[str] = None
    current_title: Optional[str] = None
    years_experience: Optional[int] = None
    industry: Optional[str] = None
    functional_area: Optional[str] = None
    seniority: Optional[SeniorityLevel] = None
    skills: List[str] = []
    languages: List[str] = []
    previous_companies: List[PreviousCompany] = []
    resume_files: List[ResumeFile] = []
    salary_data: Optional[str] = None
    notes: List[RecruiterNote] = []
    tags: List[str] = []
    status: CandidateStatus = CandidateStatus.NEW
    source: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_classification: Optional[AIClassification] = None
    embedding: Optional[List[float]] = None
    embedding_updated_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None

class CandidateCreate(BaseModel):
    full_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: str = "México"
    linkedin_url: Optional[str] = None
    source: Optional[str] = None

class CandidateUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    linkedin_url: Optional[str] = None
    current_company: Optional[str] = None
    current_title: Optional[str] = None
    years_experience: Optional[int] = None
    industry: Optional[str] = None
    functional_area: Optional[str] = None
    seniority: Optional[SeniorityLevel] = None
    skills: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    salary_data: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[CandidateStatus] = None

class ResumeUpload(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    candidate_id: Optional[str] = None
    file_name: str
    file_path: str
    file_type: str
    upload_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    parse_status: ParseStatus = ParseStatus.PENDING
    extracted_text: Optional[str] = None
    uploaded_by: str

class Industry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name_es: str
    name_en: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FunctionalArea(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name_es: str
    name_en: str
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class JobProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    description: str
    requirements: List[str] = []
    preferred_industry: Optional[str] = None
    preferred_functional_area: Optional[str] = None
    preferred_seniority: Optional[SeniorityLevel] = None
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class CandidateMatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    job_profile_id: str
    candidate_id: str
    match_score: float
    reasons: List[str] = []
    gaps: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SearchQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    query_name: str
    filters: Dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ActivityLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    action: str
    entity_type: str
    entity_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Optional[Dict[str, Any]] = None

class DuplicateSuggestionModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    new_candidate_id: str
    potential_duplicate_id: str
    match_type: str  # email, linkedin, phone, name_similarity
    confidence: float
    reason: str
    status: str = "pending"  # pending, merged, dismissed
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_by: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SavedSearch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    user_id: str
    name: str
    query: Optional[str] = None
    filters: Dict[str, Any]
    use_semantic: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class IndustryCreate(BaseModel):
    name_es: str
    name_en: str
    description: Optional[str] = None

class FunctionalAreaCreate(BaseModel):
    name_es: str
    name_en: str
    description: Optional[str] = None
