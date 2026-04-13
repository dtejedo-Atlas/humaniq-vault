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
    """Estados del ciclo de vida del candidato en el pipeline de reclutamiento"""
    NEW = "new"                    # CV recién cargado, sin revisar
    REVIEWING = "reviewing"        # Recruiter está evaluando el perfil
    QUALIFIED = "qualified"        # Perfil validado, listo para procesos
    READY_TO_SEND = "ready_to_send"  # Listo para presentar a cliente
    SUBMITTED = "submitted"        # Enviado a cliente
    INTERVIEWED = "interviewed"    # Cliente lo entrevistó
    OFFER = "offer"               # En negociación de oferta
    PLACED = "placed"             # Contratado exitosamente
    REJECTED = "rejected"         # No apto o rechazado
    ON_HOLD = "on_hold"           # Temporalmente inactivo

# Colores para estados (para UI)
STATUS_COLORS = {
    "new": {"bg": "bg-blue-100", "text": "text-blue-800", "label": "Nuevo"},
    "reviewing": {"bg": "bg-yellow-100", "text": "text-yellow-800", "label": "En Revisión"},
    "qualified": {"bg": "bg-green-100", "text": "text-green-800", "label": "Calificado"},
    "ready_to_send": {"bg": "bg-emerald-100", "text": "text-emerald-800", "label": "Listo para Enviar"},
    "submitted": {"bg": "bg-purple-100", "text": "text-purple-800", "label": "Presentado"},
    "interviewed": {"bg": "bg-cyan-100", "text": "text-cyan-800", "label": "Entrevistado"},
    "offer": {"bg": "bg-amber-100", "text": "text-amber-800", "label": "Oferta"},
    "placed": {"bg": "bg-teal-100", "text": "text-teal-800", "label": "Colocado"},
    "rejected": {"bg": "bg-gray-100", "text": "text-gray-800", "label": "Descartado"},
    "on_hold": {"bg": "bg-slate-100", "text": "text-slate-800", "label": "En Pausa"}
}

# Transiciones válidas de estado
VALID_STATUS_TRANSITIONS = {
    "new": ["reviewing", "rejected", "on_hold"],
    "reviewing": ["qualified", "rejected", "on_hold"],
    "qualified": ["ready_to_send", "rejected", "on_hold"],
    "ready_to_send": ["submitted", "qualified", "rejected", "on_hold"],
    "submitted": ["interviewed", "rejected", "on_hold"],
    "interviewed": ["offer", "qualified", "rejected", "on_hold"],
    "offer": ["placed", "rejected", "on_hold"],
    "placed": [],  # Estado final
    "rejected": ["reviewing", "on_hold"],  # Puede reactivarse
    "on_hold": ["reviewing", "qualified", "rejected"]  # Puede reactivarse
}

class StatusChange(BaseModel):
    """Registro de cambio de estado para historial"""
    from_status: str
    to_status: str
    changed_by: str           # user_id
    changed_by_name: str      # nombre del usuario
    changed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: Optional[str] = None

class SeniorityLevel(str, Enum):
    TRAINEE = "trainee"       # Becario / Practicante
    ENTRY = "entry"           # Entrada / Recién egresado
    JUNIOR = "junior"         # Junior / Coordinador
    MID = "mid"               # Mid-level / Especialista
    SENIOR = "senior"         # Senior
    LEAD = "lead"             # Lead / Líder técnico
    MANAGER = "manager"       # Gerente
    DIRECTOR = "director"     # Director
    VP = "vp"                 # VP / Vicepresidente
    C_LEVEL = "c_level"       # C-Level (CEO, CFO, etc.)

# Mapeo de seniority a niveles numéricos para scoring y ordenamiento
SENIORITY_LEVELS = {
    "trainee": {"level": 0, "label": "Becario/Trainee", "years_min": 0, "years_max": 1},
    "entry": {"level": 1, "label": "Entrada", "years_min": 0, "years_max": 2},
    "junior": {"level": 2, "label": "Junior/Coordinador", "years_min": 1, "years_max": 4},
    "mid": {"level": 3, "label": "Mid-Level", "years_min": 3, "years_max": 7},
    "senior": {"level": 4, "label": "Senior", "years_min": 5, "years_max": 12},
    "lead": {"level": 5, "label": "Lead", "years_min": 7, "years_max": 15},
    "manager": {"level": 6, "label": "Gerente", "years_min": 8, "years_max": 20},
    "director": {"level": 7, "label": "Director", "years_min": 10, "years_max": 25},
    "vp": {"level": 8, "label": "VP", "years_min": 12, "years_max": 30},
    "c_level": {"level": 9, "label": "C-Level", "years_min": 15, "years_max": 40}
}

