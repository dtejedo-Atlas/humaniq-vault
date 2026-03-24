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
    User, UserCreate, UserLogin, Token, UserRole,
    Candidate, CandidateCreate, CandidateUpdate, CandidateStatus, SeniorityLevel,
    ResumeUpload, ParseStatus, ResumeFile, PreviousCompany, RecruiterNote, AIClassification,
    Industry, FunctionalArea, JobProfile, CandidateMatch, SearchQuery, ActivityLog,
    DuplicateSuggestionModel, SavedSearch, IndustryCreate, FunctionalAreaCreate
)
from auth import verify_password, get_password_hash, create_access_token, verify_token
from atlas_service import atlas_service
from document_parser import DocumentParser
from storage_service import storage_service, init_storage
from duplicate_detector import DuplicateDetector, DuplicateSuggestion
from embedding_service import embedding_service
from hybrid_search_service import HybridSearchService

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Initialize services
duplicate_detector = DuplicateDetector(db)
hybrid_search_service = HybridSearchService(db, embedding_service)

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
    current_user: User = Depends(get_current_user)
):
    """Get candidates list with filters"""
    query = {}
    
    if status:
        query['status'] = status
    if industry:
        query['industry'] = industry
    if functional_area:
        query['functional_area'] = functional_area
    if seniority:
        query['seniority'] = seniority
    if search:
        query['$or'] = [
            {'full_name': {'$regex': search, '$options': 'i'}},
            {'email': {'$regex': search, '$options': 'i'}},
            {'current_company': {'$regex': search, '$options': 'i'}},
            {'current_title': {'$regex': search, '$options': 'i'}}
        ]
    
    candidates = await db.candidates.find(query, {"_id": 0}).skip(skip).limit(limit).to_list(limit)
    
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


# ============= RESUME UPLOAD & PARSING ROUTES =============

