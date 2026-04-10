from fastapi import FastAPI, APIRouter, HTTPException, status, Depends, UploadFile, File, Form, Header, Query, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import shutil

from models import (
    User, UserCreate, UserLogin, Token, UserRole, UserUpdate,
    Candidate, CandidateCreate, CandidateUpdate, CandidateStatus, SeniorityLevel,
    ResumeUpload, ParseStatus, ResumeFile, PreviousCompany, RecruiterNote, AIClassification,
    Industry, FunctionalArea, JobProfile, CandidateMatch, SearchQuery, ActivityLog,
    DuplicateSuggestionModel, SavedSearch, IndustryCreate, FunctionalAreaCreate,
    Job, JobCreate, JobUpdate, JobStatus as JobStatusEnum, CandidateMatchResult, JobMatchResponse,
    AssignmentCreate, ExportFormat, ExportSourceType, ExportRequest,
    SmartFolder, SmartFolderCreate, SmartFolderUpdate, FolderType, FolderCategory,
    StatusChangeRequest, StatusChange, VALID_STATUS_TRANSITIONS, STATUS_COLORS
)
from validation_models import ValidationRecord, ValidationSummary
from auth import verify_password, get_password_hash, create_access_token, verify_token
from atlas_service import atlas_service
from document_parser import DocumentParser
from storage_service import storage_service, init_storage
from duplicate_detector import DuplicateDetector, DuplicateSuggestion
from embedding_service import embedding_service
from hybrid_search_service import HybridSearchService
from text_utils import normalize_for_search
from background_processor import background_processor, JobStatus
from job_matching_service import JobMatchingService
from user_service import UserService
from assignment_service import AssignmentService
from export_service import ExportService
from smart_folder_service import SmartFolderService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize services
duplicate_detector = DuplicateDetector(db)
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
    
    # Log activity
    await db.activity_logs.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "action": "candidate_created",
        "entity_type": "candidate",
        "entity_id": candidate_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
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
    """Add note to candidate"""
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
    "other": "Otro"
}

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
    
    # ===== ETAPA 4: DETECCIÓN DE DUPLICADOS =====
    duplicates = []
    try:
        duplicates = await duplicate_detector.detect_duplicates(parsed_data)
    except Exception as e:
        logger.error(f"Error detecting duplicates: {str(e)}")
        warnings.append("Error en detección de duplicados")
    
    # Si hay duplicado de alta confianza, retornar para revisión
    if duplicates and max(d['confidence'] for d in duplicates) >= 0.90:
        result.status = "duplicate_detected"
        result.stage_reached = ProcessingStage.DUPLICATE_DETECTION
        result.processing_time_ms = int((time.time() - start_time) * 1000)
        
        response = result.to_response()
        response["duplicates"] = duplicates
        response["parsed_data"] = parsed_data
        response["message"] = "Se detectaron posibles duplicados. Por favor revisa antes de continuar."
        return response
    
    # ===== ETAPA 5: CREAR/ACTUALIZAR CANDIDATO =====
    if not candidate_id:
        candidate_id = str(uuid.uuid4())
        result.candidate_id = candidate_id
        result.stage_reached = ProcessingStage.AI_CLASSIFICATION
        
        # Crear objeto candidato con datos parseados
        try:
            candidate = Candidate(
                id=candidate_id,
                full_name=parsed_data.get('full_name', f"Candidato - {file.filename}"),
                email=parsed_data.get('email'),
                phone=parsed_data.get('phone'),
                city=parsed_data.get('city'),
                state=parsed_data.get('state'),
                country=parsed_data.get('country', 'México'),
                linkedin_url=parsed_data.get('linkedin_url'),
                current_company=parsed_data.get('current_company'),
                current_title=parsed_data.get('current_title'),
                years_experience=parsed_data.get('years_experience'),
                skills=parsed_data.get('skills', []),
                languages=parsed_data.get('languages', []),
                previous_companies=[PreviousCompany(**pc) for pc in parsed_data.get('previous_companies', []) if isinstance(pc, dict)],
                source="CV Upload",
                created_by=current_user.id
            )
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
            
            # Guardar sugerencias de duplicados si hay
            if duplicates:
                await DuplicateSuggestion.create_suggestion(
                    db, candidate_id, duplicates, current_user.id
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
    
    response = result.to_response()
    response["parsed_data"] = parsed_data
    response["has_low_confidence_duplicates"] = len(duplicates) > 0 and max(d['confidence'] for d in duplicates) < 0.90 if duplicates else False
    
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
    
    job.progress = 25
    job.current_stage = "ai_parsing"
    
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
    
    job.progress = 40
    job.current_stage = "duplicate_detection"
    
    # 3. Detección de duplicados
    duplicates = []
    try:
        duplicates = await duplicate_detector.detect_duplicates(parsed_data)
    except Exception as e:
        result["warnings"].append("Error en detección de duplicados")
    
    # Si hay duplicado de alta confianza, marcar pero continuar
    if duplicates and max(d['confidence'] for d in duplicates) >= 0.90:
        result["warnings"].append(f"Posible duplicado detectado (confianza >= 90%)")
    
    job.progress = 50
    job.current_stage = "creating_candidate"
    
    # 4. Crear candidato
    candidate_id = str(uuid.uuid4())
    
    try:
        candidate = Candidate(
            id=candidate_id,
            full_name=parsed_data.get('full_name', f"Candidato - {file_name}"),
            email=parsed_data.get('email'),
            phone=parsed_data.get('phone'),
            city=parsed_data.get('city'),
            state=parsed_data.get('state'),
            country=parsed_data.get('country', 'México'),
            linkedin_url=parsed_data.get('linkedin_url'),
            current_company=parsed_data.get('current_company'),
            current_title=parsed_data.get('current_title'),
            years_experience=parsed_data.get('years_experience'),
            skills=parsed_data.get('skills', []),
            languages=parsed_data.get('languages', []),
            previous_companies=[PreviousCompany(**pc) for pc in parsed_data.get('previous_companies', []) if isinstance(pc, dict)],
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
    
    # 5. Clasificación AI
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
        result["errors"].append({
            "type": "ai_classification_failed",
            "stage": "ai_classification",
            "message": str(e),
            "recoverable": True
        })
    
    # Generar resumen
    try:
        if extracted_text and len(extracted_text.strip()) >= 50:
            summary = await atlas_service.generate_summary(parsed_data, extracted_text)
            candidate.ai_summary = summary
    except Exception as e:
        result["warnings"].append("Resumen AI no generado")
    
    job.progress = 75
    job.current_stage = "storage"
    
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
    
    job.progress = 85
    job.current_stage = "embedding_generation"
    
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
    
    job.progress = 95
    job.current_stage = "database_save"
    
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
    """Approve Atlas classification and apply to candidate"""
    candidate_doc = await db.candidates.find_one({"id": candidate_id}, {"_id": 0})
    
    if not candidate_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidato no encontrado"
        )
    
    if not candidate_doc.get('ai_classification'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No hay clasificación de Atlas disponible"
        )
    
    ai_class = candidate_doc['ai_classification']
    
    # Apply classification
    await db.candidates.update_one(
        {"id": candidate_id},
        {
            "$set": {
                "industry": ai_class.get('industry'),
                "functional_area": ai_class.get('functional_area'),
                "seniority": ai_class.get('seniority'),
                "tags": ai_class.get('suggested_tags', []),
                "ai_classification.approved_by_recruiter": True,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    return {"message": "Clasificación de Atlas aprobada y aplicada"}


# ============= DASHBOARD & ANALYTICS ROUTES =============

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    """Get dashboard statistics"""
    
    total_candidates = await db.candidates.count_documents({})
    
    # Candidates this month
    from datetime import timedelta
    month_ago = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    new_this_month = await db.candidates.count_documents({
        "created_at": {"$gte": month_ago}
    })
    
    # By status
    by_status = {}
    for status in CandidateStatus:
        count = await db.candidates.count_documents({"status": status.value})
        by_status[status.value] = count
    
    # By industry (top 5)
    industry_pipeline = [
        {"$match": {"industry": {"$ne": None}}},
        {"$group": {"_id": "$industry", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    industry_results = await db.candidates.aggregate(industry_pipeline).to_list(5)
    by_industry = {item['_id']: item['count'] for item in industry_results}
    
    # By functional area (top 5)
    area_pipeline = [
        {"$match": {"functional_area": {"$ne": None}}},
        {"$group": {"_id": "$functional_area", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 5}
    ]
    area_results = await db.candidates.aggregate(area_pipeline).to_list(5)
    by_functional_area = {item['_id']: item['count'] for item in area_results}
    
    # By seniority
    by_seniority = {}
    for seniority in SeniorityLevel:
        count = await db.candidates.count_documents({"seniority": seniority.value})
        by_seniority[seniority.value] = count
    
    return {
        "total_candidates": total_candidates,
        "new_this_month": new_this_month,
        "by_status": by_status,
        "by_industry": by_industry,
        "by_functional_area": by_functional_area,
        "by_seniority": by_seniority
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
    source_candidate_id: str  # El que se va a eliminar
    target_candidate_id: str  # El que se va a mantener
    merge_notes: bool = True  # Combinar notas
    merge_history: bool = True  # Combinar historial de status


@api_router.post("/candidates/merge")
async def merge_candidates(
    request: MergeRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Merge de candidatos duplicados (solo Admin).
    Mantiene el target, transfiere datos del source, y marca el source como eliminado.
    """
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo Admin puede fusionar candidatos")
    
    source = await db.candidates.find_one({"id": request.source_candidate_id}, {"_id": 0})
    target = await db.candidates.find_one({"id": request.target_candidate_id}, {"_id": 0})
    
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato fuente no encontrado")
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidato destino no encontrado")
    
    now = datetime.now(timezone.utc).isoformat()
    updates = {"updated_at": now}
    push_updates = {}
    
    # Transferir notas
    if request.merge_notes and source.get("notes"):
        push_updates["notes"] = {"$each": source["notes"]}
    
    # Transferir historial de status
    if request.merge_history and source.get("status_history"):
        push_updates["status_history"] = {"$each": source["status_history"]}
    
    # Transferir archivos de CV si el target no tiene
    if source.get("resume_files") and not target.get("resume_files"):
        updates["resume_files"] = source["resume_files"]
    
    # Agregar nota del merge
    merge_note = {
        "note": f"[MERGE] Información transferida del candidato duplicado: {source.get('full_name')} (ID: {request.source_candidate_id})",
        "created_by": current_user.name,
        "created_at": now
    }
    if "notes" not in push_updates:
        push_updates["notes"] = {"$each": [merge_note]}
    else:
        push_updates["notes"]["$each"].append(merge_note)
    
    # Actualizar target
    update_ops = {"$set": updates}
    if push_updates:
        update_ops["$push"] = push_updates
    
    await db.candidates.update_one({"id": request.target_candidate_id}, update_ops)
    
    # Soft delete source
    await db.candidates.update_one(
        {"id": request.source_candidate_id},
        {"$set": {
            "is_deleted": True,
            "deleted_at": now,
            "deleted_by": current_user.id,
            "deleted_by_name": current_user.name,
            "merged_into": request.target_candidate_id,
            "updated_at": now
        }}
    )
    
    logger.info(f"Candidates merged: {request.source_candidate_id} -> {request.target_candidate_id} by {current_user.email}")
    
    return {
        "message": "Candidatos fusionados exitosamente",
        "target_candidate_id": request.target_candidate_id,
        "source_candidate_id": request.source_candidate_id,
        "source_deleted": True,
        "merged_by": current_user.name
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
        assignment = await db.candidate_assignments.find_one({
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
            client_name=client_name
        )
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
