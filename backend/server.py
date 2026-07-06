from fastapi import FastAPI, APIRouter, HTTPException, status, Depends, UploadFile, File, Form, Header, Query, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import json
import logging
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import shutil

from models import (
    User, UserCreate, UserLogin, Token, UserRole, UserUpdate,
    Candidate, CandidateCreate, CandidateUpdate, CandidateStatus, SeniorityLevel,
    ResumeUpload, ParseStatus, ResumeFile, PreviousCompany, RecruiterNote, AIClassification,
    Industry, FunctionalArea, JobProfile, CandidateMatch, SearchQuery, ActivityLog,
    DuplicateSuggestionModel, SavedSearch, IndustryCreate, FunctionalAreaCreate,
    Job, JobCreate, JobUpdate, JobStatus as JobStatusEnum, CandidateMatchResult, JobMatchResponse,
    JobScorecard,
    AssignmentCreate, ExportFormat, ExportSourceType, ExportRequest,
    SmartFolder, SmartFolderCreate, SmartFolderUpdate, FolderType, FolderCategory,
    StatusChangeRequest, StatusChange, VALID_STATUS_TRANSITIONS, STATUS_COLORS,
    SENIORITY_LEVELS, SENIORITY_TITLE_KEYWORDS
)
from validation_models import ValidationRecord, ValidationSummary
from auth import verify_password, get_password_hash, create_access_token, verify_token
from atlas_service import atlas_service, classify_seniority
from document_parser import DocumentParser
from storage_service import storage_service, init_storage
from duplicate_detector import DuplicateDetector, DuplicateSuggestion
from duplicate_detector_v2 import DuplicateDetectorV2, CandidateMerger
from embedding_service import embedding_service
from hybrid_search_service import HybridSearchService
from text_utils import normalize_for_search
from background_processor import background_processor, JobStatus
from job_matching_service import JobMatchingService
from user_service import UserService
from assignment_service import AssignmentService
from export_service import ExportService
from smart_folder_service import SmartFolderService
from cv_version_service import CVVersionService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection - Supports both local (MONGO_URL) and Atlas (ATLAS_URI)
# Priority: ATLAS_URI > MONGO_URL (allows seamless migration)
mongo_url = os.environ.get('ATLAS_URI') or os.environ.get('MONGO_URL')
if not mongo_url:
    raise ValueError("Database connection not configured. Set ATLAS_URI or MONGO_URL environment variable.")

client = AsyncIOMotorClient(mongo_url)

# When using Atlas, ATLAS_DB_NAME takes priority (production may override DB_NAME)
if os.environ.get('ATLAS_URI') and os.environ.get('ATLAS_DB_NAME'):
    db_name = os.environ['ATLAS_DB_NAME']
else:
    db_name = os.environ['DB_NAME']
db = client[db_name]

# Log which database is being used (without exposing credentials)
db_type = "MongoDB Atlas" if "mongodb+srv" in mongo_url else "Local MongoDB"
print(f"[STARTUP] Connected to {db_type} - Database: {db_name}")

# Initialize services
duplicate_detector = DuplicateDetector(db)
duplicate_detector_v2 = DuplicateDetectorV2(db)
candidate_merger = CandidateMerger(db)
cv_version_service = CVVersionService(db)
hybrid_search_service = HybridSearchService(db, embedding_service)
job_matching_service = JobMatchingService(db, embedding_service)
user_service = UserService(db)
assignment_service = AssignmentService(db)
export_service = ExportService(db, storage_service)
smart_folder_service = SmartFolderService(db)

# Create uploads directory (fallback for migration)
UPLOAD_DIR = ROOT_DIR / "uploads" / "resumes"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Security
security = HTTPBearer()

# Create the main app
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============= HELPER FUNCTIONS FOR RESILIENT DATA VALIDATION =============

def safe_int(value, default=None) -> Optional[int]:
    """
    Convierte un valor a entero de forma segura.
    Si falla, retorna el default en vez de lanzar excepción.
    """
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        # Intentar extraer número de strings como "10 años" o "10+"
        try:
            # Limpiar string
            cleaned = value.strip().replace('+', '').split()[0]
            return int(float(cleaned))
        except (ValueError, IndexError):
            return default
    return default


def safe_string(value, default=None) -> Optional[str]:
    """
    Convierte un valor a string de forma segura.
    Si es None o tipo incorrecto, retorna el default.
    """
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() if value.strip() else default
    try:
        return str(value)
    except Exception:
        return default


def safe_list(value, default=None) -> list:
    """
    Asegura que el valor sea una lista.
    Si es None o tipo incorrecto, retorna lista vacía o default.
    """
    if default is None:
        default = []
    if value is None:
        return default
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return default


def clean_previous_company(pc_data: dict) -> Optional[dict]:
    """
    Limpia y valida una entrada de previous_companies.
    Retorna None si los datos son irrecuperables.
    """
    if not isinstance(pc_data, dict):
        return None
    
    # Campos mínimos requeridos
    company_name = safe_string(pc_data.get('company_name') or pc_data.get('company'))
    title = safe_string(pc_data.get('title') or pc_data.get('position'))
    
    # Si no hay ni empresa ni título, es irrecuperable
    if not company_name and not title:
        return None
    
    # Validar company_caliber contra los 5 niveles canónicos
    caliber = pc_data.get('company_caliber')
    if caliber not in ('multinacional_global', 'corporativo_nacional', 'mediana', 'pyme', 'startup'):
        caliber = None
    
    return {
        'company_name': company_name or 'Empresa no especificada',
        'title': title or 'Puesto no especificado',
        'start_date': safe_string(pc_data.get('start_date')),
        'end_date': safe_string(pc_data.get('end_date')),
        'duration': safe_string(pc_data.get('duration')),
        'description': safe_string(pc_data.get('description')),
        'industry': safe_string(pc_data.get('industry')),
        'location': safe_string(pc_data.get('location')),
        'company_caliber': caliber,
    }


def clean_previous_companies(companies_data: list) -> list:
    """
    Limpia y valida la lista de previous_companies.
    Retorna lista de diccionarios válidos, saltando los inválidos.
    """
    if not companies_data:
        return []
    if not isinstance(companies_data, list):
        return []
    
    cleaned = []
    for pc in companies_data:
        clean_pc = clean_previous_company(pc)
        if clean_pc:
            cleaned.append(clean_pc)
    
    return cleaned


# ============= STARTUP/SHUTDOWN EVENTS =============

@app.on_event("startup")
async def startup():
    """Initialize services on startup"""
    try:
        init_storage()
        logger.info("✓ Object storage initialized")
    except Exception as e:
        logger.error(f"✗ Storage initialization failed: {e}")
    
    # Inicializar Smart Folders del sistema
    try:
        await smart_folder_service.initialize_system_folders()
        logger.info("✓ Smart Folders initialized")
    except Exception as e:
        logger.error(f"✗ Smart Folders initialization failed: {e}")


# ============= DEPENDENCY FUNCTIONS =============

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user"""
    token = credentials.credentials
    payload = verify_token(token)
    user_email = payload.get("sub")
    
    if not user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido"
        )
    
    user_doc = await db.users.find_one({"email": user_email}, {"_id": 0})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado"
        )
    
    if isinstance(user_doc.get('created_at'), str):
        user_doc['created_at'] = datetime.fromisoformat(user_doc['created_at'])
    if user_doc.get('last_login') and isinstance(user_doc['last_login'], str):
        user_doc['last_login'] = datetime.fromisoformat(user_doc['last_login'])
    
    return User(**user_doc)


def require_role(required_roles: List[UserRole]):
    """Dependency factory to check user role"""
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para esta acción"
            )
        return current_user
    return role_checker


async def verify_candidate_edit_permission(candidate_id: str, current_user: User) -> None:
    """
    Verifica si el usuario puede editar un candidato.
    - Admin/Super Admin: puede editar cualquiera
    - Recruiter: solo puede editar si está asignado a él
    
    Raises HTTPException 403 si no tiene permiso.
    """
    # Admin y Super Admin tienen acceso completo
    if current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        return
    
    # Para Recruiters, verificar asignación activa
    assignments = await assignment_service.get_candidate_assignments(candidate_id)
    
    for assignment in assignments:
        if (assignment.get("recruiter_id") == current_user.id and 
            assignment.get("status") == "active"):
            return
    
    # Si llegamos aquí, el recruiter no tiene permiso
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="No tienes permiso para editar este candidato. Solo puedes editar candidatos asignados a ti."
    )


# ============= AUTHENTICATION ROUTES =============

@api_router.post("/auth/register", response_model=User)
async def register(user_data: UserCreate):
    """Register a new user"""
    # Check if user exists
    existing = await db.users.find_one({"email": user_data.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )
    
    # Create user
    user_id = str(uuid.uuid4())
    hashed_password = get_password_hash(user_data.password)
    
    user = User(
        id=user_id,
        email=user_data.email,
        name=user_data.name,
        role=user_data.role
    )
    
    user_doc = user.model_dump()
    user_doc['password_hash'] = hashed_password
    user_doc['created_at'] = user_doc['created_at'].isoformat()
    
    await db.users.insert_one(user_doc)
    
    return user


@api_router.post("/auth/login", response_model=Token)
async def login(credentials: UserLogin):
    """Login user"""
    user_doc = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    
    if not user_doc or not verify_password(credentials.password, user_doc['password_hash']):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )
    
    # Update last login
    await db.users.update_one(
        {"email": credentials.email},
        {"$set": {"last_login": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Create access token
    access_token = create_access_token({"sub": credentials.email})
    
    # Parse dates
    if isinstance(user_doc.get('created_at'), str):
        user_doc['created_at'] = datetime.fromisoformat(user_doc['created_at'])
    if user_doc.get('last_login') and isinstance(user_doc['last_login'], str):
        user_doc['last_login'] = datetime.fromisoformat(user_doc['last_login'])
    
    user = User(**user_doc)
    
    return Token(access_token=access_token, user=user)


@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return current_user


# ============= CANDIDATE ROUTES =============

@api_router.get("/candidates", response_model=List[Candidate])
async def get_candidates(
    skip: int = 0,
    limit: int = 50,
    status: Optional[CandidateStatus] = None,
    industry: Optional[str] = None,
    functional_area: Optional[str] = None,
    seniority: Optional[SeniorityLevel] = None,
    search: Optional[str] = None,
    use_semantic: bool = True,
    sort_by: str = Query(default="created_at", description="Campo para ordenar: created_at, industry, full_name, seniority"),
    sort_order: str = Query(default="desc", description="Orden: asc o desc"),
    current_user: User = Depends(get_current_user)
):
    """
    Get candidates list with filters.
    Si hay parámetro 'search', usa el motor de búsqueda híbrida calibrada.
    """
    # Construir filtros estructurados
    filters = {}
    if status:
        filters['status'] = status.value if hasattr(status, 'value') else str(status)
    if industry and industry.strip():
        filters['industry'] = industry.strip()
    if functional_area and functional_area.strip():
        filters['functional_area'] = functional_area.strip()
    if seniority:
        filters['seniority'] = seniority.value if hasattr(seniority, 'value') else str(seniority)
    
    # Si hay búsqueda de texto, usar motor híbrido calibrado
    if search and search.strip():
        results = await hybrid_search_service.search(
            query=search.strip(),
            filters=filters,
            use_semantic=use_semantic,
            limit=limit
        )
        
        # Aplicar skip para paginación
        results = results[skip:skip+limit] if skip > 0 else results[:limit]
        
        # Parse dates para compatibilidad
        for candidate in results:
            if isinstance(candidate.get('created_at'), str):
                candidate['created_at'] = datetime.fromisoformat(candidate['created_at'])
            if isinstance(candidate.get('updated_at'), str):
                candidate['updated_at'] = datetime.fromisoformat(candidate['updated_at'])
        
        return results
    
    # Sin búsqueda de texto: solo filtros estructurados
    query = {"is_deleted": {"$ne": True}}  # Excluir eliminados
    if status:
        query['status'] = status.value if hasattr(status, 'value') else str(status)
    if industry and industry.strip():
        query['industry'] = industry.strip()
    if functional_area and functional_area.strip():
        query['functional_area'] = functional_area.strip()
    if seniority:
        query['seniority'] = seniority.value if hasattr(seniority, 'value') else str(seniority)
    
    # Determinar orden
    sort_direction = 1 if sort_order == 'asc' else -1
    valid_sort_fields = ['created_at', 'industry', 'full_name', 'seniority', 'updated_at', 'functional_area']
    sort_field = sort_by if sort_by in valid_sort_fields else 'created_at'
    
    candidates = await db.candidates.find(query, {"_id": 0}).sort(sort_field, sort_direction).skip(skip).limit(limit).to_list(limit)
    
    # Parse dates
    for candidate in candidates:
        if isinstance(candidate.get('created_at'), str):
            candidate['created_at'] = datetime.fromisoformat(candidate['created_at'])
        if isinstance(candidate.get('updated_at'), str):
            candidate['updated_at'] = datetime.fromisoformat(candidate['updated_at'])
        
        # Parse nested dates
        for note in candidate.get('notes', []):
            if isinstance(note.get('created_at'), str):
                note['created_at'] = datetime.fromisoformat(note['created_at'])
        
        for resume in candidate.get('resume_files', []):
            if isinstance(resume.get('upload_date'), str):
                resume['upload_date'] = datetime.fromisoformat(resume['upload_date'])
        
        if candidate.get('ai_classification') and isinstance(candidate['ai_classification'].get('classified_at'), str):
            candidate['ai_classification']['classified_at'] = datetime.fromisoformat(candidate['ai_classification']['classified_at'])
    
    return candidates


@api_router.post("/candidates", response_model=Candidate)
async def create_candidate(
    candidate_data: CandidateCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new candidate"""
    candidate_id = str(uuid.uuid4())
    
    candidate = Candidate(
        id=candidate_id,
        **candidate_data.model_dump(),
        created_by=current_user.id
    )
    
    # Generar campos normalizados para búsqueda sin acentos
    candidate.full_name_normalized = normalize_for_search(candidate.full_name)
    
    candidate_doc = candidate.model_dump()
    candidate_doc['created_at'] = candidate_doc['created_at'].isoformat()
    candidate_doc['updated_at'] = candidate_doc['updated_at'].isoformat()
    
    await db.candidates.insert_one(candidate_doc)
    
    await log_activity(current_user, "candidate_created", "candidate", candidate_id, candidate.full_name)
    
    return candidate


# ============= BATCH QUEUE STATUS ROUTES (MUST BE BEFORE {candidate_id}) =============

@api_router.get("/candidates/queue-stats")
async def get_queue_stats(
    current_user: User = Depends(get_current_user)
):
    """
    Obtener estadísticas de la cola de procesamiento.
    """
    return background_processor.get_queue_stats()


@api_router.get("/candidates/batch/{batch_id}")
async def get_batch_status(
    batch_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Obtener estado de un lote de uploads.
    """
    batch_status = background_processor.get_batch_status(batch_id)
    
    if not batch_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lote no encontrado"
        )
    
    return batch_status


@api_router.get("/candidates/job/{job_id}")
async def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Obtener estado detallado de un job individual.
    """
    job = background_processor.get_job(job_id)
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job no encontrado"
        )
    
    return job.to_dict()


@api_router.post("/candidates/job/{job_id}/retry")
async def retry_job(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Reintentar un job fallido.
    """
    success = await background_processor.retry_job(job_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede reintentar este job"
        )
    
    return {"message": "Job re-encolado para reintento", "job_id": job_id}


@api_router.get("/candidates/{candidate_id}", response_model=Candidate)
async def get_candidate(
    candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get candidate by ID"""
    candidate_doc = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    
    if not candidate_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato no encontrado"
        )
    
    # Parse dates
    if isinstance(candidate_doc.get('created_at'), str):
        candidate_doc['created_at'] = datetime.fromisoformat(candidate_doc['created_at'])
    if isinstance(candidate_doc.get('updated_at'), str):
        candidate_doc['updated_at'] = datetime.fromisoformat(candidate_doc['updated_at'])
    
    for note in candidate_doc.get('notes', []):
        if isinstance(note.get('created_at'), str):
            note['created_at'] = datetime.fromisoformat(note['created_at'])
    
    for resume in candidate_doc.get('resume_files', []):
        if isinstance(resume.get('upload_date'), str):
            resume['upload_date'] = datetime.fromisoformat(resume['upload_date'])
    
    if candidate_doc.get('ai_classification') and isinstance(candidate_doc['ai_classification'].get('classified_at'), str):
        candidate_doc['ai_classification']['classified_at'] = datetime.fromisoformat(candidate_doc['ai_classification']['classified_at'])
    
    return Candidate(**candidate_doc)