@api_router.post("/candidates/upload-resume")
async def upload_resume(
    file: UploadFile = File(...),
    candidate_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Upload resume and optionally create/link candidate with duplicate detection"""
    
    # Validate file type
    if not file.filename.lower().endswith(('.pdf', '.docx', '.doc')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF y DOCX"
        )
    
    # Read file data
    file_data = await file.read()
    
    # Extract text from document
    try:
        extracted_text = DocumentParser.extract_text_from_bytes(file_data, file.content_type)
    except Exception as e:
        logger.error(f"Error extracting text: {str(e)}")
        extracted_text = ""
    
    # Parse resume with Atlas AI
    try:
        parsed_data = await atlas_service.parse_resume(extracted_text)
    except Exception as e:
        logger.error(f"Error parsing resume with Atlas: {str(e)}")
        parsed_data = {"full_name": "Desconocido", "error": str(e)}
    
    # DUPLICATE DETECTION
    duplicates = await duplicate_detector.detect_duplicates(parsed_data)
    
    # If high confidence duplicate found (>= 90%), return for review
    if duplicates and max(d['confidence'] for d in duplicates) >= 0.90:
        return {
            "status": "duplicate_detected",
            "duplicates": duplicates,
            "parsed_data": parsed_data,
            "message": "Se detectaron posibles duplicados. Por favor revisa antes de continuar."
        }
    
    # If no candidate_id provided, create new candidate
    if not candidate_id:
        candidate_id = str(uuid.uuid4())
        
        candidate = Candidate(
            id=candidate_id,
            full_name=parsed_data.get('full_name', 'Desconocido'),
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
            previous_companies=[PreviousCompany(**pc) for pc in parsed_data.get('previous_companies', [])],
            source="CV Upload",
            created_by=current_user.id
        )
        
        # Classify with Atlas
        try:
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
        
        # Generate summary with Atlas
        try:
            summary = await atlas_service.generate_summary(parsed_data, extracted_text)
            candidate.ai_summary = summary
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
        
        # Upload to Object Storage
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
        except Exception as e:
            logger.error(f"Error uploading to storage: {str(e)}")
            # Fallback to local storage
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
        
        # Generate embedding
        try:
            candidate_dict = candidate.model_dump()
            embedding = await embedding_service.generate_candidate_embedding(candidate_dict)
            candidate.embedding = embedding
            candidate.embedding_updated_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
        
        # Save candidate
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
        
        # Store duplicate suggestions (if any with lower confidence)
        if duplicates:
            await DuplicateSuggestion.create_suggestion(
                db, candidate_id, duplicates, current_user.id
            )
    
    else:
        # Adding resume to existing candidate
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
            # Fallback to local
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
        
        resume_dict = resume_file.model_dump()
        resume_dict['upload_date'] = resume_dict['upload_date'].isoformat()
        
        await db.candidates.update_one(
            {"id": candidate_id},
            {
                "$push": {"resume_files": resume_dict},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
            }
        )
    
    return {
        "status": "success",
        "message": "CV procesado exitosamente",
        "candidate_id": candidate_id,
        "parsed_data": parsed_data,
        "has_low_confidence_duplicates": len(duplicates) > 0 and max(d['confidence'] for d in duplicates) < 0.90 if duplicates else False
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
    
    return results


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
    """Get duplicate suggestions for a candidate"""
    suggestions = await db.duplicate_suggestions.find(
        {"new_candidate_id": candidate_id, "status": "pending"},
        {"_id": 0}
    ).to_list(10)
    
    return suggestions


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


# ============= ADMIN TAXONOMY CRUD ROUTES =============

@api_router.post("/admin/industries")
async def create_industry(
    industry_data: IndustryCreate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN]))
):
    """Create new industry (Super Admin only)"""
    industry_id = str(uuid.uuid4())
    
    industry = {
        "id": industry_id,
        "name_es": industry_data.name_es,
        "name_en": industry_data.name_en,
        "description": industry_data.description,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.industries.insert_one(industry)
    
    return {"message": "Industria creada", "industry_id": industry_id}


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
    area_id = str(uuid.uuid4())
    
    area = {
        "id": area_id,
        "name_es": area_data.name_es,
        "name_en": area_data.name_en,
        "description": area_data.description,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.functional_areas.insert_one(area)
    
    return {"message": "Área funcional creada", "area_id": area_id}


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


# ============= SEED DATA ROUTE =============

@api_router.post("/seed/initial-data")
async def seed_initial_data():
    """Seed initial taxonomy data"""
    
    # Check if already seeded
    existing_industries = await db.industries.count_documents({})
    if existing_industries > 0:
        return {"message": "Datos ya inicializados"}
    
    # Seed industries
    industries = [
        {"id": str(uuid.uuid4()), "name_es": "Manufactura", "name_en": "Manufacturing", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Bienes de Consumo", "name_en": "Consumer Goods", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Retail", "name_en": "Retail", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Logística y Cadena de Suministro", "name_en": "Logistics and Supply Chain", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Transporte", "name_en": "Transportation", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Farmacéutica", "name_en": "Pharmaceutical", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Construcción", "name_en": "Construction", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Bienes Raíces", "name_en": "Real Estate", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Servicios Financieros", "name_en": "Financial Services", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Tecnología", "name_en": "Technology", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Hospitalidad", "name_en": "Hospitality", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Servicios Industriales", "name_en": "Industrial Services", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Energía", "name_en": "Energy", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Automotriz", "name_en": "Automotive", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Alimentos y Bebidas", "name_en": "Food and Beverage", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Servicios Profesionales", "name_en": "Professional Services", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Salud", "name_en": "Healthcare", "created_at": datetime.now(timezone.utc).isoformat()},
    ]
    
    await db.industries.insert_many(industries)
    
    # Seed functional areas
    functional_areas = [
        {"id": str(uuid.uuid4()), "name_es": "Dirección General", "name_en": "General Management", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Operaciones", "name_en": "Operations", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Manufactura", "name_en": "Manufacturing", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Cadena de Suministro", "name_en": "Supply Chain", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Logística", "name_en": "Logistics", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Compras", "name_en": "Procurement", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Ventas", "name_en": "Sales", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Desarrollo de Negocio", "name_en": "Business Development", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Marketing", "name_en": "Marketing", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Finanzas", "name_en": "Finance", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Contabilidad", "name_en": "Accounting", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Recursos Humanos", "name_en": "Human Resources", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Adquisición de Talento", "name_en": "Talent Acquisition", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Ingeniería", "name_en": "Engineering", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Calidad", "name_en": "Quality", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Mantenimiento", "name_en": "Maintenance", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Tecnología de la Información", "name_en": "IT", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Legal", "name_en": "Legal", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Servicio al Cliente", "name_en": "Customer Service", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Gestión de Proyectos", "name_en": "Project Management", "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": str(uuid.uuid4()), "name_es": "Gestión de Construcción", "name_en": "Construction Management", "created_at": datetime.now(timezone.utc).isoformat()},
    ]
    
    await db.functional_areas.insert_many(functional_areas)
    
    return {
        "message": "Datos inicializados correctamente",
        "industries": len(industries),
        "functional_areas": len(functional_areas)
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