# Keywords para detectar seniority desde título del puesto
SENIORITY_TITLE_KEYWORDS = {
    "trainee": ["intern", "internship", "becario", "becaria", "practicante", "trainee", "pasante", "aprendiz"],
    "entry": ["entry", "graduate", "egresado", "recién egresado", "auxiliar", "asistente jr"],
    "junior": ["junior", "jr", "coordinator", "coordinador", "coordinadora", "analyst", "analista", "associate", "asociado"],
    "mid": ["specialist", "especialista", "consultant", "consultor", "professional", "profesional", "engineer", "ingeniero"],
    "senior": ["senior", "sr", "lead analyst", "expert", "experto", "principal"],
    "lead": ["lead", "líder", "lider", "team lead", "tech lead", "head of"],
    "manager": ["manager", "gerente", "jefe", "jefa", "supervisor", "superintendent", "superintendente"],
    "director": ["director", "directora", "head", "regional"],
    "vp": ["vp", "vice president", "vicepresidente", "vice presidente", "svp", "evp"],
    "c_level": ["ceo", "cfo", "coo", "cto", "cio", "cmo", "chro", "chief", "presidente", "president", "managing director", "director general", "country manager", "socio", "partner", "fundador", "founder", "owner", "dueño", "general manager"]
}

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
    status_history: List[StatusChange] = []  # Historial de cambios de estado
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
    
    # Tracking de actividad
    last_activity: Optional[datetime] = None
    last_activity_type: Optional[str] = None  # status_change, note_added, exported, etc.
    
    # Soft delete
    is_deleted: Optional[bool] = None
    deleted_at: Optional[str] = None
    deleted_by: Optional[str] = None
    deleted_by_name: Optional[str] = None
    
    # Restricción (lista negra)
    is_restricted: Optional[bool] = None
    restriction_info: Optional[Dict[str, Any]] = None
    restriction_history: List[Dict[str, Any]] = []
    
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

class StatusChangeRequest(BaseModel):
    """Request para cambiar estado de candidato"""
    new_status: CandidateStatus
    notes: Optional[str] = None

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

class WorkScheme(str, Enum):
    """Esquema de trabajo"""
    ON_SITE = "on_site"
    HYBRID = "hybrid"
    REMOTE = "remote"

class Job(BaseModel):
    """Modelo de Vacante para Job Matching Engine - v2 Rediseñado"""
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
    
    # ===== NUEVOS CAMPOS v2 =====
    # Objetivo y contexto
    job_objective: Optional[str] = None           # Objetivo principal del puesto
    role_context: Optional[str] = None            # Contexto de empresa/industria
    
    # Responsabilidades y requisitos
    responsibilities: Optional[str] = None        # Responsabilidades principales
    required_experience: Optional[str] = None     # Experiencia requerida (descriptiva)
    non_negotiables: Optional[str] = None         # Requisitos no negociables
    
    # Ubicación estructurada
    location_country: str = "México"
    location_state: Optional[str] = None
    location_city: Optional[str] = None
    
    # Compensación
    salary_min: Optional[int] = None              # Salario mínimo (MXN)
    salary_max: Optional[int] = None              # Salario máximo (MXN)
    salary_currency: str = "MXN"                  # Moneda
    
    # Esquema laboral
    work_scheme: WorkScheme = WorkScheme.ON_SITE  # presencial/híbrido/remoto
    schedule: Optional[str] = None                # Jornada/horario
    
    # ===== CAMPOS DEPRECADOS (mantener por compatibilidad) =====
    required_skills: List[str] = []               # DEPRECADO - mantener vacío
    preferred_skills: List[str] = []              # DEPRECADO - mantener vacío
    requirements: Optional[str] = None            # DEPRECADO - usar non_negotiables
    nice_to_have: Optional[str] = None            # DEPRECADO
    description: Optional[str] = None             # DEPRECADO - usar job_objective + responsibilities
    remote_option: bool = False                   # DEPRECADO - usar work_scheme
    
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
    """Schema para crear vacante - v2 Rediseñado"""
    # Paso 1: Información básica
    title: str
    company: Optional[str] = None
    industry: str
    functional_area: str
    seniority: str
    min_experience: int = 0
    max_experience: Optional[int] = None
    
    # Paso 2: Contexto y responsabilidades
    job_objective: Optional[str] = None
    role_context: Optional[str] = None
    responsibilities: Optional[str] = None
    
    # Paso 3: Requisitos, ubicación y salario
    required_experience: Optional[str] = None
    non_negotiables: Optional[str] = None
    location_country: str = "México"
    location_state: Optional[str] = None
    location_city: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "MXN"
    work_scheme: WorkScheme = WorkScheme.ON_SITE
    schedule: Optional[str] = None
    
    # Campos deprecados (mantener por compatibilidad)
    required_skills: List[str] = []
    preferred_skills: List[str] = []
    responsibilities_old: Optional[str] = None    # alias del campo antiguo
    requirements: Optional[str] = None
    nice_to_have: Optional[str] = None
    description: Optional[str] = None
    remote_option: bool = False