@api_router.put("/candidates/{candidate_id}", response_model=Candidate)
async def update_candidate(
    candidate_id: str,
    update_data: CandidateUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update candidate"""
    candidate_doc = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    
    if not candidate_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato no encontrado"
        )
    
    # Verificar permisos de edición
    await verify_candidate_edit_permission(candidate_id, current_user)
    
    # Update fields
    update_dict = {k: v for k, v in update_data.model_dump(exclude_unset=True).items() if v is not None}
    update_dict['updated_at'] = datetime.now(timezone.utc).isoformat()
    
    await db.candidates.update_one(
        {"id": candidate_id},
        {"$set": update_dict}
    )
    
    # Get updated candidate
    updated_doc = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    
    if isinstance(updated_doc.get('created_at'), str):
        updated_doc['created_at'] = datetime.fromisoformat(updated_doc['created_at'])
    if isinstance(updated_doc.get('updated_at'), str):
        updated_doc['updated_at'] = datetime.fromisoformat(updated_doc['updated_at'])
    
    return Candidate(**updated_doc)


@api_router.post("/candidates/{candidate_id}/notes")
async def add_candidate_note(
    candidate_id: str,
    note_text: str = Form(...),
    current_user: User = Depends(get_current_user)
):
    """Add note to candidate — cualquier usuario autenticado puede comentar"""
    candidate_doc = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    
    if not candidate_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato no encontrado"
        )
    
    note = RecruiterNote(
        note=note_text,
        created_by=current_user.name
    )
    
    note_dict = note.model_dump()
    note_dict['created_at'] = note_dict['created_at'].isoformat()
    
    await db.candidates.update_one(
        {"id": candidate_id},
        {
            "$push": {"notes": note_dict},
            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
        }
    )
    
    await log_activity(current_user, "note_added", "candidate", candidate_id, candidate_doc.get("full_name"))
    
    return {"message": "Nota agregada exitosamente"}


@api_router.delete("/candidates/{candidate_id}")
async def delete_candidate(
    candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Soft delete de candidato.
    El candidato se marca como eliminado pero permanece en BD para trazabilidad.
    Admin y Recruiters pueden eliminar candidatos individuales.
    """
    # Verificar que existe
    candidate = await db.candidates.find_one({"id": candidate_id}, {"_id": 0, "is_deleted": 1, "full_name": 1})
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato no encontrado")
    
    if candidate.get("is_deleted"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El candidato ya está eliminado")
    
    # Realizar soft delete
    now = datetime.now(timezone.utc).isoformat()
    await db.candidates.update_one(
        {"id": candidate_id},
        {"$set": {
            "is_deleted": True,
            "deleted_at": now,
            "deleted_by": current_user.id,
            "deleted_by_name": current_user.name,
            "updated_at": now
        }}
    )
    
    logger.info(f"Candidate {candidate_id} soft deleted by {current_user.email}")
    
    return {
        "message": "Candidato eliminado exitosamente",
        "candidate_id": candidate_id,
        "deleted_by": current_user.name,
        "deleted_at": now
    }


@api_router.post("/candidates/{candidate_id}/restore")
async def restore_candidate(
    candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Restaurar candidato eliminado (solo Admin).
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo Admin puede restaurar candidatos")
    
    candidate = await db.candidates.find_one({"id": candidate_id}, {"_id": 0, "is_deleted": 1})
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato no encontrado")
    
    if not candidate.get("is_deleted"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El candidato no está eliminado")
    
    now = datetime.now(timezone.utc).isoformat()
    await db.candidates.update_one(
        {"id": candidate_id},
        {
            "$set": {"updated_at": now},
            "$unset": {"is_deleted": "", "deleted_at": "", "deleted_by": "", "deleted_by_name": ""}
        }
    )
    
    logger.info(f"Candidate {candidate_id} restored by {current_user.email}")
    
    return {"message": "Candidato restaurado exitosamente", "candidate_id": candidate_id}


# ============= CANDIDATE RESTRICTION (LISTA NEGRA) =============

from pydantic import BaseModel as PydanticBaseModel

class RestrictionRequest(PydanticBaseModel):
    reason: str = ""
    category: str  # ethical_issue, bad_reference, legal_issue, conflict_of_interest, performance_issue, other
    notes: Optional[str] = None

RESTRICTION_CATEGORIES = {
    "ethical_issue": "Problema ético",
    "bad_reference": "Mala referencia",
    "legal_issue": "Problema legal",
    "conflict_of_interest": "Conflicto de interés",
    "performance_issue": "Problema de desempeño",
    "placed_by_humaniq": "Colocado por Humaniq",
    "other": "Otro"
}

JOB_ASSIGNMENT_STAGES = {"new", "interviewed", "placed", "discarded"}


def candidate_is_placed(cand: dict) -> bool:
    """Colocado = restricción placed_by_humaniq activa O algún job_assignment en stage placed"""
    if cand.get("is_restricted") and (cand.get("restriction_info") or {}).get("category") == "placed_by_humaniq":
        return True
    return any(a.get("stage") == "placed" for a in (cand.get("job_assignments") or []))


async def log_activity(user, action: str, entity_type: str, entity_id: str = None, entity_name: str = None, details: dict = None):
    """Registro aditivo de eventos para el feed de actividad"""
    try:
        await db.activity_logs.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": getattr(user, 'id', None),
            "user_name": getattr(user, 'name', None) or getattr(user, 'email', 'Sistema'),
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"log_activity falló: {e}")


async def enrich_results_with_flags(results: list):
    """Agrega is_placed y notes_count a resultados de matching (solo lectura)"""
    ids = [r.get("candidate_id") for r in results if r.get("candidate_id")]
    if not ids:
        return
    docs = await db.candidates.find(
        {"id": {"$in": ids}},
        {"_id": 0, "id": 1, "is_restricted": 1, "restriction_info": 1, "job_assignments": 1, "notes": 1}
    ).to_list(len(ids))
    flags = {d["id"]: d for d in docs}
    for r in results:
        fd = flags.get(r.get("candidate_id"), {})
        r["is_placed"] = candidate_is_placed(fd)
        r["notes_count"] = len(fd.get("notes") or [])

@api_router.post("/candidates/{candidate_id}/restrict")
async def mark_candidate_restricted(
    candidate_id: str,
    request: RestrictionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Marcar candidato como restringido/no elegible.
    No bloquea automáticamente, solo registra para revisión.
    Queda trazado: quién, cuándo, motivo, categoría.
    """
    # Verificar que existe
    candidate = await db.candidates.find_one({"id": candidate_id}, {"_id": 0, "full_name": 1, "is_restricted": 1})
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato no encontrado")
    
    # Verificar permisos de edición
    await verify_candidate_edit_permission(candidate_id, current_user)
    
    if request.category not in RESTRICTION_CATEGORIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Categoría inválida")
    
    # Crear registro de restricción
    now = datetime.now(timezone.utc).isoformat()
    restriction_entry = {
        "category": request.category,
        "category_label": RESTRICTION_CATEGORIES[request.category],
        "reason": request.reason,
        "notes": request.notes,
        "marked_by": current_user.id,
        "marked_by_name": current_user.name,
        "marked_at": now
    }
    
    await db.candidates.update_one(
        {"id": candidate_id},
        {
            "$set": {
                "is_restricted": True,
                "restriction_info": restriction_entry,
                "updated_at": now
            },
            "$push": {
                "restriction_history": restriction_entry
            }
        }
    )
    
    logger.warning(f"Candidate {candidate_id} marked as RESTRICTED by {current_user.email} - Category: {request.category}")
    
    return {
        "message": "Candidato marcado como restringido",
        "candidate_id": candidate_id,
        "category": RESTRICTION_CATEGORIES[request.category],
        "marked_by": current_user.name,
        "marked_at": now
    }


@api_router.post("/candidates/{candidate_id}/unrestrict")
async def remove_candidate_restriction(
    candidate_id: str,
    notes: str = Form(None),
    current_user: User = Depends(get_current_user)
):
    """
    Quitar restricción de candidato (solo Admin).
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo Admin puede quitar restricciones")
    
    candidate = await db.candidates.find_one({"id": candidate_id}, {"_id": 0, "is_restricted": 1})
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato no encontrado")
    
    if not candidate.get("is_restricted"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El candidato no está restringido")
    
    now = datetime.now(timezone.utc).isoformat()
    unrestriction_entry = {
        "action": "unrestricted",
        "unrestricted_by": current_user.id,
        "unrestricted_by_name": current_user.name,
        "unrestricted_at": now,
        "notes": notes
    }
    
    await db.candidates.update_one(
        {"id": candidate_id},
        {
            "$set": {
                "is_restricted": False,
                "updated_at": now
            },
            "$unset": {"restriction_info": ""},
            "$push": {"restriction_history": unrestriction_entry}
        }
    )
    
    logger.info(f"Candidate {candidate_id} UNRESTRICTED by {current_user.email}")
    
    return {"message": "Restricción removida", "candidate_id": candidate_id}


# ============= RESUME UPLOAD & PARSING ROUTES =============

from error_handling import (
    ProcessingResult, ProcessingStage, ErrorType, 
    detect_error_type, BatchProcessingResult
)
import time

@api_router.post("/candidates/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    candidate_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """
    Upload resume and optionally create/link candidate with duplicate detection.
    Returns detailed error information for each processing stage.
    """
    start_time = time.time()
    
    # Inicializar resultado de procesamiento
    result = ProcessingResult(
        file_name=file.filename,
        status="processing",
        stage_reached=ProcessingStage.UPLOAD
    )
    
    warnings = []
    
    # ===== ETAPA 1: VALIDACIÓN DE ARCHIVO =====
    file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
    
    # Solo PDF y DOCX soportados
    if file_ext not in ['pdf', 'docx']:
        error_msg = "Formato no soportado. Solo se permiten archivos PDF y DOCX."
        if file_ext == 'doc':
            error_msg = "Formato DOC (Word 97-2003) no soportado. Por favor convierte a PDF o DOCX."
        
        result.status = "failed"
        result.add_error(
            ErrorType.UNSUPPORTED_FORMAT,
            ProcessingStage.UPLOAD,
            error_msg,
            recoverable=False
        )
        result.processing_time_ms = int((time.time() - start_time) * 1000)
        return result.to_response()
    
    # Leer datos del archivo
    try:
        file_data = await file.read()
        
        if len(file_data) == 0:
            result.status = "failed"
            result.add_error(
                ErrorType.FILE_EMPTY,
                ProcessingStage.UPLOAD,
                "El archivo tiene 0 bytes",
                recoverable=False
            )
            result.processing_time_ms = int((time.time() - start_time) * 1000)
            return result.to_response()
        
        # Verificar tamaño máximo (10MB)
        if len(file_data) > 10 * 1024 * 1024:
            result.status = "failed"
            result.add_error(
                ErrorType.FILE_TOO_LARGE,
                ProcessingStage.UPLOAD,
                f"Tamaño: {len(file_data) / 1024 / 1024:.1f}MB. Máximo: 10MB",
                recoverable=False
            )
            result.processing_time_ms = int((time.time() - start_time) * 1000)
            return result.to_response()
            
    except Exception as e:
        result.status = "failed"
        result.add_error(
            ErrorType.FILE_CORRUPTED,
            ProcessingStage.UPLOAD,
            str(e),
            recoverable=False
        )
        result.processing_time_ms = int((time.time() - start_time) * 1000)
        return result.to_response()
    
    result.stage_reached = ProcessingStage.TEXT_EXTRACTION
    
    # ===== ETAPA 2: EXTRACCIÓN DE TEXTO =====
    extracted_text = ""
    try:
        extracted_text = DocumentParser.extract_text_from_bytes(file_data, file.content_type)
        
        if not extracted_text or len(extracted_text.strip()) < 50:
            result.add_error(
                ErrorType.PDF_SCANNED_NO_OCR,
                ProcessingStage.TEXT_EXTRACTION,
                f"Texto extraído: {len(extracted_text)} caracteres. Mínimo esperado: 50",
                recoverable=True
            )
            # Continuar con advertencia
            warnings.append("Poco texto extraído - posible PDF escaneado")
            
    except Exception as e:
        error_type = detect_error_type(e, ProcessingStage.TEXT_EXTRACTION)
        result.add_error(
            error_type,
            ProcessingStage.TEXT_EXTRACTION,
            str(e),
            recoverable=True
        )
        # Continuar pero marcar como problema
        warnings.append(f"Error de extracción: {str(e)[:100]}")
    
    result.stage_reached = ProcessingStage.AI_PARSING
    
    # ===== ETAPA 3: PARSING CON AI =====
    parsed_data = {}
    try:
        if extracted_text and len(extracted_text.strip()) >= 20:
            parsed_data = await atlas_service.parse_resume(extracted_text)
        else:
            parsed_data = {"full_name": None, "error": "Texto insuficiente para parsing"}
            
    except Exception as e:
        logger.error(f"Error parsing resume with Atlas: {str(e)}")
        error_type = detect_error_type(e, ProcessingStage.AI_PARSING)
        result.add_error(
            error_type,
            ProcessingStage.AI_PARSING,
            str(e),
            recoverable=True
        )
        parsed_data = {"full_name": None, "error": str(e)}
    
    # Validar que tenemos al menos un nombre
    full_name = parsed_data.get('full_name')
    if not full_name or full_name == "Desconocido" or not isinstance(full_name, str):
        # Intentar usar el nombre del archivo como fallback
        filename_without_ext = file.filename.rsplit('.', 1)[0] if '.' in file.filename else file.filename
        # Limpiar el nombre del archivo (quitar guiones, underscores, etc.)
        fallback_name = filename_without_ext.replace('_', ' ').replace('-', ' ').title()
        
        if len(fallback_name) > 3 and not any(c.isdigit() for c in fallback_name):
            parsed_data['full_name'] = fallback_name
            warnings.append(f"Nombre extraído del archivo: {fallback_name}")
        else:
            parsed_data['full_name'] = f"Candidato - {file.filename}"
            result.add_error(
                ErrorType.AI_PARSING_FAILED,
                ProcessingStage.AI_PARSING,
                "No se pudo extraer el nombre del candidato",
                recoverable=True
            )
    
    result.extracted_name = parsed_data.get('full_name')
    result.extracted_email = parsed_data.get('email')
    
    result.stage_reached = ProcessingStage.DUPLICATE_DETECTION
    
    # ===== ETAPA 4: DETECCIÓN DE DUPLICADOS (V2 con bloqueo duro) =====
    
    # 4A: Primero verificar duplicados DUROS (L1: email, L2: linkedin)
    hard_duplicate = None
    try:
        hard_duplicate = await duplicate_detector_v2.detect_hard_duplicates(parsed_data)
    except Exception as e:
        logger.error(f"Error detecting hard duplicates: {str(e)}")
        warnings.append("Error en detección de duplicados")
    
    # Si hay duplicado DURO, BLOQUEAR y ofrecer actualizar CV existente
    if hard_duplicate:
        result.status = "duplicate_blocked"
        result.stage_reached = ProcessingStage.DUPLICATE_DETECTION
        result.processing_time_ms = int((time.time() - start_time) * 1000)
        
        response = result.to_response()
        response["duplicate_blocked"] = True
        response["existing_candidate"] = hard_duplicate
        response["parsed_data"] = parsed_data
        response["message"] = (
            f"Este candidato ya existe en el sistema ({hard_duplicate['reason']}). "
            f"¿Deseas actualizar su CV existente?"
        )
        response["actions"] = {
            "update_cv": f"/api/candidates/{hard_duplicate['candidate_id']}/update-cv",
            "view_candidate": f"/candidates/{hard_duplicate['candidate_id']}"
        }
        return response
    
    # 4B: Verificar duplicados SUAVES (L3-L5: teléfono+nombre, nombre+empresas, etc.)
    soft_duplicates = []
    try:
        soft_duplicates = await duplicate_detector_v2.detect_soft_duplicates(parsed_data)
    except Exception as e:
        logger.error(f"Error detecting soft duplicates: {str(e)}")
    
    # Si hay duplicados suaves de alta confianza (>=85%), sugerir revisión
    if soft_duplicates and soft_duplicates[0]['confidence'] >= 0.85:
        result.status = "duplicate_suggested"
        result.stage_reached = ProcessingStage.DUPLICATE_DETECTION
        result.processing_time_ms = int((time.time() - start_time) * 1000)
        
        response = result.to_response()
        response["duplicate_suggested"] = True
        response["potential_duplicates"] = soft_duplicates
        response["parsed_data"] = parsed_data
        response["message"] = "Se encontraron posibles duplicados. Revisa antes de continuar."
        response["actions"] = {
            "create_anyway": "/api/candidates/create-confirmed",
            "merge": "/api/candidates/merge"
        }
        return response
    
    # ===== ETAPA 5: CREAR/ACTUALIZAR CANDIDATO =====
    if not candidate_id:
        candidate_id = str(uuid.uuid4())
        result.candidate_id = candidate_id
        result.stage_reached = ProcessingStage.AI_CLASSIFICATION
        
        # Crear objeto candidato con datos parseados (con validación defensiva)
        try:
            # Limpiar y validar previous_companies
            cleaned_companies = clean_previous_companies(parsed_data.get('previous_companies', []))
            previous_companies_objs = []
            for pc in cleaned_companies:
                try:
                    previous_companies_objs.append(PreviousCompany(**pc))
                except Exception as pc_err:
                    logger.warning(f"Saltando previous_company inválida: {pc_err}")
            
            # Validar years_experience de forma segura
            years_exp = safe_int(parsed_data.get('years_experience'))
            
            # Validar skills y languages como listas
            skills = safe_list(parsed_data.get('skills'))
            languages = safe_list(parsed_data.get('languages'))
            
            candidate = Candidate(
                id=candidate_id,
                full_name=safe_string(parsed_data.get('full_name'), f"Candidato - {file.filename}"),
                email=safe_string(parsed_data.get('email')),
                phone=safe_string(parsed_data.get('phone')),
                city=safe_string(parsed_data.get('city')),
                state=safe_string(parsed_data.get('state')),
                country=safe_string(parsed_data.get('country'), 'México'),
                linkedin_url=safe_string(parsed_data.get('linkedin_url')),
                current_company=safe_string(parsed_data.get('current_company')),
                current_title=safe_string(parsed_data.get('current_title')),
                years_experience=years_exp,
                skills=skills,
                languages=languages,
                previous_companies=previous_companies_objs,
                source="CV Upload",
                created_by=current_user.id
            )
            
            # Inferir current_title y current_company de previous_companies si no vienen directamente
            if not candidate.current_title and candidate.previous_companies:
                # Ordenar por fecha de fin (más reciente primero) o tomar el primero
                most_recent = candidate.previous_companies[0]
                candidate.current_title = most_recent.title
                candidate.current_company = most_recent.company_name
            
            # Construir location desde city/state si no viene
            if not candidate.city and not candidate.state:
                if parsed_data.get('city'):
                    candidate.city = safe_string(parsed_data.get('city'))
                if parsed_data.get('state'):
                    candidate.state = safe_string(parsed_data.get('state'))
        except Exception as e:
            result.status = "failed"
            result.add_error(
                ErrorType.VALIDATION_ERROR,
                ProcessingStage.DATABASE_SAVE,
                f"Error creando candidato: {str(e)}",
                recoverable=True
            )
            result.processing_time_ms = int((time.time() - start_time) * 1000)
            return result.to_response()
        
        # ===== ETAPA 6: CLASIFICACIÓN CON AI =====
        try:
            if extracted_text and len(extracted_text.strip()) >= 50:
                classification = await atlas_service.classify_candidate(parsed_data, extracted_text)
                
                candidate.industry = classification.get('industry')
                candidate.functional_area = classification.get('functional_area')
                candidate.seniority = classification.get('seniority')
                candidate.tags = classification.get('suggested_tags', [])
                
                candidate.ai_classification = AIClassification(
                    industry=classification.get('industry'),
                    functional_area=classification.get('functional_area'),
                    seniority=classification.get('seniority'),
                    confidence_score=classification.get('confidence_score', 0.0),
                    suggested_tags=classification.get('suggested_tags', [])
                )
        except Exception as e:
            logger.error(f"Error classifying candidate: {str(e)}")
            result.add_error(
                ErrorType.AI_CLASSIFICATION_FAILED,
                ProcessingStage.AI_CLASSIFICATION,
                str(e),
                recoverable=True
            )
            warnings.append("Clasificación AI no disponible")
        
        # Generar resumen con Atlas
        try:
            if extracted_text and len(extracted_text.strip()) >= 50:
                summary = await atlas_service.generate_summary(parsed_data, extracted_text)
                candidate.ai_summary = summary
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            warnings.append("Resumen AI no generado")
        
        result.stage_reached = ProcessingStage.STORAGE
        
        # ===== ETAPA 7: ALMACENAMIENTO DE ARCHIVO =====
        try:
            storage_result = storage_service.upload_resume(
                file_data,
                candidate_id,
                file.filename,
                file.content_type
            )
            
            resume_file = ResumeFile(
                file_name=file.filename,
                file_path=storage_result['storage_path'],
                file_type=storage_result['content_type'],
                upload_date=datetime.now(timezone.utc)
            )
            candidate.resume_files = [resume_file]
            result.file_id = storage_result.get('file_id')
            
        except Exception as e:
            logger.error(f"Error uploading to storage: {str(e)}")
            result.add_error(
                ErrorType.STORAGE_UPLOAD_FAILED,
                ProcessingStage.STORAGE,
                str(e),
                recoverable=True
            )
            
            # Fallback a almacenamiento local
            try:
                upload_path = UPLOAD_DIR / candidate_id
                upload_path.mkdir(parents=True, exist_ok=True)
                file_path = upload_path / file.filename
                with open(file_path, "wb") as f:
                    f.write(file_data)
                
                resume_file = ResumeFile(
                    file_name=file.filename,
                    file_path=str(file_path.relative_to(ROOT_DIR)),
                    file_type=Path(file.filename).suffix,
                    upload_date=datetime.now(timezone.utc)
                )
                candidate.resume_files = [resume_file]
                warnings.append("Archivo guardado localmente (fallback)")
            except Exception as local_e:
                logger.error(f"Error saving locally: {str(local_e)}")
        
        result.stage_reached = ProcessingStage.EMBEDDING_GENERATION
        
        # ===== ETAPA 8: GENERACIÓN DE EMBEDDINGS =====
        try:
            candidate_dict = candidate.model_dump()
            embedding = await embedding_service.generate_candidate_embedding(candidate_dict)
            candidate.embedding = embedding
            candidate.embedding_updated_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            result.add_error(
                ErrorType.EMBEDDING_API_ERROR,
                ProcessingStage.EMBEDDING_GENERATION,
                str(e),
                recoverable=True
            )
            warnings.append("Búsqueda semántica no disponible para este candidato")
        
        # Generar campos normalizados para búsqueda
        candidate.full_name_normalized = normalize_for_search(candidate.full_name)
        if candidate.current_company:
            candidate.company_normalized = normalize_for_search(candidate.current_company)
        if candidate.current_title:
            candidate.title_normalized = normalize_for_search(candidate.current_title)
        
        result.stage_reached = ProcessingStage.DATABASE_SAVE
        
        # ===== ETAPA 9: GUARDAR EN BASE DE DATOS =====
        try:
            candidate_doc = candidate.model_dump()
            candidate_doc['created_at'] = candidate_doc['created_at'].isoformat()
            candidate_doc['updated_at'] = candidate_doc['updated_at'].isoformat()
            
            for note in candidate_doc.get('notes', []):
                note['created_at'] = note['created_at'].isoformat()
            
            if candidate_doc.get('ai_classification'):
                candidate_doc['ai_classification']['classified_at'] = candidate_doc['ai_classification']['classified_at'].isoformat()
            
            if candidate_doc.get('embedding_updated_at'):
                candidate_doc['embedding_updated_at'] = candidate_doc['embedding_updated_at'].isoformat()
            
            for resume in candidate_doc.get('resume_files', []):
                resume['upload_date'] = resume['upload_date'].isoformat()
            
            await db.candidates.insert_one(candidate_doc)
            
            # Crear primera versión de CV
            if candidate.resume_files and len(candidate.resume_files) > 0:
                resume = candidate.resume_files[0]
                parsed_snapshot = {
                    "full_name": candidate.full_name,
                    "current_title": candidate.current_title,
                    "current_company": candidate.current_company,
                    "years_experience": candidate.years_experience,
                    "industry": candidate.industry,
                    "functional_area": candidate.functional_area,
                    "seniority": candidate.seniority,
                    "skills": candidate.skills,
                    "previous_companies": [c.model_dump() if hasattr(c, 'model_dump') else c for c in (candidate.previous_companies or [])],
                    "languages": candidate.languages,
                    "email": candidate.email,
                    "phone": candidate.phone,
                    "parsed_at": datetime.now(timezone.utc).isoformat()
                }
                
                await cv_version_service.create_version(
                    candidate_id=candidate_id,
                    file_key=resume.file_path,
                    file_name=resume.file_name,
                    file_type=resume.file_type or "application/pdf",
                    uploaded_by=current_user.id,
                    uploaded_by_name=current_user.name,
                    upload_source="manual",
                    parsed_snapshot=parsed_snapshot
                )
            
            # Guardar sugerencias de duplicados si hay (duplicados suaves)
            if soft_duplicates:
                await DuplicateSuggestion.create_suggestion(
                    db, candidate_id, soft_duplicates, current_user.id
                )
                
        except Exception as e:
            logger.error(f"Error saving to database: {str(e)}")
            result.status = "failed"
            result.add_error(
                ErrorType.DATABASE_SAVE_FAILED,
                ProcessingStage.DATABASE_SAVE,
                str(e),
                recoverable=True
            )
            result.processing_time_ms = int((time.time() - start_time) * 1000)
            return result.to_response()
    
    else:
        # Agregar CV a candidato existente
        result.candidate_id = candidate_id
        result.stage_reached = ProcessingStage.STORAGE
        
        try:
            storage_result = storage_service.upload_resume(
                file_data,
                candidate_id,
                file.filename,
                file.content_type
            )
            
            resume_file = ResumeFile(
                file_name=file.filename,
                file_path=storage_result['storage_path'],
                file_type=storage_result['content_type'],
                upload_date=datetime.now(timezone.utc)
            )
        except Exception as e:
            logger.error(f"Error uploading to storage: {str(e)}")
            # Fallback local
            upload_path = UPLOAD_DIR / candidate_id
            upload_path.mkdir(parents=True, exist_ok=True)
            file_path = upload_path / file.filename
            with open(file_path, "wb") as f:
                f.write(file_data)
            
            resume_file = ResumeFile(
                file_name=file.filename,
                file_path=str(file_path.relative_to(ROOT_DIR)),
                file_type=Path(file.filename).suffix,
                upload_date=datetime.now(timezone.utc)
            )
            warnings.append("Archivo guardado localmente")
        
        resume_dict = resume_file.model_dump()
        resume_dict['upload_date'] = resume_dict['upload_date'].isoformat()
        
        result.stage_reached = ProcessingStage.DATABASE_SAVE
        
        await db.candidates.update_one(
            {"id": candidate_id},
            {
                "$push": {"resume_files": resume_dict},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
    
    # ===== RESULTADO FINAL =====
    result.stage_reached = ProcessingStage.COMPLETED
    result.processing_time_ms = int((time.time() - start_time) * 1000)
    
    # Determinar estado final
    if len(result.errors) == 0:
        result.status = "success"
    elif any(e.error_type in [ErrorType.DATABASE_SAVE_FAILED, ErrorType.FILE_CORRUPTED] for e in result.errors):
        result.status = "failed"
    else:
        result.status = "partial_success"
    
    result.warnings = warnings
    
    if result.status == "success" and result.candidate_id:
        await log_activity(current_user, "candidate_uploaded", "candidate", result.candidate_id, (parsed_data or {}).get("full_name"))
    
    response = result.to_response()
    response["parsed_data"] = parsed_data
    response["has_low_confidence_duplicates"] = len(soft_duplicates) > 0 and soft_duplicates[0]['confidence'] < 0.85 if soft_duplicates else False
    
    return response


@api_router.post("/candidates/retry-processing/{candidate_id}")
async def retry_candidate_processing(
    candidate_id: str,
    reprocess_classification: bool = Query(True),
    reprocess_embedding: bool = Query(True),
    current_user: User = Depends(get_current_user)
):
    """
    Reintentar procesamiento de un candidato que tuvo errores.
    Permite reprocesar clasificación y/o embeddings.
    """
    candidate_doc = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    
    if not candidate_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato no encontrado"
        )
    
    updates = {}
    errors = []
    warnings = []
    
    # Obtener texto del CV si existe
    resume_text = ""
    if candidate_doc.get('resume_files'):
        first_resume = candidate_doc['resume_files'][0]
        resume_path = ROOT_DIR / first_resume['file_path']
        try:
            resume_text = DocumentParser.extract_text(str(resume_path))
        except Exception as e:
            errors.append(f"No se pudo extraer texto del CV: {str(e)}")
    
    # Reprocesar clasificación
    if reprocess_classification and resume_text:
        try:
            classification = await atlas_service.classify_candidate(candidate_doc, resume_text)
            
            updates['industry'] = classification.get('industry')
            updates['functional_area'] = classification.get('functional_area')
            updates['seniority'] = classification.get('seniority')
            updates['tags'] = classification.get('suggested_tags', [])
            
            ai_classification = AIClassification(
                industry=classification.get('industry'),
                functional_area=classification.get('functional_area'),
                seniority=classification.get('seniority'),
                confidence_score=classification.get('confidence_score', 0.0),
                suggested_tags=classification.get('suggested_tags', [])
            )
            ai_class_dict = ai_classification.model_dump()
            ai_class_dict['classified_at'] = ai_class_dict['classified_at'].isoformat()
            updates['ai_classification'] = ai_class_dict
            
        except Exception as e:
            errors.append(f"Error en clasificación: {str(e)}")
    
    # Reprocesar embedding
    if reprocess_embedding:
        try:
            embedding = await embedding_service.generate_candidate_embedding(candidate_doc)
            updates['embedding'] = embedding
            updates['embedding_updated_at'] = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            errors.append(f"Error generando embedding: {str(e)}")
    
    # Aplicar actualizaciones
    if updates:
        updates['updated_at'] = datetime.now(timezone.utc).isoformat()
        await db.candidates.update_one(
            {"id": candidate_id},
            {"$set": updates}
        )
    
    return {
        "status": "success" if not errors else "partial_success",
        "candidate_id": candidate_id,
        "updates_applied": list(updates.keys()),
        "errors": errors,
        "warnings": warnings
    }


# ============= BATCH UPLOAD (PROCESAMIENTO EN BACKGROUND) =============

async def process_cv_job(job, file_data: bytes, file_metadata: Dict) -> Dict:
    """
    Función que procesa un CV individual en background.
    Esta función es llamada por el BackgroundProcessor.
    """
    from error_handling import ProcessingStage, ErrorType, detect_error_type
    
    result = {
        "status": "processing",
        "candidate_id": None,
        "extracted_name": None,
        "extracted_email": None,
        "errors": [],
        "warnings": []
    }
    
    user_id = file_metadata.get('user_id')
    file_name = file_metadata.get('file_name')
    content_type = file_metadata.get('content_type')
    
    # Actualizar progreso
    job.progress = 10
    job.current_stage = "text_extraction"
    _t = time.time()
    
    # 1. Extracción de texto
    extracted_text = ""
    try:
        extracted_text = DocumentParser.extract_text_from_bytes(file_data, content_type)
        
        if not extracted_text or len(extracted_text.strip()) < 50:
            result["warnings"].append("Poco texto extraído - posible PDF escaneado")
    except Exception as e:
        error_type = detect_error_type(e, ProcessingStage.TEXT_EXTRACTION)
        result["errors"].append({
            "type": error_type.value,
            "stage": "text_extraction",
            "message": str(e),
            "recoverable": True
        })
        result["warnings"].append(f"Error de extracción: {str(e)[:100]}")
    
    job.stage_timings["text_extraction"] = int((time.time() - _t) * 1000)
    job.progress = 25
    job.current_stage = "ai_parsing"
    _t = time.time()
    
    # 2. Parsing con AI
    parsed_data = {}
    try:
        if extracted_text and len(extracted_text.strip()) >= 20:
            parsed_data = await atlas_service.parse_resume(extracted_text)
        else:
            parsed_data = {"full_name": None}
    except Exception as e:
        result["errors"].append({
            "type": "ai_parsing_failed",
            "stage": "ai_parsing",
            "message": str(e),
            "recoverable": True
        })
    
    # Validar nombre
    full_name = parsed_data.get('full_name')
    if not full_name or not isinstance(full_name, str):
        filename_without_ext = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
        fallback_name = filename_without_ext.replace('_', ' ').replace('-', ' ').title()
        
        if len(fallback_name) > 3 and not any(c.isdigit() for c in fallback_name):
            parsed_data['full_name'] = fallback_name
            result["warnings"].append(f"Nombre extraído del archivo: {fallback_name}")
        else:
            parsed_data['full_name'] = f"Candidato - {file_name}"
    
    result["extracted_name"] = parsed_data.get('full_name')
    result["extracted_email"] = parsed_data.get('email')
    
    job.stage_timings["ai_parsing"] = int((time.time() - _t) * 1000)
    job.progress = 40
    job.current_stage = "duplicate_detection"
    _t = time.time()
    
    # 3. Detección de duplicados
    duplicates = []
    try:
        duplicates = await duplicate_detector.detect_duplicates(parsed_data)
    except Exception as e:
        result["warnings"].append("Error en detección de duplicados")
    
    # Si hay duplicado de alta confianza, marcar pero continuar
    if duplicates and max(d['confidence'] for d in duplicates) >= 0.90:
        result["warnings"].append(f"Posible duplicado detectado (confianza >= 90%)")
    
    job.stage_timings["duplicate_detection"] = int((time.time() - _t) * 1000)
    job.progress = 50
    job.current_stage = "creating_candidate"
    
    # 4. Crear candidato (con validación defensiva)
    candidate_id = str(uuid.uuid4())
    
    try:
        # Limpiar y validar previous_companies
        cleaned_companies = clean_previous_companies(parsed_data.get('previous_companies', []))
        previous_companies_objs = []
        for pc in cleaned_companies:
            try:
                previous_companies_objs.append(PreviousCompany(**pc))
            except Exception as pc_err:
                logger.warning(f"[Batch] Saltando previous_company inválida: {pc_err}")
        
        # Validar years_experience de forma segura
        years_exp = safe_int(parsed_data.get('years_experience'))
        
        # Validar skills y languages como listas
        skills = safe_list(parsed_data.get('skills'))
        languages = safe_list(parsed_data.get('languages'))
        
        candidate = Candidate(
            id=candidate_id,
            full_name=safe_string(parsed_data.get('full_name'), f"Candidato - {file_name}"),
            email=safe_string(parsed_data.get('email')),
            phone=safe_string(parsed_data.get('phone')),
            city=safe_string(parsed_data.get('city')),
            state=safe_string(parsed_data.get('state')),
            country=safe_string(parsed_data.get('country'), 'México'),
            linkedin_url=safe_string(parsed_data.get('linkedin_url')),
            current_company=safe_string(parsed_data.get('current_company')),
            current_title=safe_string(parsed_data.get('current_title')),
            years_experience=years_exp,
            skills=skills,
            languages=languages,
            previous_companies=previous_companies_objs,
            source="CV Upload (Batch)",
            created_by=user_id
        )
    except Exception as e:
        result["status"] = "failed"
        result["errors"].append({
            "type": "validation_error",
            "stage": "creating_candidate",
            "message": str(e),
            "recoverable": True
        })
        return result
    
    job.progress = 60
    job.current_stage = "ai_classification"
    _t = time.time()
    
    # 5. Clasificación AI + Resumen AI (en paralelo — 2 llamadas LLM independientes entre sí)
    classification_task = None
    summary_task = None
    if extracted_text and len(extracted_text.strip()) >= 50:
        classification_task = asyncio.create_task(atlas_service.classify_candidate(parsed_data, extracted_text))
        summary_task = asyncio.create_task(atlas_service.generate_summary(parsed_data, extracted_text))
    
    try:
        if classification_task:
            classification = await classification_task
            
            candidate.industry = classification.get('industry')
            candidate.functional_area = classification.get('functional_area')
            candidate.seniority = classification.get('seniority')
            candidate.tags = classification.get('suggested_tags', [])
            
            candidate.ai_classification = AIClassification(
                industry=classification.get('industry'),
                functional_area=classification.get('functional_area'),
                seniority=classification.get('seniority'),
                confidence_score=classification.get('confidence_score', 0.0),
                suggested_tags=classification.get('suggested_tags', [])
            )
    except Exception as e:
        result["errors"].append({
            "type": "ai_classification_failed",
            "stage": "ai_classification",
            "message": str(e),
            "recoverable": True
        })
    
    # Resumen (misma etapa, corre en paralelo con la clasificación)
    try:
        if summary_task:
            candidate.ai_summary = await summary_task
    except Exception as e:
        result["warnings"].append("Resumen AI no generado")
    
    job.stage_timings["ai_classification_y_resumen"] = int((time.time() - _t) * 1000)
    job.progress = 75
    job.current_stage = "storage"
    _t = time.time()
    
    # 6. Almacenar archivo
    try:
        storage_result = storage_service.upload_resume(
            file_data,
            candidate_id,
            file_name,
            content_type
        )
        
        resume_file = ResumeFile(
            file_name=file_name,
            file_path=storage_result['storage_path'],
            file_type=storage_result['content_type'],
            upload_date=datetime.now(timezone.utc)
        )
        candidate.resume_files = [resume_file]
    except Exception as e:
        result["warnings"].append("Archivo guardado localmente (fallback)")
        
        upload_path = UPLOAD_DIR / candidate_id
        upload_path.mkdir(parents=True, exist_ok=True)
        file_path = upload_path / file_name
        with open(file_path, "wb") as f:
            f.write(file_data)
        
        resume_file = ResumeFile(
            file_name=file_name,
            file_path=str(file_path.relative_to(ROOT_DIR)),
            file_type=Path(file_name).suffix,
            upload_date=datetime.now(timezone.utc)
        )
        candidate.resume_files = [resume_file]
    
    job.stage_timings["storage"] = int((time.time() - _t) * 1000)
    job.progress = 85
    job.current_stage = "embedding_generation"
    _t = time.time()
    
    # 7. Embeddings (opcional)
    try:
        embedding = await embedding_service.generate_candidate_embedding(candidate.model_dump())
        if embedding:
            candidate.embedding = embedding
            candidate.embedding_updated_at = datetime.now(timezone.utc)
    except Exception as e:
        result["warnings"].append("Búsqueda semántica no disponible")
    
    # Normalizar campos
    candidate.full_name_normalized = normalize_for_search(candidate.full_name)
    if candidate.current_company:
        candidate.company_normalized = normalize_for_search(candidate.current_company)
    if candidate.current_title:
        candidate.title_normalized = normalize_for_search(candidate.current_title)
    
    job.stage_timings["embedding_generation"] = int((time.time() - _t) * 1000)
    job.progress = 95
    job.current_stage = "database_save"
    _t = time.time()
    
    # 8. Guardar en DB
    try:
        candidate_doc = candidate.model_dump()
        candidate_doc['created_at'] = candidate_doc['created_at'].isoformat()
        candidate_doc['updated_at'] = candidate_doc['updated_at'].isoformat()
        
        for note in candidate_doc.get('notes', []):
            note['created_at'] = note['created_at'].isoformat()
        
        if candidate_doc.get('ai_classification'):
            candidate_doc['ai_classification']['classified_at'] = candidate_doc['ai_classification']['classified_at'].isoformat()
        
        if candidate_doc.get('embedding_updated_at'):
            candidate_doc['embedding_updated_at'] = candidate_doc['embedding_updated_at'].isoformat()
        
        for resume in candidate_doc.get('resume_files', []):
            resume['upload_date'] = resume['upload_date'].isoformat()
        
        await db.candidates.insert_one(candidate_doc)
        
        if duplicates:
            await DuplicateSuggestion.create_suggestion(
                db, candidate_id, duplicates, user_id
            )
    except Exception as e:
        result["status"] = "failed"
        result["errors"].append({
            "type": "database_save_failed",
            "stage": "database_save",
            "message": str(e),
            "recoverable": True
        })
        return result
    
    job.stage_timings["database_save"] = int((time.time() - _t) * 1000)
    job.progress = 100
    job.current_stage = "completed"
    
    # Determinar estado final
    result["candidate_id"] = candidate_id
    if len(result["errors"]) == 0:
        result["status"] = "success"
    else:
        result["status"] = "partial_success"
    
    return result


@api_router.post("/candidates/upload-batch")
async def upload_batch(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload múltiples CVs para procesamiento en background.
    
    Retorna inmediatamente con un batch_id para monitorear el progreso.
    Los archivos se procesan en paralelo en background (máx 3 simultáneos).
    """
    if len(files) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se enviaron archivos"
        )
    
    if len(files) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Máximo 50 archivos por lote"
        )
    
    # Inicializar processor si es necesario
    await background_processor.initialize()
    await background_processor.start_workers(process_cv_job)
    
    # Crear batch
    batch = background_processor.create_batch(current_user.id, len(files))
    
    # Agregar cada archivo a la cola
    jobs_added = []
    for file in files:
        file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        
        # Solo PDF y DOCX soportados
        if file_ext not in ['pdf', 'docx']:
            reason = "Formato no soportado. Solo se permiten PDF y DOCX."
            if file_ext == 'doc':
                reason = "Formato DOC (Word antiguo) no soportado. Convierte a PDF o DOCX."
            jobs_added.append({
                "file_name": file.filename,
                "status": "rejected",
                "reason": reason
            })
            continue
        
        file_data = await file.read()
        
        if len(file_data) == 0:
            jobs_added.append({
                "file_name": file.filename,
                "status": "rejected",
                "reason": "Archivo vacío"
            })
            continue
        
        if len(file_data) > 10 * 1024 * 1024:
            jobs_added.append({
                "file_name": file.filename,
                "status": "rejected",
                "reason": "Archivo muy grande (máx 10MB)"
            })
            continue
        
        job = await background_processor.add_job(
            batch_id=batch.batch_id,
            file_name=file.filename,
            file_data=file_data,
            content_type=file.content_type,
            user_id=current_user.id
        )
        
        jobs_added.append({
            "file_name": file.filename,
            "job_id": job.job_id,
            "status": "queued"
        })
    
    return {
        "batch_id": batch.batch_id,
        "total_files": len(files),
        "queued": len([j for j in jobs_added if j.get("status") == "queued"]),
        "rejected": len([j for j in jobs_added if j.get("status") == "rejected"]),
        "jobs": jobs_added,
        "message": "Archivos en cola para procesamiento. Use GET /api/candidates/batch/{batch_id} para monitorear."
    }


# ============= ATLAS AI ROUTES =============

@api_router.post("/atlas/classify/{candidate_id}")
async def classify_candidate_by_atlas(
    candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """Classify candidate using Atlas AI"""
    candidate_doc = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    
    if not candidate_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato no encontrado"
        )
    
    # Get resume text
    resume_text = ""
    if candidate_doc.get('resume_files'):
        first_resume = candidate_doc['resume_files'][0]
        resume_path = ROOT_DIR / first_resume['file_path']
        try:
            resume_text = DocumentParser.extract_text(str(resume_path))
        except:
            pass
    
    # Classify
    classification = await atlas_service.classify_candidate(candidate_doc, resume_text)
    
    # Update candidate
    ai_classification = AIClassification(
        industry=classification.get('industry'),
        functional_area=classification.get('functional_area'),
        seniority=classification.get('seniority'),
        confidence_score=classification.get('confidence_score', 0.0),
        suggested_tags=classification.get('suggested_tags', [])
    )
    
    ai_class_dict = ai_classification.model_dump()
    ai_class_dict['classified_at'] = ai_class_dict['classified_at'].isoformat()
    
    await db.candidates.update_one(
        {"id": candidate_id},
        {
            "$set": {
                "ai_classification": ai_class_dict,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    return classification


@api_router.post("/atlas/approve-classification/{candidate_id}")
async def approve_atlas_classification(
    candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """Approve Atlas classification and apply to candidate.
    For unclassified candidates (ai_classification=null), creates a manual approval record.
    """
    candidate_doc = await db.candidates.find_one(
        {"id": candidate_id}, 
        {"_id": 0, "ai_classification": 1, "industry": 1, "functional_area": 1, "seniority": 1, "tags": 1}
    )
    
    if not candidate_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato no encontrado"
        )
    
    now = datetime.now(timezone.utc).isoformat()
    ai_class = candidate_doc.get('ai_classification') or {}
    
    if ai_class:
        # Has AI classification - apply it
        update_data = {
            "industry": ai_class.get('industry') or candidate_doc.get('industry'),
            "functional_area": ai_class.get('functional_area') or candidate_doc.get('functional_area'),
            "seniority": ai_class.get('seniority') or candidate_doc.get('seniority'),
            "tags": ai_class.get('suggested_tags') or candidate_doc.get('tags', []),
            "ai_classification.approved_by_recruiter": True,
            "ai_classification.approved_at": now,
            "ai_classification.approved_by": current_user.id,
            "updated_at": now
        }
    else:
        # No AI classification - create manual approval record
        update_data = {
            "ai_classification": {
                "approved_by_recruiter": True,
                "approved_at": now,
                "approved_by": current_user.id,
                "source": "manual_approval",
                "confidence_score": 1.0
            },
            "updated_at": now
        }
    
    await db.candidates.update_one(
        {"id": candidate_id},
        {"$set": update_data}
    )
    
    full_name_doc = await db.candidates.find_one({"id": candidate_id}, {"_id": 0, "full_name": 1})
    await log_activity(current_user, "classification_approved", "candidate", candidate_id, (full_name_doc or {}).get("full_name"))
    
    return {"message": "Clasificación aprobada"}


# ============= CLASSIFICATION REVIEW ENDPOINTS =============

@api_router.get("/atlas/classifications/pending")
async def get_pending_classifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """
    Get candidates with low-confidence classifications OR no classification at all.
    Criteria: 
      - ai_classification is null/missing (unclassified), OR
      - confidence_score < 0.75 AND approved_by_recruiter = false
    """
    skip = (page - 1) * limit
    
    # Build aggregation pipeline to include both unclassified and low-confidence candidates
    pipeline = [
        {"$match": {"is_deleted": {"$ne": True}}},
        # Add computed fields for filtering
        {"$addFields": {
            "has_classification": {"$ifNull": ["$ai_classification", None]},
            "conf_score": {"$ifNull": ["$ai_classification.confidence_score", 0]},
            "is_approved": {"$ifNull": ["$ai_classification.approved_by_recruiter", False]}
        }},
        # Match: no classification OR (low confidence AND not approved)
        {"$match": {
            "$or": [
                {"has_classification": None},
                {
                    "$and": [
                        {"conf_score": {"$lt": 0.75}},
                        {"is_approved": False}
                    ]
                }
            ]
        }},
        # Sort: unclassified first (conf_score=0), then by confidence ascending
        {"$sort": {"conf_score": 1, "created_at": -1}},
        {"$facet": {
            "data": [{"$skip": skip}, {"$limit": limit}],
            "total": [{"$count": "count"}]
        }}
    ]
    
    result = await db.candidates.aggregate(pipeline).to_list(1)
    
    if not result:
        return {"candidates": [], "total": 0, "page": page, "limit": limit, "pages": 0}
    
    facet_result = result[0]
    candidates_data = facet_result.get("data", [])
    total_data = facet_result.get("total", [])
    total = total_data[0]["count"] if total_data else 0
    
    # Format response
    results = []
    for c in candidates_data:
        ai_class = c.get("ai_classification") or {}
        results.append({
            "id": c.get("id"),
            "full_name": c.get("full_name"),
            "current_title": c.get("current_title"),
            "current_company": c.get("current_company"),
            "current_classification": {
                "industry": c.get("industry"),
                "functional_area": c.get("functional_area"),
                "seniority": c.get("seniority"),
                "tags": c.get("tags", [])
            },
            "proposed_classification": {
                "industry": ai_class.get("industry"),
                "functional_area": ai_class.get("functional_area"),
                "seniority": ai_class.get("seniority"),
                "suggested_tags": ai_class.get("suggested_tags", [])
            },
            "confidence_score": ai_class.get("confidence_score", 0),
            "classified_at": ai_class.get("classified_at"),
            "created_at": c.get("created_at")
        })
    
    return {
        "candidates": results,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit if total > 0 else 0
    }


@api_router.get("/atlas/classifications/pending/count")
async def get_pending_classifications_count(
    current_user: User = Depends(get_current_user)
):
    """Get count of candidates pending classification review (for badge)
    Includes: unclassified candidates AND low-confidence classifications not yet approved
    """
    pipeline = [
        {"$match": {"is_deleted": {"$ne": True}}},
        {"$addFields": {
            "has_classification": {"$ifNull": ["$ai_classification", None]},
            "conf_score": {"$ifNull": ["$ai_classification.confidence_score", 0]},
            "is_approved": {"$ifNull": ["$ai_classification.approved_by_recruiter", False]}
        }},
        {"$match": {
            "$or": [
                {"has_classification": None},
                {
                    "$and": [
                        {"conf_score": {"$lt": 0.75}},
                        {"is_approved": False}
                    ]
                }
            ]
        }},
        {"$count": "count"}
    ]
    
    result = await db.candidates.aggregate(pipeline).to_list(1)
    count = result[0]["count"] if result else 0
    
    return {"count": count}


class BulkApproveRequest(PydanticBaseModel):
    candidate_ids: List[str]


@api_router.post("/atlas/classifications/bulk-approve")
async def bulk_approve_classifications(
    request: BulkApproveRequest,
    current_user: User = Depends(get_current_user)
):
    """Approve multiple classifications at once. 
    For unclassified candidates (ai_classification=null), marks as manually approved without changing fields.
    """
    if not request.candidate_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Debe especificar al menos un candidato"
        )
    
    approved_count = 0
    errors = []
    now = datetime.now(timezone.utc).isoformat()
    
    for candidate_id in request.candidate_ids:
        try:
            candidate_doc = await db.candidates.find_one(
                {"id": candidate_id, "is_deleted": {"$ne": True}},
                {"_id": 0, "ai_classification": 1, "industry": 1, "functional_area": 1, "seniority": 1, "tags": 1}
            )
            
            if not candidate_doc:
                errors.append({"id": candidate_id, "error": "No encontrado"})
                continue
            
            ai_class = candidate_doc.get("ai_classification") or {}
            
            # Handle both classified and unclassified candidates
            if ai_class:
                # Has AI classification - apply it
                update_data = {
                    "industry": ai_class.get("industry") or candidate_doc.get("industry"),
                    "functional_area": ai_class.get("functional_area") or candidate_doc.get("functional_area"),
                    "seniority": ai_class.get("seniority") or candidate_doc.get("seniority"),
                    "tags": ai_class.get("suggested_tags") or candidate_doc.get("tags", []),
                    "ai_classification.approved_by_recruiter": True,
                    "ai_classification.approved_at": now,
                    "ai_classification.approved_by": current_user.id,
                    "updated_at": now
                }
            else:
                # No AI classification - create minimal approval record
                update_data = {
                    "ai_classification": {
                        "approved_by_recruiter": True,
                        "approved_at": now,
                        "approved_by": current_user.id,
                        "source": "manual_approval",
                        "confidence_score": 1.0  # Manual = full confidence
                    },
                    "updated_at": now
                }
            
            await db.candidates.update_one(
                {"id": candidate_id},
                {"$set": update_data}
            )
            approved_count += 1
            
        except Exception as e:
            errors.append({"id": candidate_id, "error": str(e)})
    
    logger.info(f"Bulk approval: {approved_count} classifications approved by {current_user.email}")
    
    return {
        "success": True,
        "approved_count": approved_count,
        "total_requested": len(request.candidate_ids),
        "errors": errors if errors else None
    }


class CorrectClassificationRequest(PydanticBaseModel):
    industry: Optional[str] = None
    functional_area: Optional[str] = None
    seniority: Optional[str] = None


@api_router.post("/atlas/classifications/correct/{candidate_id}")
async def correct_classification(
    candidate_id: str,
    corrections: CorrectClassificationRequest,
    current_user: User = Depends(get_current_user)
):
    """Correct and approve a classification with user-provided values.
    Works for both classified and unclassified candidates.
    """
    candidate_doc = await db.candidates.find_one(
        {"id": candidate_id, "is_deleted": {"$ne": True}},
        {"_id": 0, "ai_classification": 1, "industry": 1, "functional_area": 1, "seniority": 1}
    )
    
    if not candidate_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato no encontrado"
        )
    
    # Handle both null and existing ai_classification
    ai_class = candidate_doc.get("ai_classification") or {}
    now = datetime.now(timezone.utc).isoformat()
    
    # Determine final values (correction > AI suggestion > existing value)
    final_industry = corrections.industry or ai_class.get("industry") or candidate_doc.get("industry")
    final_area = corrections.functional_area or ai_class.get("functional_area") or candidate_doc.get("functional_area")
    final_seniority = corrections.seniority or ai_class.get("seniority") or candidate_doc.get("seniority")
    
    # Build the complete ai_classification object (avoids dot-notation on null)
    new_ai_classification = {
        "industry": final_industry,
        "functional_area": final_area,
        "seniority": final_seniority,
        "suggested_tags": ai_class.get("suggested_tags", []),
        "confidence_score": ai_class.get("confidence_score", 1.0),  # Manual correction = full confidence
        "approved_by_recruiter": True,
        "approved_at": now,
        "approved_by": current_user.id,
        "was_corrected": True,
        "corrections": {
            "industry": corrections.industry,
            "functional_area": corrections.functional_area,
            "seniority": corrections.seniority
        },
        "classified_at": ai_class.get("classified_at", now),
        "source": ai_class.get("source", "manual_correction")
    }
    
    # Update candidate with complete object replacement (no dot-notation issues)
    await db.candidates.update_one(
        {"id": candidate_id},
        {"$set": {
            "industry": final_industry,
            "functional_area": final_area,
            "seniority": final_seniority,
            "ai_classification": new_ai_classification,
            "updated_at": now
        }}
    )
    
    logger.info(f"Classification corrected for {candidate_id} by {current_user.email}")
    
    return {
        "success": True,
        "message": "Clasificación corregida y aprobada",
        "applied_classification": {
            "industry": final_industry,
            "functional_area": final_area,
            "seniority": final_seniority
        }
    }


# ============= DASHBOARD & ANALYTICS ROUTES =============

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    """Get dashboard statistics including job metrics"""
    
    total_candidates = await db.candidates.count_documents({"is_deleted": {"$ne": True}})
    
    # Candidates this month
    from datetime import timedelta
    month_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    new_this_month = await db.candidates.count_documents({
        "created_at": {"$gte": month_ago},
        "is_deleted": {"$ne": True}
    })
    
    # By status
    by_status = {}
    for status in CandidateStatus:
        count = await db.candidates.count_documents({"status": status.value, "is_deleted": {"$ne": True}})
        by_status[status.value] = count
    
    # By industry (top 5)
    industry_pipeline = [
        {"$match": {"industry": {"$ne": None}, "is_deleted": {"$ne": True}}},
        {"$group": {"_id": "$industry", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    industry_results = await db.candidates.aggregate(industry_pipeline).to_list(5)
    by_industry = {item['_id']: item['count'] for item in industry_results}
    
    # By functional area (top 5)
    area_pipeline = [
        {"$match": {"functional_area": {"$ne": None}, "is_deleted": {"$ne": True}}},
        {"$group": {"_id": "$functional_area", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    area_results = await db.candidates.aggregate(area_pipeline).to_list(5)
    by_functional_area = {item['_id']: item['count'] for item in area_results}
    
    # By seniority
    by_seniority = {}
    for seniority in SeniorityLevel:
        count = await db.candidates.count_documents({"seniority": seniority.value, "is_deleted": {"$ne": True}})
        by_seniority[seniority.value] = count
    
    # ========== JOB METRICS ==========
    # Total active jobs
    total_jobs = await db.jobs.count_documents({"status": "open"})
    
    # Get all open jobs with their shortlist counts
    jobs_cursor = db.jobs.find(
        {"status": "open"},
        {"_id": 0, "id": 1, "title": 1, "company_name": 1, "shortlist": 1, "created_at": 1}
    )
    jobs_list = await jobs_cursor.to_list(100)
    
    # Calculate job metrics
    jobs_without_candidates = []
    jobs_low_match = []  # < 3 candidates
    jobs_high_volume = []  # > 10 candidates
    top_jobs = []
    
    for job in jobs_list:
        shortlist_count = len(job.get('shortlist', []))
        job_info = {
            "id": job.get('id'),
            "title": job.get('title'),
            "company": job.get('company_name'),
            "candidates": shortlist_count
        }
        
        if shortlist_count == 0:
            jobs_without_candidates.append(job_info)
        elif shortlist_count < 3:
            jobs_low_match.append(job_info)
        elif shortlist_count > 10:
            jobs_high_volume.append(job_info)
        
        top_jobs.append(job_info)
    
    # Sort top jobs by candidate count
    top_jobs.sort(key=lambda x: x['candidates'], reverse=True)
    
    job_metrics = {
        "total_active_jobs": total_jobs,
        "jobs_without_candidates": {
            "count": len(jobs_without_candidates),
            "jobs": jobs_without_candidates[:5]  # Top 5
        },
        "jobs_low_match": {
            "count": len(jobs_low_match),
            "jobs": jobs_low_match[:5]
        },
        "jobs_high_volume": {
            "count": len(jobs_high_volume),
            "jobs": jobs_high_volume[:5]
        },
        "top_jobs_with_candidates": top_jobs[:5]
    }
    
    return {
        "total_candidates": total_candidates,
        "new_this_month": new_this_month,
        "by_status": by_status,
        "by_industry": by_industry,
        "by_functional_area": by_functional_area,
        "by_seniority": by_seniority,
        "job_metrics": job_metrics
    }


@api_router.get("/dashboard/recent-activity")
async def get_recent_activity(
    limit: int = 10,
    current_user: User = Depends(get_current_user)
):
    """Get recent activity logs"""
    logs = await db.activity_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    
    for log in logs:
        if isinstance(log.get('timestamp'), str):
            log['timestamp'] = datetime.fromisoformat(log['timestamp'])
    
    return logs



# ============= HYBRID SEARCH ROUTES =============

@api_router.post("/search/hybrid")
async def hybrid_search(
    query: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    industry: Optional[str] = Query(None),
    functional_area: Optional[str] = Query(None),
    seniority: Optional[str] = Query(None),
    min_experience: Optional[int] = Query(None),
    max_experience: Optional[int] = Query(None),
    city: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    use_semantic: bool = Query(True),
    limit: int = Query(50),
    current_user: User = Depends(get_current_user)
):
    """Hybrid search with filters, keyword, and semantic search"""
    filters = {}
    if status:
        filters['status'] = status
    if industry:
        filters['industry'] = industry
    if functional_area:
        filters['functional_area'] = functional_area
    if seniority:
        filters['seniority'] = seniority
    if min_experience:
        filters['min_experience'] = min_experience
    if max_experience:
        filters['max_experience'] = max_experience
    if city:
        filters['city'] = city
    if state:
        filters['state'] = state
    
    results = await hybrid_search_service.search(
        query=query,
        filters=filters,
        use_semantic=use_semantic,
        limit=limit
    )
    
    # Parse dates for results
    for candidate in results:
        if isinstance(candidate.get('created_at'), str):
            candidate['created_at'] = datetime.fromisoformat(candidate['created_at'])
        if isinstance(candidate.get('updated_at'), str):
            candidate['updated_at'] = datetime.fromisoformat(candidate['updated_at'])
    
    # Agregar metadata de búsqueda
    return {
        "results": results,
        "total": len(results),
        "search_metadata": {
            "query": query,
            "use_semantic": use_semantic,
            "semantic_search_active": use_semantic and embedding_service.enabled,
            "filters_applied": bool(filters),
            "embedding_service_enabled": embedding_service.enabled
        }
    }


@api_router.post("/search/save")
async def save_search(
    name: str = Form(...),
    query: Optional[str] = Form(None),
    filters: str = Form("{}"),
    use_semantic: bool = Form(False),
    current_user: User = Depends(get_current_user)
):
    """Save a search query for later use"""
    import json
    
    search_id = str(uuid.uuid4())
    filters_dict = json.loads(filters)
    
    saved_search = {
        "id": search_id,
        "user_id": current_user.id,
        "name": name,
        "query": query,
        "filters": filters_dict,
        "use_semantic": use_semantic,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.saved_searches.insert_one(saved_search)
    
    return {"message": "Búsqueda guardada", "search_id": search_id}


@api_router.get("/search/saved")
async def get_saved_searches(current_user: User = Depends(get_current_user)):
    """Get user's saved searches"""
    searches = await db.saved_searches.find(
        {"user_id": current_user.id},
        {"_id": 0}
    ).to_list(100)
    
    for search in searches:
        if isinstance(search.get('created_at'), str):
            search['created_at'] = datetime.fromisoformat(search['created_at'])
    
    return searches


# ============= DUPLICATE MANAGEMENT ROUTES =============

@api_router.get("/candidates/{candidate_id}/duplicates")
async def get_candidate_duplicates(
    candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get duplicate suggestions for a candidate.
    Incluye sugerencias pendientes y búsqueda activa de posibles duplicados.
    """
    # Obtener sugerencias guardadas
    saved_suggestions = await db.duplicate_suggestions.find(
        {"new_candidate_id": candidate_id, "status": "pending"},
        {"_id": 0}
    ).to_list(10)
    
    # Buscar duplicados activamente
    candidate = await db.candidates.find_one(
        {"id": candidate_id},
        {"_id": 0, "email": 1, "phone": 1, "linkedin_url": 1, "full_name": 1, "previous_companies": 1}
    )
    
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato no encontrado")
    
    active_duplicates = await duplicate_detector.detect_duplicates(candidate)
    
    # Filtrar auto-match (no comparar consigo mismo)
    active_duplicates = [d for d in active_duplicates if d.get('candidate_id') != candidate_id]
    
    # Categorizar por nivel de confianza
    high_confidence = [d for d in active_duplicates if d['confidence'] >= 0.9]
    medium_confidence = [d for d in active_duplicates if 0.7 <= d['confidence'] < 0.9]
    low_confidence = [d for d in active_duplicates if d['confidence'] < 0.7]
    
    return {
        "saved_suggestions": saved_suggestions,
        "active_duplicates": {
            "high_confidence": high_confidence,
            "medium_confidence": medium_confidence,
            "low_confidence": low_confidence,
            "total": len(active_duplicates)
        }
    }


@api_router.post("/candidates/{candidate_id}/dismiss-duplicate/{suggestion_id}")
async def dismiss_duplicate(
    candidate_id: str,
    suggestion_id: str,
    current_user: User = Depends(get_current_user)
):
    """Dismiss a duplicate suggestion"""
    await db.duplicate_suggestions.update_one(
        {"id": suggestion_id},
        {
            "$set": {
                "status": "dismissed",
                "reviewed_by": current_user.id,
                "reviewed_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    return {"message": "Duplicado descartado"}


class MergeRequest(PydanticBaseModel):
    primary_candidate_id: str  # El que se va a mantener
    secondary_candidate_id: str  # El que se va a fusionar
    merge_experience: bool = True  # Combinar experiencia laboral
    merge_education: bool = True  # Combinar educación
    merge_skills: bool = True  # Combinar skills
    merge_notes: bool = True  # Combinar notas
    keep_all_cvs: bool = True  # Conservar CVs de ambos como versiones
    use_secondary_contact: bool = False  # Usar info de contacto del secundario


@api_router.post("/candidates/merge")
async def merge_candidates(
    request: MergeRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Merge de candidatos duplicados (Admin y Reclutadores con permiso).
    Mantiene el primary, transfiere datos del secondary, y marca el secondary como eliminado.
    """
    # Verificar permisos
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.RECRUITER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso para fusionar candidatos")
    
    try:
        merge_options = {
            "merge_experience": request.merge_experience,
            "merge_education": request.merge_education,
            "merge_skills": request.merge_skills,
            "merge_notes": request.merge_notes,
            "keep_all_cvs": request.keep_all_cvs,
            "use_secondary_contact": request.use_secondary_contact
        }
        
        result = await candidate_merger.merge_candidates(
            primary_id=request.primary_candidate_id,
            secondary_id=request.secondary_candidate_id,
            merge_options=merge_options,
            merged_by=current_user.id
        )
        
        logger.info(f"Candidates merged: {request.secondary_candidate_id} -> {request.primary_candidate_id} by {current_user.email}")
        
        return {
            "success": True,
            "message": "Candidatos fusionados exitosamente",
            "primary_candidate_id": request.primary_candidate_id,
            "secondary_candidate_id": request.secondary_candidate_id,
            "changes": result.get("changes", []),
            "audit_id": result.get("audit_id"),
            "merged_by": current_user.name
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error merging candidates: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al fusionar: {str(e)}")


class MergeMultipleRequest(PydanticBaseModel):
    primary_candidate_id: str  # El que se va a mantener
    secondary_candidate_ids: List[str]  # Los que se van a fusionar
    merge_experience: bool = True
    merge_education: bool = True
    merge_skills: bool = True
    merge_notes: bool = True
    keep_all_cvs: bool = True
    use_secondary_contact: bool = False


@api_router.post("/candidates/merge-multiple")
async def merge_multiple_candidates(
    request: MergeMultipleRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Merge multiple candidate records into a single primary.
    Supports groups of 3+ duplicates in a single operation.
    """
    # Verificar permisos
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.RECRUITER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin permiso para fusionar candidatos")
    
    # Validación
    if not request.secondary_candidate_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe especificar al menos un candidato secundario")
    
    if request.primary_candidate_id in request.secondary_candidate_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El candidato principal no puede estar en la lista de secundarios")
    
    try:
        merge_options = {
            "merge_experience": request.merge_experience,
            "merge_education": request.merge_education,
            "merge_skills": request.merge_skills,
            "merge_notes": request.merge_notes,
            "keep_all_cvs": request.keep_all_cvs,
            "use_secondary_contact": request.use_secondary_contact
        }
        
        result = await candidate_merger.merge_multiple_candidates(
            primary_id=request.primary_candidate_id,
            secondary_ids=request.secondary_candidate_ids,
            merge_options=merge_options,
            merged_by=current_user.id
        )
        
        logger.info(f"Multiple candidates merged: {request.secondary_candidate_ids} -> {request.primary_candidate_id} by {current_user.email}")
        
        return {
            "success": True,
            "message": f"{result['total_merged']} candidatos fusionados exitosamente",
            "primary_candidate_id": request.primary_candidate_id,
            "secondary_candidate_ids": request.secondary_candidate_ids,
            "total_merged": result["total_merged"],
            "changes": result.get("changes", []),
            "audit_ids": result.get("audit_ids", []),
            "merged_by": current_user.name
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error merging multiple candidates: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al fusionar: {str(e)}")


@api_router.get("/duplicates/review")
async def get_all_duplicates_for_review(
    current_user: User = Depends(get_current_user)
):
    """
    Get all detected duplicate groups for manual review.
    Returns groups of candidates that appear to be duplicates.
    """
    try:
        duplicate_groups = await duplicate_detector_v2.get_all_duplicate_groups()
        
        # Enrich with additional info
        for group in duplicate_groups:
            for candidate in group['candidates']:
                # Add resume info
                full_candidate = await db.candidates.find_one(
                    {"id": candidate['id']},
                    {"_id": 0, "resume_files": 1, "status": 1, "seniority": 1}
                )
                if full_candidate:
                    candidate['has_resume'] = bool(full_candidate.get('resume_files'))
                    candidate['status'] = full_candidate.get('status', 'nuevo')
                    candidate['seniority'] = full_candidate.get('seniority')
        
        return {
            "total_groups": len(duplicate_groups),
            "duplicate_groups": duplicate_groups
        }
    except Exception as e:
        logger.error(f"Error getting duplicates for review: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/duplicates/stats")
async def get_duplicate_stats(
    current_user: User = Depends(get_current_user)
):
    """Get statistics about duplicates in the system"""
    try:
        duplicate_groups = await duplicate_detector_v2.get_all_duplicate_groups()
        
        total_duplicates = sum(g['count'] for g in duplicate_groups)
        by_type = {}
        for g in duplicate_groups:
            match_type = g['match_type']
            by_type[match_type] = by_type.get(match_type, 0) + g['count']
        
        # Get pending suggestions
        pending_suggestions = await db.duplicate_suggestions.count_documents({"status": "pending"})
        
        # Get merge history count
        merge_count = await db.merge_audit_log.count_documents({})
        
        return {
            "total_duplicate_groups": len(duplicate_groups),
            "total_duplicate_records": total_duplicates,
            "by_match_type": by_type,
            "pending_suggestions": pending_suggestions,
            "total_merges_performed": merge_count
        }
    except Exception as e:
        logger.error(f"Error getting duplicate stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/duplicates/orphan-records")
async def get_orphan_records(
    current_user: User = Depends(get_current_user)
):
    """
    Identify orphan/incomplete records from failed uploads.
    Orphan criteria:
    - No email AND no full_name (or generic name like "Candidato - filename.pdf")
    - No resume_files or empty resume_files
    - Created more than 1 hour ago (to avoid catching in-progress uploads)
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admins pueden ver registros huérfanos")
    
    try:
        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        
        # Find candidates that appear to be incomplete/orphan
        orphan_query = {
            "is_deleted": {"$ne": True},
            "created_at": {"$lt": one_hour_ago},
            "$or": [
                # No email AND (no name OR generic name)
                {
                    "email": {"$in": [None, ""]},
                    "$or": [
                        {"full_name": {"$in": [None, ""]}},
                        {"full_name": {"$regex": "^Candidato - ", "$options": "i"}}
                    ]
                },
                # No resume files
                {
                    "resume_files": {"$in": [None, []]}
                },
                # Very incomplete: no title, no company, no skills
                {
                    "current_title": {"$in": [None, ""]},
                    "current_company": {"$in": [None, ""]},
                    "skills": {"$in": [None, []]},
                    "previous_companies": {"$in": [None, []]}
                }
            ]
        }
        
        orphans = await db.candidates.find(
            orphan_query,
            {"_id": 0, "id": 1, "full_name": 1, "email": 1, "current_title": 1, 
             "created_at": 1, "source": 1, "resume_files": 1, "skills": 1}
        ).sort("created_at", -1).limit(100).to_list(100)
        
        # Categorize orphans
        categorized = {
            "no_contact_info": [],
            "no_resume": [],
            "incomplete_profile": [],
            "generic_name": []
        }
        
        for o in orphans:
            has_email = bool(o.get("email"))
            has_resume = bool(o.get("resume_files"))
            has_skills = bool(o.get("skills"))
            is_generic_name = o.get("full_name", "").startswith("Candidato - ")
            
            if is_generic_name:
                categorized["generic_name"].append(o)
            elif not has_email:
                categorized["no_contact_info"].append(o)
            elif not has_resume:
                categorized["no_resume"].append(o)
            elif not has_skills:
                categorized["incomplete_profile"].append(o)
        
        return {
            "total_orphans": len(orphans),
            "categorized": categorized,
            "by_category": {
                "no_contact_info": len(categorized["no_contact_info"]),
                "no_resume": len(categorized["no_resume"]),
                "incomplete_profile": len(categorized["incomplete_profile"]),
                "generic_name": len(categorized["generic_name"])
            },
            "orphans": orphans
        }
    except Exception as e:
        logger.error(f"Error getting orphan records: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/duplicates/cleanup-orphans")
async def cleanup_orphan_records(
    candidate_ids: List[str],
    current_user: User = Depends(get_current_user)
):
    """
    Soft delete orphan/incomplete records.
    Only admins can perform this action.
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo admins pueden eliminar registros huérfanos")
    
    if not candidate_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Debe especificar IDs de candidatos")
    
    try:
        deleted_count = 0
        errors = []
        
        for cid in candidate_ids:
            try:
                result = await db.candidates.update_one(
                    {"id": cid, "is_deleted": {"$ne": True}},
                    {"$set": {
                        "is_deleted": True,
                        "deleted_at": datetime.now(timezone.utc).isoformat(),
                        "deletion_type": "orphan_cleanup",
                        "deleted_by": current_user.id
                    }}
                )
                if result.modified_count > 0:
                    deleted_count += 1
            except Exception as e:
                errors.append({"id": cid, "error": str(e)})
        
        # Create audit log
        await db.cleanup_audit_log.insert_one({
            "id": str(uuid.uuid4()),
            "action": "orphan_cleanup",
            "candidate_ids": candidate_ids,
            "deleted_count": deleted_count,
            "errors": errors,
            "performed_by": current_user.id,
            "performed_at": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"Orphan cleanup: {deleted_count} records deleted by {current_user.email}")
        
        return {
            "success": True,
            "message": f"{deleted_count} registros eliminados",
            "deleted_count": deleted_count,
            "errors": errors if errors else None
        }
    except Exception as e:
        logger.error(f"Error cleaning up orphans: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/duplicates/merge-history")
async def get_merge_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get history of merge operations"""
    merges = await db.merge_audit_log.find(
        {},
        {"_id": 0}
    ).sort("merged_at", -1).limit(limit).to_list(limit)
    
    # Enrich with user names
    for merge in merges:
        user = await db.users.find_one({"id": merge.get("merged_by")}, {"_id": 0, "name": 1, "email": 1})
        if user:
            merge["merged_by_name"] = user.get("name")
            merge["merged_by_email"] = user.get("email")
    
    return {"merges": merges}


@api_router.get("/candidates/{candidate_id}/merge-preview/{other_candidate_id}")
async def get_merge_preview(
    candidate_id: str,
    other_candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get a side-by-side preview of two candidates for merge decision.
    """
    candidate1 = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    candidate2 = await db.candidates.find_one({"id": other_candidate_id}, {"_id": 0})
    
    if not candidate1 or not candidate2:
        raise HTTPException(status_code=404, detail="Uno o ambos candidatos no encontrados")
    
    # Calculate completeness scores
    def calc_completeness(c):
        score = 0
        if c.get('full_name'): score += 10
        if c.get('email'): score += 10
        if c.get('phone'): score += 5
        if c.get('current_title'): score += 10
        if c.get('current_company'): score += 10
        if c.get('years_experience'): score += 10
        if c.get('previous_companies'): score += len(c['previous_companies']) * 5
        if c.get('skills'): score += min(len(c['skills']), 10) * 2
        if c.get('resume_files'): score += 15
        if c.get('notes'): score += 5
        return score
    
    # Find differences
    differences = []
    
    # Compare experiences
    exp1 = {(e.get('company_name', '').lower(), e.get('title', '').lower()) 
            for e in (candidate1.get('previous_companies') or [])}
    exp2 = {(e.get('company_name', '').lower(), e.get('title', '').lower()) 
            for e in (candidate2.get('previous_companies') or [])}
    
    only_in_1 = exp1 - exp2
    only_in_2 = exp2 - exp1
    
    if only_in_1:
        differences.append(f"Experiencias solo en candidato 1: {len(only_in_1)}")
    if only_in_2:
        differences.append(f"Experiencias solo en candidato 2: {len(only_in_2)}")
    
    # Compare skills
    skills1 = set(candidate1.get('skills') or [])
    skills2 = set(candidate2.get('skills') or [])
    skills_diff = skills1.symmetric_difference(skills2)
    if skills_diff:
        differences.append(f"Skills diferentes: {len(skills_diff)}")
    
    return {
        "candidate_1": {
            "id": candidate1['id'],
            "full_name": candidate1.get('full_name'),
            "email": candidate1.get('email'),
            "phone": candidate1.get('phone'),
            "current_title": candidate1.get('current_title'),
            "current_company": candidate1.get('current_company'),
            "years_experience": candidate1.get('years_experience'),
            "industry": candidate1.get('industry'),
            "seniority": candidate1.get('seniority'),
            "experience_count": len(candidate1.get('previous_companies') or []),
            "skills_count": len(candidate1.get('skills') or []),
            "has_resume": bool(candidate1.get('resume_files')),
            "created_at": candidate1.get('created_at'),
            "completeness_score": calc_completeness(candidate1)
        },
        "candidate_2": {
            "id": candidate2['id'],
            "full_name": candidate2.get('full_name'),
            "email": candidate2.get('email'),
            "phone": candidate2.get('phone'),
            "current_title": candidate2.get('current_title'),
            "current_company": candidate2.get('current_company'),
            "years_experience": candidate2.get('years_experience'),
            "industry": candidate2.get('industry'),
            "seniority": candidate2.get('seniority'),
            "experience_count": len(candidate2.get('previous_companies') or []),
            "skills_count": len(candidate2.get('skills') or []),
            "has_resume": bool(candidate2.get('resume_files')),
            "created_at": candidate2.get('created_at'),
            "completeness_score": calc_completeness(candidate2)
        },
        "differences": differences,
        "recommendation": "candidate_1" if calc_completeness(candidate1) >= calc_completeness(candidate2) else "candidate_2"
    }


@api_router.post("/candidates/{candidate_id}/update-cv")
async def update_candidate_cv(
    candidate_id: str,
    file: UploadFile = File(...),
    notes: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Update CV for an existing candidate.
    Creates a new CV version with parsed snapshot for comparison.
    """
    user = await get_current_user(credentials)
    
    # Verify candidate exists
    candidate = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato no encontrado")
    
    # Verificar permisos de edición
    await verify_candidate_edit_permission(candidate_id, user)
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="Archivo sin nombre")
    
    file_ext = file.filename.split('.')[-1].lower()
    if file_ext not in ['pdf', 'docx']:
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF o DOCX")
    
    try:
        file_data = await file.read()
        file_size = len(file_data)
        
        # Upload new CV to storage
        storage_result = storage_service.upload_resume(
            file_data, candidate_id, file.filename, file.content_type
        )
        
        # Extract and parse new CV
        parsed_snapshot = None
        try:
            extracted_text = DocumentParser.extract_text_from_bytes(file_data, file.content_type)
            if extracted_text and len(extracted_text.strip()) > 50:
                from atlas_service import atlas_service
                parsed_data = await atlas_service.parse_resume(extracted_text)
                
                # Build snapshot with key fields for comparison
                parsed_snapshot = {
                    "full_name": parsed_data.get("full_name"),
                    "current_title": parsed_data.get("current_title"),
                    "current_company": parsed_data.get("current_company"),
                    "years_experience": parsed_data.get("years_experience"),
                    "industry": parsed_data.get("industry"),
                    "functional_area": parsed_data.get("functional_area"),
                    "seniority": parsed_data.get("seniority"),
                    "skills": parsed_data.get("skills", []),
                    "previous_companies": parsed_data.get("previous_companies", []),
                    "education": parsed_data.get("education", []),
                    "languages": parsed_data.get("languages", []),
                    "email": parsed_data.get("email"),
                    "phone": parsed_data.get("phone"),
                    "parsed_at": datetime.now(timezone.utc).isoformat()
                }
        except Exception as e:
            logger.warning(f"Could not parse updated CV for {candidate_id}: {str(e)}")
        
        # Create new version using service
        cv_version = await cv_version_service.create_version(
            candidate_id=candidate_id,
            file_key=storage_result['storage_path'],
            file_name=file.filename,
            file_type=file.content_type,
            file_size=file_size,
            uploaded_by=user.id,
            uploaded_by_name=user.name,
            upload_source="update",
            parsed_snapshot=parsed_snapshot,
            notes=notes
        )
        
        # Update candidate's main resume info
        resume_file = {
            "file_name": file.filename,
            "file_path": storage_result['storage_path'],
            "file_type": file.content_type,
            "upload_date": datetime.now(timezone.utc).isoformat()
        }
        
        # Also update candidate profile if parsed data is available
        update_data = {
            "resume_file_key": storage_result['storage_path'],
            "resume_file_name": file.filename,
            "resume_file_type": file.content_type,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_cv_update": datetime.now(timezone.utc).isoformat()
        }
        
        # Optionally update profile fields from new CV (if parsed)
        if parsed_snapshot:
            # Update fields that might have changed
            if parsed_snapshot.get("current_title"):
                update_data["current_title"] = parsed_snapshot["current_title"]
            if parsed_snapshot.get("current_company"):
                update_data["current_company"] = parsed_snapshot["current_company"]
            if parsed_snapshot.get("years_experience"):
                update_data["years_experience"] = parsed_snapshot["years_experience"]
            if parsed_snapshot.get("skills"):
                # Merge skills (keep existing + add new)
                existing_skills = set(candidate.get("skills") or [])
                new_skills = set(parsed_snapshot.get("skills") or [])
                update_data["skills"] = list(existing_skills | new_skills)
        
        await db.candidates.update_one(
            {"id": candidate_id},
            {
                "$set": update_data,
                "$push": {"resume_files": resume_file}
            }
        )
        
        logger.info(f"CV updated for candidate {candidate_id}: version {cv_version['version']}")
        
        return {
            "success": True,
            "message": f"CV actualizado exitosamente (versión {cv_version['version']})",
            "candidate_id": candidate_id,
            "version": cv_version['version'],
            "file_name": file.filename,
            "has_parsed_snapshot": parsed_snapshot is not None
        }
        
    except Exception as e:
        logger.error(f"Error updating CV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error actualizando CV: {str(e)}")


# ============= CV VERSION ENDPOINTS =============

@api_router.get("/candidates/{candidate_id}/cv-versions")
async def get_candidate_cv_versions(
    candidate_id: str,
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user)
):
    """
    Get all CV versions for a candidate.
    Returns list sorted by version descending (newest first).
    """
    # Verify candidate exists
    candidate = await db.candidates.find_one({"id": candidate_id}, {"_id": 0, "id": 1, "full_name": 1})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato no encontrado")
    
    versions = await cv_version_service.get_versions(candidate_id, include_inactive)
    
    # Format response (without full snapshot)
    formatted_versions = []
    for v in versions:
        formatted_versions.append({
            "id": v.get("id"),
            "version": v.get("version"),
            "file_name": v.get("file_name"),
            "file_type": v.get("file_type"),
            "file_size": v.get("file_size"),
            "uploaded_at": v.get("uploaded_at"),
            "uploaded_by": v.get("uploaded_by"),
            "uploaded_by_name": v.get("uploaded_by_name"),
            "upload_source": v.get("upload_source"),
            "is_current": v.get("is_current"),
            "is_active": v.get("is_active"),
            "notes": v.get("notes"),
            "has_snapshot": v.get("parsed_snapshot") is not None
        })
    
    return {
        "candidate_id": candidate_id,
        "candidate_name": candidate.get("full_name"),
        "total_versions": len(formatted_versions),
        "versions": formatted_versions
    }


@api_router.get("/candidates/{candidate_id}/cv-versions/{version}")
async def get_candidate_cv_version(
    candidate_id: str,
    version: int,
    include_snapshot: bool = False,
    current_user: User = Depends(get_current_user)
):
    """Get a specific CV version with optional parsed snapshot"""
    version_doc = await cv_version_service.get_version(candidate_id, version)
    
    if not version_doc:
        raise HTTPException(status_code=404, detail="Versión no encontrada")
    
    response = {
        "id": version_doc.get("id"),
        "candidate_id": version_doc.get("candidate_id"),
        "version": version_doc.get("version"),
        "file_name": version_doc.get("file_name"),
        "file_type": version_doc.get("file_type"),
        "file_size": version_doc.get("file_size"),
        "uploaded_at": version_doc.get("uploaded_at"),
        "uploaded_by": version_doc.get("uploaded_by"),
        "uploaded_by_name": version_doc.get("uploaded_by_name"),
        "upload_source": version_doc.get("upload_source"),
        "is_current": version_doc.get("is_current"),
        "notes": version_doc.get("notes")
    }
    
    if include_snapshot:
        response["parsed_snapshot"] = version_doc.get("parsed_snapshot")
    
    return response


@api_router.get("/candidates/{candidate_id}/cv-versions/{version}/download")
async def download_cv_version(
    candidate_id: str,
    version: int,
    current_user: User = Depends(get_current_user)
):
    """Download a specific version of a candidate's CV"""
    version_doc = await cv_version_service.get_version(candidate_id, version)
    
    if not version_doc:
        raise HTTPException(status_code=404, detail="Versión no encontrada")
    
    file_key = version_doc.get("file_key")
    if not file_key:
        raise HTTPException(status_code=404, detail="Archivo no disponible")
    
    try:
        file_data, storage_content_type = storage_service.get_object(file_key)
        
        if not file_data:
            raise HTTPException(status_code=404, detail="Archivo no encontrado en almacenamiento")
        
        file_name = version_doc.get("file_name", f"cv_v{version}.pdf")
        content_type = version_doc.get("file_type") or storage_content_type or "application/pdf"
        
        return Response(
            content=file_data,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading CV version: {str(e)}")
        raise HTTPException(status_code=500, detail="Error descargando archivo")


@api_router.get("/candidates/{candidate_id}/cv-versions/{version1}/compare/{version2}")
async def compare_cv_versions(
    candidate_id: str,
    version1: int,
    version2: int,
    current_user: User = Depends(get_current_user)
):
    """
    Compare two CV versions and return differences.
    Useful for detecting changes in candidate's profile over time.
    """
    comparison = await cv_version_service.compare_versions(candidate_id, version1, version2)
    
    if comparison.get("error"):
        raise HTTPException(status_code=404, detail=comparison["error"])
    
    return comparison


@api_router.post("/admin/cv-versions/migrate")
async def migrate_existing_cvs(
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.ADMIN]))
):
    """
    Migrate existing CVs to the cv_versions collection.
    Should be run once after deploying the versioning feature.
    """
    result = await cv_version_service.migrate_existing_cvs()
    return {
        "success": True,
        "message": "Migración completada",
        **result
    }


@api_router.get("/admin/cv-versions/stats")
async def get_cv_version_stats(
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.ADMIN]))
):
    """Get statistics about CV versions in the system"""
    total_versions = await db.cv_versions.count_documents({})
    candidates_with_versions = len(await db.cv_versions.distinct("candidate_id"))
    
    # Candidates with multiple versions
    pipeline = [
        {"$group": {"_id": "$candidate_id", "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}}
    ]
    multi_version_candidates = len(await db.cv_versions.aggregate(pipeline).to_list(10000))
    
    # Versions by source
    source_pipeline = [
        {"$group": {"_id": "$upload_source", "count": {"$sum": 1}}}
    ]
    by_source = {r["_id"]: r["count"] for r in await db.cv_versions.aggregate(source_pipeline).to_list(100)}
    
    return {
        "total_versions": total_versions,
        "candidates_with_versions": candidates_with_versions,
        "candidates_with_multiple_versions": multi_version_candidates,
        "versions_by_source": by_source
    }


# ============= ADMIN TAXONOMY CRUD ROUTES =============

@api_router.post("/admin/industries")
async def create_industry(
    industry_data: IndustryCreate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN]))
):
    """Create new industry (Super Admin only)"""
    # Verificar que la key no exista ya
    existing = await db.industries.find_one({"key": industry_data.key})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una industria con la key '{industry_data.key}'"
        )
    
    industry_id = str(uuid.uuid4())
    
    industry = {
        "id": industry_id,
        "key": industry_data.key,
        "name_es": industry_data.name_es,
        "name_en": industry_data.name_en,
        "description": industry_data.description,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.industries.insert_one(industry)
    
    return {"message": "Industria creada", "industry_id": industry_id, "key": industry_data.key}


@api_router.put("/admin/industries/{industry_id}")
async def update_industry(
    industry_id: str,
    industry_data: IndustryCreate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN]))
):
    """Update industry (Super Admin only)"""
    result = await db.industries.update_one(
        {"id": industry_id},
        {
            "$set": {
                "key": industry_data.key,
                "name_es": industry_data.name_es,
                "name_en": industry_data.name_en,
                "description": industry_data.description
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Industria no encontrada"
        )
    
    return {"message": "Industria actualizada"}


@api_router.delete("/admin/industries/{industry_id}")
async def delete_industry(
    industry_id: str,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN]))
):
    """Delete industry (Super Admin only)"""
    # Check if any candidates use this industry
    count = await db.candidates.count_documents({"industry": industry_id})
    
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar. {count} candidatos usan esta industria"
        )
    
    result = await db.industries.delete_one({"id": industry_id})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Industria no encontrada"
        )
    
    return {"message": "Industria eliminada"}


@api_router.post("/admin/functional-areas")
async def create_functional_area(
    area_data: FunctionalAreaCreate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN]))
):
    """Create new functional area (Super Admin only)"""
    # Verificar que la key no exista ya
    existing = await db.functional_areas.find_one({"key": area_data.key})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un área funcional con la key '{area_data.key}'"
        )
    
    area_id = str(uuid.uuid4())
    
    area = {
        "id": area_id,
        "key": area_data.key,
        "name_es": area_data.name_es,
        "name_en": area_data.name_en,
        "description": area_data.description,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.functional_areas.insert_one(area)
    
    return {"message": "Área funcional creada", "area_id": area_id, "key": area_data.key}


@api_router.put("/admin/functional-areas/{area_id}")
async def update_functional_area(
    area_id: str,
    area_data: FunctionalAreaCreate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN]))
):
    """Update functional area (Super Admin only)"""
    result = await db.functional_areas.update_one(
        {"id": area_id},
        {
            "$set": {
                "key": area_data.key,
                "name_es": area_data.name_es,
                "name_en": area_data.name_en,
                "description": area_data.description
            }
        }
    )
    
    if result.matched_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Área funcional no encontrada"
        )
    
    return {"message": "Área funcional actualizada"}


