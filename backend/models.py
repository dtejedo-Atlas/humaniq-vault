from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    RECRUITER = "recruiter"
    RESEARCHER = "researcher"
    # VIEWER = "viewer"  # Fase futura

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
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: Optional[str] = None  # ID del usuario que lo creó
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
    industry: Optional[str] = None  # Almacena el 'key' canónico (ej: "manufacturing")
    functional_area: Optional[str] = None  # Almacena el 'key' canónico (ej: "supply_chain")
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
    
    # Campos normalizados SOLO para búsqueda (sin acentos, lowercase)
    full_name_normalized: Optional[str] = None
    company_normalized: Optional[str] = None
    title_normalized: Optional[str] = None
    
    # Campos de búsqueda híbrida (solo presentes en resultados de búsqueda)
    match_score: Optional[int] = None
    match_breakdown: Optional[Dict[str, Any]] = None
    
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
    key: str  # Identificador canónico, neutral al idioma (ej: "manufacturing")
    name_es: str  # Nombre en español para UI
    name_en: str  # Nombre en inglés
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FunctionalArea(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    key: str  # Identificador canónico, neutral al idioma (ej: "supply_chain")
    name_es: str  # Nombre en español para UI
    name_en: str  # Nombre en inglés
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
    key: str  # Identificador canónico (ej: "manufacturing")
    name_es: str
    name_en: str
    description: Optional[str] = None

class FunctionalAreaCreate(BaseModel):
    key: str  # Identificador canónico (ej: "supply_chain")
    name_es: str
    name_en: str
    description: Optional[str] = None



# ============= JOB / VACANTE MODELS =============

class JobStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    DRAFT = "draft"

class Job(BaseModel):
    """Modelo de Vacante para Job Matching Engine"""
    model_config = ConfigDict(extra="ignore")
    
    id: str
    title: str                                    # "Gerente de Operaciones"
    company: Optional[str] = None                 # Empresa (contexto)
    
    # Taxonomía (misma que candidatos)
    industry: str                                 # key: "manufacturing"
    functional_area: str                          # key: "operations"
    seniority: str                                # "manager", "director", etc.
    
    # Requisitos de experiencia
    min_experience: int = 0                       # Años mínimos
    max_experience: Optional[int] = None          # Años máximos (opcional)
    
    # Skills
    required_skills: List[str] = []               # Skills obligatorios
    preferred_skills: List[str] = []              # Skills deseables
    
    # Descripción estructurada
    responsibilities: Optional[str] = None        # Responsabilidades clave
    requirements: Optional[str] = None            # Requisitos no negociables (texto)
    nice_to_have: Optional[str] = None            # Deseables (texto)
    description: Optional[str] = None             # Descripción completa libre
    role_context: Optional[str] = None            # Contexto del rol
    
    # Ubicación (soft matching - no descarte)
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: str = "México"
    remote_option: bool = False
    
    # Idioma (para Fase B - soft matching)
    language_requirements: Optional[List[str]] = None  # ["spanish:fluent", "english:advanced"]
    
    # Metadata
    status: JobStatus = JobStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str                               # ID del usuario
    
    # Embedding para búsqueda semántica
    embedding: Optional[List[float]] = None

class JobCreate(BaseModel):
    """Schema para crear vacante"""
    title: str
    company: Optional[str] = None
    industry: str
    functional_area: str
    seniority: str
    min_experience: int = 0
    max_experience: Optional[int] = None
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    nice_to_have: Optional[str] = None
    description: Optional[str] = None
    role_context: Optional[str] = None
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: str = "México"
    remote_option: bool = False

class JobUpdate(BaseModel):
    """Schema para actualizar vacante"""
    title: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    functional_area: Optional[str] = None
    seniority: Optional[str] = None
    min_experience: Optional[int] = None
    max_experience: Optional[int] = None
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    responsibilities: Optional[str] = None
    requirements: Optional[str] = None
    nice_to_have: Optional[str] = None
    description: Optional[str] = None
    role_context: Optional[str] = None
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    location_country: Optional[str] = None
    remote_option: Optional[bool] = None
    status: Optional[JobStatus] = None

class CandidateMatchResult(BaseModel):
    """Resultado de matching de un candidato contra una vacante"""
    candidate_id: str
    candidate_name: str
    current_title: Optional[str] = None
    current_company: Optional[str] = None
    
    # Score total
    match_percentage: int                         # 0-100
    
    # Breakdown detallado
    breakdown: Dict[str, Any]
    
    # Análisis cualitativo
    strengths: List[str] = []                     # Fortalezas principales
    risks: List[Dict[str, Any]] = []              # Riesgos detectados
    missing_skills: List[str] = []                # Skills faltantes
    
    # Datos adicionales del candidato para display
    years_experience: Optional[int] = None
    industry: Optional[str] = None
    functional_area: Optional[str] = None
    seniority: Optional[str] = None

class JobMatchResponse(BaseModel):
    """Respuesta del endpoint de matching"""
    job_id: str
    job_title: str
    total_candidates: int
    matched_candidates: int
    threshold_used: int
    results: List[CandidateMatchResult]



# ============= CANDIDATE ASSIGNMENT MODELS =============

class AssignmentStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    TRANSFERRED = "transferred"

class CandidateAssignment(BaseModel):
    """Asignación de candidato a reclutador"""
    model_config = ConfigDict(extra="ignore")
    
    id: str
    candidate_id: str
    candidate_name: str  # Desnormalizado para display rápido
    recruiter_id: str
    recruiter_name: str  # Desnormalizado para display rápido
    assigned_by: str
    assigned_by_name: str
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = None
    status: AssignmentStatus = AssignmentStatus.ACTIVE

class AssignmentCreate(BaseModel):
    candidate_id: str
    recruiter_id: str
    notes: Optional[str] = None


# ============= SMART FOLDER MODELS =============

class FolderType(str, Enum):
    SYSTEM = "system"  # Predefinido, no eliminable
    USER = "user"      # Creado por usuario, editable

class SmartFolderCriteria(BaseModel):
    """Criterios de filtrado para smart folder"""
    industries: List[str] = []           # OR entre valores
    functional_areas: List[str] = []     # OR entre valores
    seniority_levels: List[str] = []     # OR entre valores
    min_experience: Optional[int] = None
    max_experience: Optional[int] = None
    skills: List[str] = []               # AND - debe tener todos

class SmartFolder(BaseModel):
    """Smart Folder para organizar candidatos dinámicamente"""
    model_config = ConfigDict(extra="ignore")
    
    id: str
    name: str                            # "CFO - Consumer Goods"
    description: Optional[str] = None
    folder_type: FolderType = FolderType.USER
    criteria: SmartFolderCriteria
    
    # Ownership
    owner_id: Optional[str] = None       # None para folders del sistema
    owner_name: Optional[str] = None
    is_shared: bool = True               # Visible para todo el equipo
    
    # Stats (calculados dinámicamente)
    candidate_count: int = 0
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SmartFolderCreate(BaseModel):
    name: str
    description: Optional[str] = None
    criteria: SmartFolderCriteria
    is_shared: bool = True

class SmartFolderUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    criteria: Optional[SmartFolderCriteria] = None
    is_shared: Optional[bool] = None


# ============= ACTIVITY LOG MODELS =============

class ActivityAction(str, Enum):
    # Candidatos
    CANDIDATE_UPLOADED = "candidate_uploaded"
    CANDIDATE_VIEWED = "candidate_viewed"
    CANDIDATE_UPDATED = "candidate_updated"
    CANDIDATE_ASSIGNED = "candidate_assigned"
    CANDIDATE_UNASSIGNED = "candidate_unassigned"
    
    # Vacantes
    JOB_CREATED = "job_created"
    JOB_UPDATED = "job_updated"
    JOB_MATCHED = "job_matched"
    JOB_DELETED = "job_deleted"
    
    # Folders
    FOLDER_CREATED = "folder_created"
    FOLDER_UPDATED = "folder_updated"
    FOLDER_DELETED = "folder_deleted"
    
    # Exports
    EXPORT_GENERATED = "export_generated"
    
    # Users
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_LOGIN = "user_login"

class ActivityLog(BaseModel):
    """Log de actividad del sistema"""
    model_config = ConfigDict(extra="ignore")
    
    id: str
    user_id: str
    user_name: str
    action: ActivityAction
    entity_type: str                     # "candidate", "job", "folder", "user"
    entity_id: Optional[str] = None
    entity_name: Optional[str] = None    # Para display sin lookup
    details: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============= EXPORT MODELS =============

class ExportFormat(str, Enum):
    PDF = "pdf"
    DOCX = "docx"

class ExportSourceType(str, Enum):
    JOB = "job"
    FOLDER = "folder"
    CUSTOM = "custom"

class ExportRequest(BaseModel):
    """Request para generar exportación"""
    source_type: ExportSourceType
    source_id: Optional[str] = None      # ID de job o folder
    candidate_ids: List[str] = []        # Si es custom, lista de IDs
    format: ExportFormat = ExportFormat.PDF
    include_breakdown: bool = True
    include_risks: bool = True
    include_contact_info: bool = False   # Solo para admins

class ExportRecord(BaseModel):
    """Registro de exportación generada"""
    model_config = ConfigDict(extra="ignore")
    
    id: str
    user_id: str
    user_name: str
    source_type: ExportSourceType
    source_id: Optional[str] = None
    source_name: str                     # Nombre de la vacante/folder
    format: ExportFormat
    candidate_count: int
    file_url: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============= USER MANAGEMENT MODELS =============

class UserUpdate(BaseModel):
    """Schema para actualizar usuario"""
    name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserWithStats(BaseModel):
    """Usuario con estadísticas"""
    id: str
    email: str
    name: str
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    candidates_assigned: int = 0
    jobs_created: int = 0