class JobUpdate(BaseModel):
    """Schema para actualizar vacante - v2"""
    title: Optional[str] = None
    company: Optional[str] = None
    industry: Optional[str] = None
    functional_area: Optional[str] = None
    seniority: Optional[str] = None
    min_experience: Optional[int] = None
    max_experience: Optional[int] = None
    
    # Nuevos campos v2
    job_objective: Optional[str] = None
    role_context: Optional[str] = None
    responsibilities: Optional[str] = None
    required_experience: Optional[str] = None
    non_negotiables: Optional[str] = None
    location_country: Optional[str] = None
    location_state: Optional[str] = None
    location_city: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = None
    work_scheme: Optional[WorkScheme] = None
    schedule: Optional[str] = None
    
    # Deprecados
    required_skills: Optional[List[str]] = None
    preferred_skills: Optional[List[str]] = None
    requirements: Optional[str] = None
    nice_to_have: Optional[str] = None
    description: Optional[str] = None
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
    include_risks: bool = True
    include_contact_info: bool = False   # Solo para admins
    # Cover page info (opcional)
    client_name: Optional[str] = None    # Nombre del cliente/empresa

class ExportRecord(BaseModel):
    """Registro de exportación generada (para trazabilidad)"""
    model_config = ConfigDict(extra="ignore")
    
    id: str
    user_id: str
    user_name: str
    source_type: ExportSourceType
    source_id: Optional[str] = None
    source_name: str                     # Nombre de la vacante/folder
    format: ExportFormat
    candidate_count: int
    candidate_ids: List[str] = []        # IDs de candidatos incluidos
    included_contact_info: bool = False  # Si se incluyó contacto
    file_url: str
    file_path: Optional[str] = None      # Path en storage
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


# ============= SMART FOLDERS MODELS =============

class FolderType(str, Enum):
    """Tipo de folder"""
    SYSTEM = "system"       # Predefinido, no editable
    USER = "user"           # Creado por usuario

class FolderCategory(str, Enum):
    """Categoría de folder"""
    VERTICAL = "vertical"   # Por expertise (CFO, Operaciones, etc.)
    PROCESS = "process"     # Por estado de proceso (Listos para enviar, etc.)
    CUSTOM = "custom"       # Personalizado por usuario

class SeniorityFilter(BaseModel):
    """Filtro de seniority para folders"""
    mode: str = "range"  # "range" o "exact"
    min_level: Optional[str] = None
    max_level: Optional[str] = None
    exact_levels: List[str] = []

class FolderCriteria(BaseModel):
    """Criterios dinámicos para Smart Folder"""
    model_config = ConfigDict(extra="ignore")
    
    # Expertise
    functional_area: List[str] = []
    industry: List[str] = []
    seniority: Optional[SeniorityFilter] = None
    
    # Estado de proceso
    candidate_status: List[str] = []  # active, in_process, interviewed, ready_to_send
    last_activity_days: Optional[int] = None
    min_match_score: Optional[int] = None
    created_last_days: Optional[int] = None
    
    # Asignación
    assignment_filter: str = "all"  # "mine", "unassigned", "all"

class SmartFolder(BaseModel):
    """Smart Folder - Vista dinámica de candidatos"""
    model_config = ConfigDict(extra="ignore")
    
    id: str
    name: str
    description: Optional[str] = None
    icon: str = "folder"
    color: str = "slate"
    
    # Tipo y categoría
    folder_type: FolderType
    folder_category: FolderCategory
    
    # Criterios dinámicos
    criteria: FolderCriteria
    
    # Ownership
    created_by: Optional[str] = None  # user_id, null para sistema
    
    # Orden y visibilidad
    sort_order: int = 0
    is_pinned: bool = False
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SmartFolderCreate(BaseModel):
    """Request para crear Smart Folder"""
    name: str
    description: Optional[str] = None
    icon: str = "folder"
    color: str = "slate"
    folder_category: FolderCategory = FolderCategory.CUSTOM
    criteria: FolderCriteria
    is_pinned: bool = False

class SmartFolderUpdate(BaseModel):
    """Request para actualizar Smart Folder"""
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    criteria: Optional[FolderCriteria] = None
    is_pinned: Optional[bool] = None
    sort_order: Optional[int] = None

class FolderAnalytics(BaseModel):
    """Métricas de uso de un folder"""
    folder_id: str
    total_views: int = 0
    views_last_30_days: int = 0
    total_exports: int = 0
    candidates_selected: int = 0
    last_accessed: Optional[datetime] = None

class SmartFolderWithCount(BaseModel):
    """Smart Folder con conteo de candidatos"""
    model_config = ConfigDict(extra="ignore")
    
    id: str
    name: str
    description: Optional[str] = None
    icon: str
    color: str
    folder_type: FolderType
    folder_category: FolderCategory
    criteria: FolderCriteria
    candidate_count: int = 0
    sort_order: int = 0
    is_pinned: bool = False
    analytics: Optional[FolderAnalytics] = None