@api_router.delete("/admin/functional-areas/{area_id}")



# ============= VALIDATION & QUALITY TRACKING ROUTES =============

@api_router.post("/validation/record")
async def create_validation_record(
    candidate_id: str = Form(...),
    expected_industry: Optional[str] = Form(None),
    expected_functional_area: Optional[str] = Form(None),
    expected_seniority: Optional[str] = Form(None),
    industry_correct: Optional[bool] = Form(None),
    functional_area_correct: Optional[bool] = Form(None),
    seniority_correct: Optional[bool] = Form(None),
    parsing_quality_score: Optional[int] = Form(None),
    parsing_notes: Optional[str] = Form(None),
    search_query: Optional[str] = Form(None),
    search_relevant: Optional[bool] = Form(None),
    search_notes: Optional[str] = Form(None),
    comments: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Create validation record for quality tracking"""
    
    # Get candidate info
    candidate = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidato no encontrado")
    
    record_id = str(uuid.uuid4())
    
    validation_record = {
        "id": record_id,
        "candidate_id": candidate_id,
        "candidate_name": candidate.get("full_name"),
        "expected_industry": expected_industry,
        "expected_functional_area": expected_functional_area,
        "expected_seniority": expected_seniority,
        "atlas_industry": candidate.get("industry"),
        "atlas_functional_area": candidate.get("functional_area"),
        "atlas_seniority": candidate.get("seniority"),
        "industry_correct": industry_correct,
        "functional_area_correct": functional_area_correct,
        "seniority_correct": seniority_correct,
        "parsing_quality_score": parsing_quality_score,
        "parsing_notes": parsing_notes,
        "search_query": search_query,
        "search_relevant": search_relevant,
        "search_notes": search_notes,
        "reviewer_name": current_user.name,
        "comments": comments,
        "validated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.validation_records.insert_one(validation_record)
    
    return {"message": "Registro de validación creado", "record_id": record_id}


@api_router.get("/validation/records")
async def get_validation_records(
    limit: int = Query(100),
    current_user: User = Depends(get_current_user)
):
    """Get all validation records"""
    records = await db.validation_records.find({}, {"_id": 0}).sort("validated_at", -1).limit(limit).to_list(limit)
    
    for record in records:
        if isinstance(record.get('validated_at'), str):
            record['validated_at'] = datetime.fromisoformat(record['validated_at'])
    
    return records


@api_router.get("/validation/summary")
async def get_validation_summary(current_user: User = Depends(get_current_user)):
    """Get validation summary statistics"""
    
    records = await db.validation_records.find({}, {"_id": 0}).to_list(1000)
    
    if not records:
        return {
            "total_evaluated": 0,
            "industry_accuracy": 0,
            "functional_area_accuracy": 0,
            "seniority_accuracy": 0,
            "avg_parsing_quality": 0,
            "search_relevance_rate": 0,
            "common_errors": []
        }
    
    total = len(records)
    
    # Calculate accuracies
    industry_correct = sum(1 for r in records if r.get('industry_correct') == True)
    industry_total = sum(1 for r in records if r.get('industry_correct') is not None)
    
    functional_area_correct = sum(1 for r in records if r.get('functional_area_correct') == True)
    functional_area_total = sum(1 for r in records if r.get('functional_area_correct') is not None)
    
    seniority_correct = sum(1 for r in records if r.get('seniority_correct') == True)
    seniority_total = sum(1 for r in records if r.get('seniority_correct') is not None)
    
    # Parsing quality
    parsing_scores = [r.get('parsing_quality_score') for r in records if r.get('parsing_quality_score')]
    avg_parsing = sum(parsing_scores) / len(parsing_scores) if parsing_scores else 0
    
    # Search relevance
    search_relevant = sum(1 for r in records if r.get('search_relevant') == True)
    search_total = sum(1 for r in records if r.get('search_relevant') is not None)
    
    # Common errors
    errors = {}
    for record in records:
        if record.get('industry_correct') == False:
            key = f"Industria incorrecta: {record.get('atlas_industry')} → {record.get('expected_industry')}"
            errors[key] = errors.get(key, 0) + 1
        
        if record.get('functional_area_correct') == False:
            key = f"Área incorrecta: {record.get('atlas_functional_area')} → {record.get('expected_functional_area')}"
            errors[key] = errors.get(key, 0) + 1
    
    common_errors = [{"error": k, "count": v} for k, v in sorted(errors.items(), key=lambda x: x[1], reverse=True)[:5]]
    
    return {
        "total_evaluated": total,
        "industry_accuracy": round((industry_correct / industry_total * 100) if industry_total > 0 else 0, 1),
        "functional_area_accuracy": round((functional_area_correct / functional_area_total * 100) if functional_area_total > 0 else 0, 1),
        "seniority_accuracy": round((seniority_correct / seniority_total * 100) if seniority_total > 0 else 0, 1),
        "avg_parsing_quality": round(avg_parsing, 1),
        "search_relevance_rate": round((search_relevant / search_total * 100) if search_total > 0 else 0, 1),
        "common_errors": common_errors
    }


@api_router.get("/validation/export")
async def export_validation_records(current_user: User = Depends(get_current_user)):
    """Export validation records as CSV"""
    import csv
    from io import StringIO
    
    records = await db.validation_records.find({}, {"_id": 0}).to_list(1000)
    
    if not records:
        return Response(content="No hay registros de validación", media_type="text/csv")
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=records[0].keys())
    writer.writeheader()
    writer.writerows(records)
    
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=atlas_validation_records.csv"}
    )

async def delete_functional_area(
    area_id: str,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN]))
):
    """Delete functional area (Super Admin only)"""
    # Check if any candidates use this functional area
    count = await db.candidates.count_documents({"functional_area": area_id})
    
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar. {count} candidatos usan esta área funcional"
        )
    
    result = await db.functional_areas.delete_one({"id": area_id})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Área funcional no encontrada"
        )
    
    return {"message": "Área funcional eliminada"}



# ============= TAXONOMY ROUTES (ADMIN) =============

@api_router.get("/taxonomy/industries", response_model=List[Industry])
async def get_industries(current_user: User = Depends(get_current_user)):
    """Get all industries"""
    industries = await db.industries.find({}, {"_id": 0}).to_list(1000)
    
    for industry in industries:
        if isinstance(industry.get('created_at'), str):
            industry['created_at'] = datetime.fromisoformat(industry['created_at'])
    
    return industries


@api_router.get("/taxonomy/functional-areas", response_model=List[FunctionalArea])
async def get_functional_areas(current_user: User = Depends(get_current_user)):
    """Get all functional areas"""
    areas = await db.functional_areas.find({}, {"_id": 0}).to_list(1000)
    
    for area in areas:
        if isinstance(area.get('created_at'), str):
            area['created_at'] = datetime.fromisoformat(area['created_at'])
    
    return areas


@api_router.get("/taxonomy/lookup")
async def get_taxonomy_lookup(current_user: User = Depends(get_current_user)):
    """Get taxonomy lookup maps (key -> display names) for frontend"""
    industries = await db.industries.find({}, {"_id": 0, "key": 1, "name_es": 1, "name_en": 1}).to_list(1000)
    areas = await db.functional_areas.find({}, {"_id": 0, "key": 1, "name_es": 1, "name_en": 1}).to_list(1000)
    
    return {
        "industries": {ind["key"]: {"name_es": ind["name_es"], "name_en": ind["name_en"]} for ind in industries},
        "functional_areas": {area["key"]: {"name_es": area["name_es"], "name_en": area["name_en"]} for area in areas}
    }


@api_router.get("/taxonomy/seniority-levels")
async def get_seniority_levels(current_user: User = Depends(get_current_user)):
    """Get seniority levels configuration"""
    return {
        "levels": SENIORITY_LEVELS,
        "keywords": SENIORITY_TITLE_KEYWORDS
    }


@api_router.post("/candidates/{candidate_id}/reclassify-seniority")
async def reclassify_candidate_seniority(
    candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Reclasifica el seniority de un candidato usando la nueva lógica.
    Basado en: título del puesto + años de experiencia.
    """
    candidate = await db.candidates.find_one(
        {"id": candidate_id},
        {"_id": 0, "id": 1, "full_name": 1, "current_title": 1, "years_experience": 1, "seniority": 1, "previous_companies": 1}
    )
    
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato no encontrado")
    
    # Verificar permisos de edición
    await verify_candidate_edit_permission(candidate_id, current_user)
    
    # Obtener título - usar current_title o el más reciente de previous_companies
    title = candidate.get("current_title")
    if not title and candidate.get("previous_companies"):
        title = candidate["previous_companies"][0].get("title", "")
    
    years = candidate.get("years_experience", 0)
    old_seniority = candidate.get("seniority")
    
    # Clasificar
    result = classify_seniority(title, years)
    new_seniority = result["seniority"]
    
    # Actualizar si cambió
    if new_seniority != old_seniority:
        await db.candidates.update_one(
            {"id": candidate_id},
            {"$set": {
                "seniority": new_seniority,
                "seniority_classification": result,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
    
    return {
        "candidate_id": candidate_id,
        "candidate_name": candidate.get("full_name"),
        "old_seniority": old_seniority,
        "new_seniority": new_seniority,
        "changed": new_seniority != old_seniority,
        "classification_details": result
    }


@api_router.post("/admin/reclassify-all-seniority")
async def reclassify_all_seniority(
    dry_run: bool = Query(True, description="Si es True, solo simula sin guardar cambios"),
    current_user: User = Depends(get_current_user)
):
    """
    Reclasifica el seniority de TODOS los candidatos usando la nueva lógica.
    Solo Admin puede ejecutar esto.
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo Admin puede ejecutar reclasificación masiva")
    
    candidates = await db.candidates.find(
        {"is_deleted": {"$ne": True}},
        {"_id": 0, "id": 1, "full_name": 1, "current_title": 1, "years_experience": 1, "seniority": 1, "previous_companies": 1}
    ).to_list(5000)
    
    results = {
        "total_processed": 0,
        "changed": 0,
        "unchanged": 0,
        "examples_changed": [],
        "by_new_seniority": {}
    }
    
    for candidate in candidates:
        title = candidate.get("current_title")
        if not title and candidate.get("previous_companies"):
            title = candidate["previous_companies"][0].get("title", "")
        
        years = candidate.get("years_experience", 0)
        old_seniority = candidate.get("seniority")
        
        classification = classify_seniority(title, years)
        new_seniority = classification["seniority"]
        
        results["total_processed"] += 1
        
        # Contar por nuevo seniority
        if new_seniority not in results["by_new_seniority"]:
            results["by_new_seniority"][new_seniority] = 0
        results["by_new_seniority"][new_seniority] += 1
        
        if new_seniority != old_seniority:
            results["changed"] += 1
            
            # Guardar ejemplos (máximo 10)
            if len(results["examples_changed"]) < 10:
                results["examples_changed"].append({
                    "name": candidate.get("full_name"),
                    "title": title,
                    "years": years,
                    "old_seniority": old_seniority,
                    "new_seniority": new_seniority,
                    "reason": classification["reason"]
                })
            
            # Si no es dry_run, actualizar
            if not dry_run:
                await db.candidates.update_one(
                    {"id": candidate["id"]},
                    {"$set": {
                        "seniority": new_seniority,
                        "seniority_classification": classification,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
        else:
            results["unchanged"] += 1
    
    results["dry_run"] = dry_run
    if dry_run:
        results["message"] = "Simulación completada. Usa dry_run=false para aplicar cambios."
    else:
        results["message"] = f"Reclasificación completada. {results['changed']} candidatos actualizados."
    
    return results


# ============= SEED DATA ROUTE =============

@api_router.post("/seed/initial-data")
async def seed_initial_data():
    """Seed initial taxonomy data from master taxonomy file"""
    from taxonomy import get_all_industries, get_all_functional_areas
    
    # Check if already seeded
    existing_industries = await db.industries.count_documents({})
    if existing_industries > 0:
        return {"message": "Datos ya inicializados"}
    
    # Seed industries from taxonomy.py
    industries = []
    for ind in get_all_industries():
        industries.append({
            "id": str(uuid.uuid4()),
            "key": ind["key"],
            "name_es": ind["name_es"],
            "name_en": ind["name_en"],
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    await db.industries.insert_many(industries)
    
    # Seed functional areas from taxonomy.py
    functional_areas = []
    for area in get_all_functional_areas():
        functional_areas.append({
            "id": str(uuid.uuid4()),
            "key": area["key"],
            "name_es": area["name_es"],
            "name_en": area["name_en"],
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    await db.functional_areas.insert_many(functional_areas)
    
    return {
        "message": "Datos inicializados correctamente",
        "industries": len(industries),
        "functional_areas": len(functional_areas)
    }


# ============= JOB / VACANTES ENDPOINTS =============

@api_router.post("/jobs/parse-jd")
async def parse_job_description(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Parse a Job Description document (PDF/DOCX) and extract structured data.
    
    Returns structured job data that can be used to pre-fill the job creation form.
    The user should review and edit before saving.
    """
    user = await get_current_user(credentials)
    
    # Validar tipo de archivo
    file_ext = file.filename.split('.')[-1].lower() if file.filename else ''
    if file_ext not in ['pdf', 'docx']:
        raise HTTPException(
            status_code=400, 
            detail="Formato no soportado. Solo se permiten archivos PDF o DOCX."
        )
    
    try:
        # Leer archivo
        file_data = await file.read()
        
        if len(file_data) == 0:
            raise HTTPException(status_code=400, detail="El archivo está vacío")
        
        if len(file_data) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail="El archivo excede el límite de 10MB")
        
        # Extraer texto
        try:
            extracted_text = DocumentParser.extract_text_from_bytes(file_data, file.content_type)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error extrayendo texto: {str(e)}")
        
        if not extracted_text or len(extracted_text.strip()) < 50:
            raise HTTPException(
                status_code=400, 
                detail="No se pudo extraer suficiente texto del documento. Verifica que el archivo contenga texto legible."
            )
        
        logger.info(f"JD text extracted: {len(extracted_text)} chars from {file.filename}")
        
        # Parsear con AI
        from atlas_service import atlas_service
        parsed_data = await atlas_service.parse_job_description(extracted_text)
        
        # Agregar metadata
        parsed_data["_source_file"] = file.filename
        parsed_data["_text_length"] = len(extracted_text)
        parsed_data["_parsed_by"] = user.id
        
        logger.info(f"JD parsed successfully: {parsed_data.get('title', 'No title')} - Confidence: {parsed_data.get('confidence_score', 0)}")
        
        return {
            "success": True,
            "data": parsed_data,
            "message": "Documento procesado. Revisa y ajusta la información antes de guardar."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing JD: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error procesando documento: {str(e)}")

@api_router.post("/jobs", response_model=Job)
async def create_job(
    job_data: JobCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Crear nueva vacante"""
    user = await get_current_user(credentials)
    
    # Crear ID único
    job_id = str(uuid.uuid4())
    
    # Construir documento
    job_doc = {
        "id": job_id,
        **job_data.model_dump(),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.id,
        "embedding": None
    }
    
    # Generar embedding para la vacante
    if embedding_service.enabled:
        try:
            searchable_text = f"""
            Puesto: {job_data.title}
            Área: {job_data.functional_area}
            Industria: {job_data.industry}
            Nivel: {job_data.seniority}
            Skills: {', '.join(job_data.required_skills + job_data.preferred_skills)}
            Responsabilidades: {job_data.responsibilities or ''}
            Requisitos: {job_data.requirements or ''}
            Descripción: {job_data.description or ''}
            """
            embedding = await embedding_service.generate_embedding(searchable_text)
            if embedding:
                job_doc["embedding"] = embedding
                logger.info(f"Generated embedding for job {job_id}")
        except Exception as e:
            logger.error(f"Error generating job embedding: {str(e)}")
    
    # Guardar en MongoDB
    await db.jobs.insert_one(job_doc)
    
    # Remover _id para respuesta
    job_doc.pop("_id", None)
    
    return job_doc


@api_router.get("/jobs", response_model=List[Job])
async def list_jobs(
    status: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Listar vacantes"""
    await get_current_user(credentials)
    
    query = {}
    if status:
        query["status"] = status
    
    jobs = await db.jobs.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return jobs


@api_router.get("/jobs/{job_id}", response_model=Job)
async def get_job(
    job_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Obtener detalle de vacante"""
    await get_current_user(credentials)
    
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")
    
    return job


@api_router.put("/jobs/{job_id}", response_model=Job)
async def update_job(
    job_id: str,
    job_update: JobUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Actualizar vacante"""
    await get_current_user(credentials)
    
    # Verificar que existe
    existing = await db.jobs.find_one({"id": job_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")
    
    # Construir actualización
    update_data = {k: v for k, v in job_update.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    # Si se actualizan campos relevantes, regenerar embedding
    embedding_fields = {"title", "functional_area", "industry", "required_skills", 
                       "preferred_skills", "responsibilities", "requirements", "description"}
    if embedding_fields & set(update_data.keys()) and embedding_service.enabled:
        try:
            # Merge con datos existentes para generar embedding completo
            merged = {**existing, **update_data}
            searchable_text = f"""
            Puesto: {merged.get('title', '')}
            Área: {merged.get('functional_area', '')}
            Industria: {merged.get('industry', '')}
            Skills: {', '.join(merged.get('required_skills', []) + merged.get('preferred_skills', []))}
            Responsabilidades: {merged.get('responsibilities', '') or ''}
            Descripción: {merged.get('description', '') or ''}
            """
            embedding = await embedding_service.generate_embedding(searchable_text)
            if embedding:
                update_data["embedding"] = embedding
        except Exception as e:
            logger.error(f"Error updating job embedding: {str(e)}")
    
    await db.jobs.update_one(
        {"id": job_id},
        {"$set": update_data}
    )
    
    updated_job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    return updated_job


@api_router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Eliminar vacante"""
    await get_current_user(credentials)
    
    result = await db.jobs.delete_one({"id": job_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")
    
    return {"message": "Vacante eliminada correctamente"}


@api_router.post("/jobs/{job_id}/match", response_model=JobMatchResponse)
async def match_job_candidates(
    job_id: str,
    threshold: int = Query(default=60, ge=0, le=100, description="Score mínimo para incluir"),
    limit: int = Query(default=50, ge=1, le=200, description="Máximo de resultados"),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Ejecutar matching de candidatos contra una vacante.
    Retorna lista de candidatos rankeados con breakdown de compatibilidad.
    """
    await get_current_user(credentials)
    
    # Obtener vacante
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")
    
    # Ejecutar matching
    result = await job_matching_service.match_candidates(
        job=job,
        threshold=threshold,
        limit=limit
    )
    
    try:
        await enrich_results_with_flags(result.get("results", []))
    except Exception as e:
        logger.warning(f"No se pudieron enriquecer flags v2: {e}")
    
    # Doble visualización (transición v2→v3): agrega HMS v3 + acción a cada resultado v2.
    # Solo lectura/display — NO altera el orden ni los scores v2.
    try:
        from scoring.engine_v3 import score_v3
        ids = [r.get("candidate_id") for r in result.get("results", []) if r.get("candidate_id")]
        if ids:
            docs = await db.candidates.find({"id": {"$in": ids}}, {"_id": 0}).to_list(len(ids))
            cmap = {d["id"]: d for d in docs}
            for r in result.get("results", []):
                cd = cmap.get(r.get("candidate_id"))
                if cd:
                    v3 = score_v3(cd, job)
                    r["v3_hms"] = v3.get("match_score_v3")
                    r["v3_action"] = v3.get("recommended_action")
    except Exception as e:
        logger.warning(f"No se pudo calcular v3 comparativo: {e}")
    
    user_for_log = await get_current_user(credentials)
    await log_activity(user_for_log, "matching_run", "job", job_id, job.get("title"), {"engine": "v2"})
    
    return result


@api_router.get("/jobs/{job_id}/matches", response_model=JobMatchResponse)
async def get_job_matches(
    job_id: str,
    threshold: int = Query(default=60, ge=0, le=100),
    limit: int = Query(default=50, ge=1, le=200),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Obtener candidatos rankeados para una vacante (ejecuta matching).
    Alias de POST /jobs/{job_id}/match para conveniencia.
    """
    return await match_job_candidates(job_id, threshold, limit, credentials)


@api_router.post("/jobs/{job_id}/match-v3")
async def match_job_candidates_v3(
    job_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Matching v3 (HMS). No persiste resultados. Feature flag: MATCHING_ENGINE_VERSION."""
    await get_current_user(credentials)

    engine_version = os.environ.get("MATCHING_ENGINE_VERSION", "v2")
    if engine_version == "v2":
        raise HTTPException(
            status_code=403,
            detail="Motor v3 deshabilitado. Configura MATCHING_ENGINE_VERSION=v3 o compare."
        )

    from scoring.engine_v3 import score_v3

    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")

    candidates = await db.candidates.find(
        {"is_deleted": {"$ne": True}}, {"_id": 0}
    ).to_list(2000)

    results = []
    for cand in candidates:
        try:
            r = score_v3(cand, job)
            r["candidate_id"] = cand.get("id")
            r["candidate_name"] = cand.get("full_name")
            r["current_title"] = cand.get("current_title")
            results.append(r)
        except Exception as e:
            logger.warning(f"score_v3 falló para {cand.get('id')}: {e}")

    results.sort(key=lambda x: x.get("match_score_v3", 0), reverse=True)
    results = results[:limit]

    try:
        await enrich_results_with_flags(results)
    except Exception as e:
        logger.warning(f"No se pudieron enriquecer flags v3: {e}")

    user_v3 = await get_current_user(credentials)
    await log_activity(user_v3, "matching_run", "job", job_id, job.get("title"), {"engine": "v3"})

    if engine_version == "compare":
        v2_result = await job_matching_service.match_candidates(job=job, threshold=60, limit=limit)
        return {"engine": "compare", "v3": results, "v2": v2_result}

    return {"engine": "v3", "job_id": job_id, "total_evaluated": len(candidates), "results": results}


# ============= JOB SCORECARD ENDPOINTS (v3) =============

def default_scorecard_from_job(job: dict) -> dict:
    """Deriva un scorecard básico para jobs sin scorecard guardado."""
    from scoring.engine_v3 import derive_default_scorecard
    return derive_default_scorecard(job)


@api_router.put("/jobs/{job_id}/scorecard")
async def update_job_scorecard(
    job_id: str,
    scorecard: JobScorecard,
    current_user: User = Depends(get_current_user)
):
    """Guarda el JobScorecard de una vacante (motor de scoring v3)."""
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0, "id": 1})
    if not job:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")
    
    await db.jobs.update_one(
        {"id": job_id},
        {"$set": {
            "job_scorecard": scorecard.model_dump(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"job_id": job_id, "scorecard": scorecard, "source": "saved"}


@api_router.get("/jobs/{job_id}/scorecard")
async def get_job_scorecard(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """Devuelve el JobScorecard guardado o, si no existe, uno derivado del job."""
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")
    
    saved = job.get("job_scorecard")
    if saved:
        return {"job_id": job_id, "scorecard": saved, "source": "saved"}
    return {"job_id": job_id, "scorecard": default_scorecard_from_job(job), "source": "derived"}


# ============= JOB ASSIGNMENTS (vínculo candidato↔vacante) + DASHBOARD OPERATIVO =============

class AssignJobRequest(PydanticBaseModel):
    job_id: str

class UpdateAssignmentStageRequest(PydanticBaseModel):
    stage: str


@api_router.post("/candidates/{candidate_id}/assign-job")
async def assign_candidate_to_job(
    candidate_id: str,
    request: AssignJobRequest,
    current_user: User = Depends(get_current_user)
):
    """Asigna un candidato a una vacante (stage inicial: new)"""
    cand = await db.candidates.find_one({"id": candidate_id, "is_deleted": {"$ne": True}}, {"_id": 0, "full_name": 1, "job_assignments": 1})
    if not cand:
        raise HTTPException(status_code=404, detail="Candidato no encontrado")
    job = await db.jobs.find_one({"id": request.job_id}, {"_id": 0, "title": 1, "company": 1})
    if not job:
        raise HTTPException(status_code=404, detail="Vacante no encontrada")
    if any(a.get("job_id") == request.job_id for a in (cand.get("job_assignments") or [])):
        raise HTTPException(status_code=409, detail="El candidato ya está asignado a esta vacante")
    
    now = datetime.now(timezone.utc).isoformat()
    assignment = {
        "job_id": request.job_id,
        "stage": "new",
        "assigned_by": current_user.name,
        "assigned_at": now,
        "updated_at": now,
    }
    await db.candidates.update_one({"id": candidate_id}, {"$push": {"job_assignments": assignment}})
    await log_activity(current_user, "candidate_assigned", "candidate", candidate_id, cand.get("full_name"), {"job_id": request.job_id, "job_title": job.get("title")})
    return {"message": "Candidato asignado", "assignment": assignment}


@api_router.put("/candidates/{candidate_id}/job-assignments/{job_id}")
async def update_assignment_stage(
    candidate_id: str,
    job_id: str,
    request: UpdateAssignmentStageRequest,
    current_user: User = Depends(get_current_user)
):
    """Actualiza el stage del vínculo. Si llega a 'placed', crea la restricción de colocación."""
    if request.stage not in JOB_ASSIGNMENT_STAGES:
        raise HTTPException(status_code=400, detail=f"Stage inválido. Válidos: {sorted(JOB_ASSIGNMENT_STAGES)}")
    
    now = datetime.now(timezone.utc).isoformat()
    result = await db.candidates.update_one(
        {"id": candidate_id, "job_assignments.job_id": job_id},
        {"$set": {"job_assignments.$.stage": request.stage, "job_assignments.$.updated_at": now}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Asignación no encontrada")
    
    cand = await db.candidates.find_one({"id": candidate_id}, {"_id": 0, "full_name": 1, "is_restricted": 1, "restriction_info": 1})
    job = await db.jobs.find_one({"id": job_id}, {"_id": 0, "title": 1, "company": 1})
    
    if request.stage == "placed":
        restriction_info = {
            "category": "placed_by_humaniq",
            "category_label": RESTRICTION_CATEGORIES["placed_by_humaniq"],
            "reason": f"Colocado en '{(job or {}).get('title')}' — Cliente: {(job or {}).get('company') or 'N/D'}",
            "job_id": job_id,
            "job_title": (job or {}).get("title"),
            "client": (job or {}).get("company"),
            "placed_at": now,
            "marked_by": current_user.id,
            "marked_by_name": current_user.name,
            "marked_at": now,
        }
        await db.candidates.update_one(
            {"id": candidate_id},
            {"$set": {"is_restricted": True, "restriction_info": restriction_info, "updated_at": now}}
        )
        await log_activity(current_user, "candidate_placed", "candidate", candidate_id, (cand or {}).get("full_name"), {"job_id": job_id, "job_title": (job or {}).get("title")})
    else:
        await log_activity(current_user, "assignment_stage_changed", "candidate", candidate_id, (cand or {}).get("full_name"), {"job_id": job_id, "stage": request.stage})
    
    return {"message": "Stage actualizado", "stage": request.stage}


@api_router.get("/jobs/{job_id}/assignments")
async def get_job_assignments(
    job_id: str,
    current_user: User = Depends(get_current_user)
):
    """Candidatos asignados a una vacante con su stage en ese vínculo"""
    cands = await db.candidates.find(
        {"is_deleted": {"$ne": True}, "job_assignments.job_id": job_id},
        {"_id": 0, "id": 1, "full_name": 1, "current_title": 1, "current_company": 1,
         "job_assignments": 1, "is_restricted": 1, "restriction_info": 1, "notes": 1}
    ).to_list(500)
    
    items = []
    for c in cands:
        a = next((x for x in c.get("job_assignments", []) if x.get("job_id") == job_id), None)
        if not a:
            continue
        items.append({
            "candidate_id": c["id"],
            "candidate_name": c.get("full_name"),
            "current_title": c.get("current_title"),
            "stage": a.get("stage"),
            "assigned_by": a.get("assigned_by"),
            "updated_at": a.get("updated_at"),
            "is_placed": candidate_is_placed(c),
            "notes_count": len(c.get("notes") or []),
        })
    return {"job_id": job_id, "assignments": items, "total": len(items)}


@api_router.get("/candidates/{candidate_id}/notes")
async def get_candidate_notes(
    candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """Notas del candidato — visibles para todo el equipo"""
    cand = await db.candidates.find_one({"id": candidate_id}, {"_id": 0, "notes": 1})
    if not cand:
        raise HTTPException(status_code=404, detail="Candidato no encontrado")
    notes = cand.get("notes") or []
    return {"candidate_id": candidate_id, "notes": notes, "total": len(notes)}


@api_router.get("/dashboard/operational")
async def get_operational_dashboard(current_user: User = Depends(get_current_user)):
    """Dashboard operativo: KPIs, tablero de vacantes, actividad y bandeja personal (solo lectura)"""
    now = datetime.now(timezone.utc)
    active_q = {"is_deleted": {"$ne": True}}
    
    def parse_dt(v):
        if not v:
            return None
        if isinstance(v, datetime):
            return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    
    # ===== KPIs =====
    total_candidates = await db.candidates.count_documents(active_q)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    candidates_this_month = await db.candidates.count_documents({**active_q, "created_at": {"$gte": month_start}})
    pending_pipeline = [
        {"$match": {"is_deleted": {"$ne": True}}},
        {"$addFields": {
            "has_classification": {"$ifNull": ["$ai_classification", None]},
            "conf_score": {"$ifNull": ["$ai_classification.confidence_score", 0]},
            "is_approved": {"$ifNull": ["$ai_classification.approved_by_recruiter", False]},
        }},
        {"$match": {"$or": [
            {"has_classification": None},
            {"$and": [{"conf_score": {"$lt": 0.75}}, {"is_approved": False}]},
        ]}},
        {"$count": "n"},
    ]
    pending_rows = await db.candidates.aggregate(pending_pipeline).to_list(1)
    pending_classifications = pending_rows[0]["n"] if pending_rows else 0
    placed_count = await db.candidates.count_documents({"$and": [active_q, {"$or": [
        {"is_restricted": True, "restriction_info.category": "placed_by_humaniq"},
        {"job_assignments": {"$elemMatch": {"stage": "placed"}}},
    ]}]})
    
    jobs = await db.jobs.find({"$or": [{"status": "active"}, {"status": {"$exists": False}}]}, {"_id": 0}).to_list(500)
    days_open_list = []
    for j in jobs:
        dt = parse_dt(j.get("created_at"))
        j["_days_open"] = (now - dt).days if dt else 0
        days_open_list.append(j["_days_open"])
    avg_days_open = round(sum(days_open_list) / len(days_open_list), 1) if days_open_list else 0
    
    # ===== users map =====
    users = await db.users.find({}, {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(100)
    user_names = {u["id"]: (u.get("name") or u.get("email")) for u in users}
    
    # ===== candidates_by_stage por vacante =====
    stage_pipeline = [
        {"$match": {**active_q, "job_assignments.0": {"$exists": True}}},
        {"$unwind": "$job_assignments"},
        {"$group": {"_id": {"job": "$job_assignments.job_id", "stage": "$job_assignments.stage"}, "n": {"$sum": 1}}},
    ]
    stage_counts = {}
    assignment_last = {}
    async for row in db.candidates.aggregate(stage_pipeline):
        jid = row["_id"]["job"]
        stage_counts.setdefault(jid, {})[row["_id"]["stage"]] = row["n"]
    async for row in db.candidates.aggregate([
        {"$match": {**active_q, "job_assignments.0": {"$exists": True}}},
        {"$unwind": "$job_assignments"},
        {"$group": {"_id": "$job_assignments.job_id", "last": {"$max": "$job_assignments.updated_at"}}},
    ]):
        assignment_last[row["_id"]] = row["last"]
    
    # última actividad por job desde activity_logs
    job_activity_last = {}
    async for row in db.activity_logs.aggregate([
        {"$match": {"entity_type": "job"}},
        {"$group": {"_id": "$entity_id", "last": {"$max": "$timestamp"}}},
    ]):
        job_activity_last[row["_id"]] = row["last"]
    
    jobs_board = []
    for j in jobs:
        candidates_by_stage = stage_counts.get(j["id"], {})
        last_candidates = [parse_dt(j.get("updated_at")), parse_dt(j.get("created_at")),
                           parse_dt(job_activity_last.get(j["id"])), parse_dt(assignment_last.get(j["id"]))]
        last_activity = max([d for d in last_candidates if d], default=None)
        days_inactive = (now - last_activity).days if last_activity else 999
        health = "green" if days_inactive < 7 else ("yellow" if days_inactive <= 14 else "red")
        jobs_board.append({
            "id": j["id"],
            "title": j.get("title"),
            "company": j.get("company"),
            "days_open": j["_days_open"],
            "created_by": user_names.get(j.get("created_by"), j.get("created_by") or "—"),
            "candidates_by_stage": candidates_by_stage,
            "assigned_total": sum(candidates_by_stage.values()),
            "last_activity_date": last_activity.isoformat() if last_activity else None,
            "health": health,
        })
    health_order = {"red": 0, "yellow": 1, "green": 2}
    jobs_board.sort(key=lambda x: (health_order[x["health"]], -x["days_open"]))
    
    # ===== recent_activity =====
    logs = await db.activity_logs.find({}, {"_id": 0}).sort("timestamp", -1).to_list(20)
    for lg in logs:
        if not lg.get("user_name"):
            lg["user_name"] = user_names.get(lg.get("user_id"), "Sistema")
    
    # ===== action_inbox =====
    is_admin = current_user.role in [UserRole.SUPER_ADMIN, UserRole.ADMIN]
    unassigned_q = {
        **active_q,
        "$or": [{"job_assignments": {"$exists": False}}, {"job_assignments": {"$size": 0}}],
    }
    if not is_admin:
        unassigned_q["created_by"] = current_user.id
    my_unassigned = await db.candidates.count_documents(unassigned_q)
    my_stale_jobs = [
        {"id": j["id"], "title": j["title"], "days_inactive": (now - parse_dt(j["last_activity_date"])).days if j["last_activity_date"] else None}
        for j in jobs_board
        if user_names.get(current_user.id) == j["created_by"] and j["health"] != "green"
    ]
    action_inbox = {
        "pending_classifications": pending_classifications,
        "my_unassigned_candidates": my_unassigned,
        "unassigned_scope": "team" if is_admin else "mine",
        "my_stale_jobs": my_stale_jobs[:10],
    }
    
    # ===== charts =====
    by_area = []
    async for row in db.candidates.aggregate([
        {"$match": active_q},
        {"$group": {"_id": "$functional_area", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}}, {"$limit": 10},
    ]):
        by_area.append({"area": row["_id"] or "sin_clasificar", "count": row["n"]})
    
    week_buckets = {}
    for i in range(8):
        week_start = (now - timedelta(days=now.weekday()) - timedelta(weeks=7 - i)).replace(hour=0, minute=0, second=0, microsecond=0)
        week_buckets[week_start.strftime("%d %b")] = [week_start, 0]
    async for c in db.candidates.find({**active_q, "created_at": {"$gte": (now - timedelta(weeks=8)).isoformat()}}, {"_id": 0, "created_at": 1}):
        dt = parse_dt(c.get("created_at"))
        if not dt:
            continue
        for label, (start, _) in week_buckets.items():
            if start <= dt < start + timedelta(weeks=1):
                week_buckets[label][1] += 1
                break
    new_by_week = [{"week": label, "count": v[1]} for label, v in week_buckets.items()]
    
    caliber_rank = {"multinacional_global": 4, "corporativo_nacional": 3, "mediana": 2, "pyme": 1, "startup": 0}
    caliber_dist = {k: 0 for k in caliber_rank}
    async for c in db.candidates.find(active_q, {"_id": 0, "previous_companies.company_caliber": 1}):
        calibers = [pc.get("company_caliber") for pc in (c.get("previous_companies") or []) if pc.get("company_caliber") in caliber_rank]
        if calibers:
            rep = max(calibers, key=lambda x: caliber_rank[x])
            caliber_dist[rep] += 1
    by_caliber = [{"caliber": k, "count": v} for k, v in caliber_dist.items()]
    
    return {
        "kpis": {
            "total_candidates_active": total_candidates,
            "total_jobs_active": len(jobs),
            "candidates_this_month": candidates_this_month,
            "avg_days_jobs_open": avg_days_open,
            "pending_classifications_count": pending_classifications,
            "placed_candidates_count": placed_count,
        },
        "jobs_board": jobs_board,
        "recent_activity": logs,
        "action_inbox": action_inbox,
        "charts": {"by_functional_area": by_area, "new_by_week": new_by_week, "by_caliber": by_caliber},
    }


# ============= USER MANAGEMENT ENDPOINTS =============

@api_router.get("/users")
async def list_users(
    include_inactive: bool = Query(default=False),
    current_user: User = Depends(get_current_user)
):
    """
    Listar todos los usuarios (solo Admin/Super Admin).
    """
    try:
        users = await user_service.list_users_with_stats(current_user)
        if not include_inactive:
            users = [u for u in users if u.get("is_active", True)]
        return {"users": users, "total": len(users)}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@api_router.post("/users")
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Crear nuevo usuario (solo Admin/Super Admin).
    """
    try:
        new_user = await user_service.create_user(user_data, current_user)
        return new_user
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@api_router.get("/users/me")
async def get_current_user_details(current_user: User = Depends(get_current_user)):
    """
    Obtener detalles del usuario actual (incluye permisos).
    """
    user_data = current_user.model_dump()
    user_data["can_manage_users"] = user_service.can_manage_users(current_user)
    user_data["can_assign_candidates"] = assignment_service.can_assign(current_user)
    return user_data


@api_router.get("/users/recruiters")
async def get_recruiters(current_user: User = Depends(get_current_user)):
    """
    Obtener lista de reclutadores activos (para asignación de candidatos).
    Solo Admin/Super Admin pueden ver esta lista.
    """
    if not assignment_service.can_assign(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver la lista de reclutadores"
        )
    
    recruiters = await user_service.get_recruiters()
    return {"recruiters": recruiters}


@api_router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Obtener un usuario por ID.
    """
    if not user_service.can_manage_users(current_user) and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para ver este usuario"
        )
    
    user = await user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    
    return user


@api_router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    update_data: UserUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Actualizar usuario.
    - Admin/Super Admin: puede actualizar rol, nombre, estado
    - Usuario normal: solo puede actualizar su propio nombre
    """
    try:
        updated = await user_service.update_user(user_id, update_data, current_user)
        return updated
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@api_router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Desactivar usuario (soft delete).
    Solo Admin/Super Admin.
    """
    try:
        result = await user_service.deactivate_user(user_id, current_user)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ============= CANDIDATE STATUS ENDPOINTS =============

@api_router.put("/candidates/{candidate_id}/status")
async def change_candidate_status(
    candidate_id: str,
    request: StatusChangeRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Cambiar el estado de un candidato.
    Solo el recruiter asignado o Admin pueden cambiar el estado.
    """
    # Obtener candidato
    candidate = await db.candidates.find_one({"id": candidate_id})
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato no encontrado")
    
    current_status = candidate.get("status", "new")
    new_status = request.new_status.value
    
    # Validar transición
    valid_transitions = VALID_STATUS_TRANSITIONS.get(current_status, [])
    if new_status not in valid_transitions and current_status != new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transición no válida: {current_status} → {new_status}. Transiciones permitidas: {valid_transitions}"
        )
    
    # Verificar permisos: Admin puede todo, Recruiter solo si está asignado
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        # Verificar si el recruiter está asignado a este candidato
        assignment = await db.assignments.find_one({
            "candidate_id": candidate_id,
            "recruiter_id": current_user.id,
            "status": "active"
        })
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo puedes cambiar el estado de candidatos asignados a ti"
            )
    
    # Crear registro de historial
    status_change = {
        "from_status": current_status,
        "to_status": new_status,
        "changed_by": current_user.id,
        "changed_by_name": current_user.name,
        "changed_at": datetime.now(timezone.utc).isoformat(),
        "notes": request.notes
    }
    
    # Actualizar candidato
    now = datetime.now(timezone.utc).isoformat()
    update_result = await db.candidates.update_one(
        {"id": candidate_id},
        {
            "$set": {
                "status": new_status,
                "updated_at": now,
                "last_activity": now,
                "last_activity_type": "status_change"
            },
            "$push": {
                "status_history": status_change
            }
        }
    )
    
    if update_result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error actualizando estado")
    
    logger.info(f"Candidate {candidate_id} status changed: {current_status} → {new_status} by {current_user.email}")
    
    return {
        "candidate_id": candidate_id,
        "previous_status": current_status,
        "new_status": new_status,
        "changed_by": current_user.name,
        "changed_at": now
    }


@api_router.get("/candidates/{candidate_id}/status-history")
async def get_candidate_status_history(
    candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Obtener historial de cambios de estado de un candidato.
    """
    candidate = await db.candidates.find_one(
        {"id": candidate_id},
        {"_id": 0, "status": 1, "status_history": 1}
    )
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato no encontrado")
    
    return {
        "candidate_id": candidate_id,
        "current_status": candidate.get("status", "new"),
        "status_info": STATUS_COLORS.get(candidate.get("status", "new")),
        "history": candidate.get("status_history", [])
    }


@api_router.get("/status-config")
async def get_status_config(current_user: User = Depends(get_current_user)):
    """
    Obtener configuración de estados (colores, labels, transiciones).
    Útil para el frontend.
    """
    return {
        "statuses": STATUS_COLORS,
        "transitions": VALID_STATUS_TRANSITIONS
    }


# ============= CANDIDATE ASSIGNMENT ENDPOINTS =============

@api_router.post("/candidates/{candidate_id}/assign")
async def assign_candidate(
    candidate_id: str,
    assignment_data: AssignmentCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Asignar un candidato a un reclutador.
    Solo Admin/Super Admin pueden asignar.
    """
    try:
        # Validar que el candidate_id del path coincida
        if assignment_data.candidate_id != candidate_id:
            assignment_data.candidate_id = candidate_id
        
        assignment = await assignment_service.assign_candidate(
            candidate_id=candidate_id,
            recruiter_id=assignment_data.recruiter_id,
            assigned_by=current_user,
            notes=assignment_data.notes
        )
        return assignment
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@api_router.delete("/candidates/{candidate_id}/assign/{recruiter_id}")
async def unassign_candidate(
    candidate_id: str,
    recruiter_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Eliminar asignación de un candidato.
    Solo Admin/Super Admin.
    """
    try:
        result = await assignment_service.unassign_candidate(
            candidate_id=candidate_id,
            recruiter_id=recruiter_id,
            current_user=current_user
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@api_router.get("/candidates/{candidate_id}/assignments")
async def get_candidate_assignments(
    candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Obtener todas las asignaciones de un candidato.
    Todos los usuarios autenticados pueden ver esto.
    """
    assignments = await assignment_service.get_candidate_assignments(candidate_id)
    return {"assignments": assignments}


@api_router.get("/assignments/my")
async def get_my_assignments(current_user: User = Depends(get_current_user)):
    """
    Obtener candidatos asignados al usuario actual.
    """
    assignments = await assignment_service.get_my_assignments(current_user)
    return {"assignments": assignments, "total": len(assignments)}


@api_router.get("/assignments")
async def get_all_assignments(current_user: User = Depends(get_current_user)):
    """
    Obtener todas las asignaciones activas (solo Admin).
    """
    try:
        assignments = await assignment_service.get_all_assignments(current_user)
        
        # Contar candidatos sin asignar
        unassigned_count = await assignment_service.get_unassigned_candidates_count()
        
        return {
            "assignments": assignments,
            "total": len(assignments),
            "unassigned_candidates": unassigned_count
        }
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@api_router.post("/candidates/{candidate_id}/transfer")
async def transfer_candidate(
    candidate_id: str,
    from_recruiter_id: str = Query(...),
    to_recruiter_id: str = Query(...),
    notes: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user)
):
    """
    Transferir candidato de un reclutador a otro.
    Solo Admin/Super Admin.
    """
    try:
        result = await assignment_service.transfer_assignment(
            candidate_id=candidate_id,
            from_recruiter_id=from_recruiter_id,
            to_recruiter_id=to_recruiter_id,
            current_user=current_user,
            notes=notes
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@api_router.get("/candidates/{candidate_id}/can-edit")
async def check_candidate_edit_permission(
    candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Verificar si el usuario actual puede editar un candidato.
    Retorna información de permisos para la UI.
    """
    # Obtener asignaciones del candidato
    assignments = await assignment_service.get_candidate_assignments(candidate_id)
    
    can_edit = assignment_service.can_edit_candidate(current_user, candidate_id, assignments)
    
    # Determinar razón para UI
    reason = None
    if not can_edit:
        if current_user.role == UserRole.RECRUITER:
            reason = "Este candidato no está asignado a ti. Solo puedes ver su información."
        else:
            reason = "No tienes permisos de edición."
    
    return {
        "can_edit": can_edit,
        "reason": reason,
        "user_role": current_user.role.value,
        "assignments": assignments
    }


# ============= EXPORT ENDPOINTS =============

@api_router.post("/exports/job/{job_id}")
async def export_job_shortlist(
    job_id: str,
    format: ExportFormat = Query(default=ExportFormat.PDF),
    limit: int = Query(default=10, ge=1, le=20),
    include_risks: bool = Query(default=True),
    include_contact_info: bool = Query(default=False),
    client_name: Optional[str] = Query(default=None),
    engine: str = Query(default="v2"),
    current_user: User = Depends(get_current_user)
):
    """
    Exportar shortlist de candidatos de una vacante.
    Genera PDF o DOCX con branding Humaniq.
    - Solo Admin puede incluir información de contacto
    - Máximo 20 candidatos por exportación
    """
    try:
        result = await export_service.export_job_shortlist(
            job_id=job_id,
            user=current_user,
            format=format,
            limit=limit,
            include_risks=include_risks,
            include_contact_info=include_contact_info,
            client_name=client_name,
            engine=engine
        )
        job_doc = await db.jobs.find_one({"id": job_id}, {"_id": 0, "title": 1})
        await log_activity(current_user, "shortlist_exported", "job", job_id, (job_doc or {}).get("title"), {"engine": engine, "format": str(format)})
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error generando exportación")


@api_router.post("/exports/candidates")
async def export_custom_candidates(
    request: ExportRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Exportar selección custom de candidatos.
    """
    try:
        if not request.candidate_ids:
            raise ValueError("Debe proporcionar al menos un candidato")
        
        result = await export_service.export_custom_candidates(
            candidate_ids=request.candidate_ids,
            user=current_user,
            title=request.source_id or "Selección de Candidatos",  # Usar source_id como título si se proporciona
            format=request.format,
            include_risks=request.include_risks,
            include_contact_info=request.include_contact_info,
            client_name=request.client_name
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error generando exportación")


@api_router.get("/exports/{export_id}/download")
async def download_export(
    export_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Descargar archivo de exportación.
    """
    # Verificar que existe y pertenece al usuario (o es admin)
    record = await export_service.get_export_record(export_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exportación no encontrada")
    
    # Verificar permisos
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        if record.get("user_id") != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a esta exportación")
    
    # Obtener archivo
    file_data = await export_service.get_export_file(export_id)
    if not file_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado")
    
    file_bytes, filename, content_type = file_data
    
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


@api_router.get("/candidates/{candidate_id}/download-cv")
async def download_candidate_cv(
    candidate_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Descargar CV original del candidato (PDF/DOCX).
    """
    # Obtener candidato
    candidate = await db.candidates.find_one(
        {"id": candidate_id},
        {"_id": 0, "resume_files": 1, "full_name": 1}
    )
    
    if not candidate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato no encontrado")
    
    resume_files = candidate.get('resume_files', [])
    if not resume_files:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El candidato no tiene CV adjunto")
    
    # Tomar el primer archivo (más reciente normalmente)
    resume = resume_files[0]
    file_path = resume.get('file_path')
    file_name = resume.get('file_name', 'cv.pdf')
    file_type = resume.get('file_type', 'application/pdf')
    
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ruta del archivo no encontrada")
    
    # Intentar primero desde storage remoto
    try:
        if file_path.startswith('atlas-talent-vault/'):
            file_bytes, content_type = storage_service.get_object(file_path)
            return Response(
                content=file_bytes,
                media_type=content_type or file_type,
                headers={
                    "Content-Disposition": f"attachment; filename=\"{file_name}\""
                }
            )
    except Exception as e:
        logger.warning(f"Could not fetch from remote storage: {e}")
    
    # Fallback: archivo local
    local_path = ROOT_DIR / file_path
    if local_path.exists():
        with open(local_path, 'rb') as f:
            file_bytes = f.read()
        return Response(
            content=file_bytes,
            media_type=file_type,
            headers={
                "Content-Disposition": f"attachment; filename=\"{file_name}\""
            }
        )
    
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado en storage")


@api_router.get("/exports")
async def list_exports(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(get_current_user)
):
    """
    Listar exportaciones del usuario.
    Admin ve todas, recruiters solo las suyas.
    """
    exports = await export_service.list_exports(current_user, limit=limit)
    return {"exports": exports, "total": len(exports)}


@api_router.get("/exports/{export_id}")
async def get_export_details(
    export_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Obtener detalles de una exportación.
    """
    record = await export_service.get_export_record(export_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exportación no encontrada")
    
    # Verificar permisos
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        if record.get("user_id") != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a esta exportación")
    
    return record


# ============= SMART FOLDERS ENDPOINTS =============

@api_router.get("/folders")
async def list_folders(
    include_counts: bool = Query(default=True),
    current_user: User = Depends(get_current_user)
):
    """
    Lista todos los Smart Folders (sistema + usuario).
    Incluye conteo de candidatos por folder.
    """
    folders = await smart_folder_service.list_folders(current_user, include_counts)
    
    # Separar por categoría
    verticals = [f for f in folders if f.get("folder_category") == "vertical"]
    process = [f for f in folders if f.get("folder_category") == "process"]
    custom = [f for f in folders if f.get("folder_category") == "custom"]
    
    return {
        "folders": folders,
        "by_category": {
            "verticals": verticals,
            "process": process,
            "custom": custom
        },
        "total": len(folders)
    }


@api_router.post("/folders")
async def create_folder(
    data: SmartFolderCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Crear un nuevo Smart Folder personalizado.
    """
    try:
        folder = await smart_folder_service.create_folder(data, current_user)
        return folder
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@api_router.get("/folders/{folder_id}")
async def get_folder(
    folder_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Obtener detalle de un Smart Folder.
    """
    folder = await smart_folder_service.get_folder(folder_id, current_user)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder no encontrado")
    
    return folder


@api_router.put("/folders/{folder_id}")
async def update_folder(
    folder_id: str,
    data: SmartFolderUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Actualizar un Smart Folder de usuario.
    Los folders del sistema no pueden modificarse.
    """
    try:
        folder = await smart_folder_service.update_folder(folder_id, data, current_user)
        return folder
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@api_router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Eliminar un Smart Folder de usuario.
    Los folders del sistema no pueden eliminarse.
    """
    try:
        await smart_folder_service.delete_folder(folder_id, current_user)
        return {"message": "Folder eliminado"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@api_router.get("/folders/{folder_id}/candidates")
async def get_folder_candidates(
    folder_id: str,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    sort_by: str = Query(default="match_score"),
    current_user: User = Depends(get_current_user)
):
    """
    Obtener candidatos que matchean los criterios del folder.
    Los criterios se evalúan en tiempo real (Smart/Dinámico).
    """
    try:
        result = await smart_folder_service.get_folder_candidates(
            folder_id, current_user, skip, limit, sort_by
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@api_router.get("/folders/{folder_id}/count")
async def get_folder_count(
    folder_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Obtener conteo rápido de candidatos en el folder.
    Útil para actualizar badges en el sidebar.
    """
    folder = await smart_folder_service.get_folder(folder_id, current_user)
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder no encontrado")
    
    count = await smart_folder_service._count_candidates(folder, current_user)
    return {"folder_id": folder_id, "count": count}


@api_router.get("/folders/{folder_id}/analytics")
async def get_folder_analytics(
    folder_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Obtener métricas de uso del folder.
    """
    analytics = await smart_folder_service.get_folder_analytics(folder_id)
    if not analytics:
        return {
            "folder_id": folder_id,
            "total_views": 0,
            "views_last_30_days": 0,
            "total_exports": 0,
            "candidates_selected": 0,
            "last_accessed": None
        }
    return analytics


@api_router.post("/folders/initialize")
async def initialize_system_folders(
    force_update: bool = Query(False, description="Forzar actualización de folders existentes"),
    current_user: User = Depends(get_current_user)
):
    """
    Inicializa los folders del sistema (solo Admin).
    Con force_update=True actualiza los criterios de folders existentes.
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo Admin puede inicializar folders")
    
    await smart_folder_service.initialize_system_folders(force_update=force_update)
    return {"message": "Folders del sistema inicializados" + (" (criterios actualizados)" if force_update else "")}


# ============== BACKUP STATUS ENDPOINT ==============
@api_router.get("/admin/backup-status")
async def get_backup_status(current_user: User = Depends(get_current_user)):
    """Get the status of the last backup and next scheduled backup."""
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Solo administradores pueden ver el estado de backups")
    
    status_file = Path("/app/backups/last_backup_status.json")
    backup_dir = Path("/app/backups")
    
    # Get status from status file
    if status_file.exists():
        with open(status_file) as f:
            status = json.load(f)
    else:
        status = {
            "last_run": None,
            "success": None,
            "message": "No hay backups ejecutados aún",
            "next_run": None
        }
    
    # List available backups
    backups = []
    if backup_dir.exists():
        for f in sorted(backup_dir.glob("backup_*.archive.gz"), reverse=True)[:7]:
            backups.append({
                "filename": f.name,
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()
            })
    
    return {
        "scheduler_active": True,
        "backup_time_utc": "03:00",
        "last_backup": status,
        "available_backups": backups,
        "total_backups": len(backups)
    }


# ============= ROOT ROUTE =============

@api_router.get("/")
async def root():
    return {"message": "Atlas Talent Vault API", "version": "1.0.0"}


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

