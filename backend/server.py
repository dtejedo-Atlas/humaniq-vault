from fastapi import FastAPI, APIRouter, HTTPException, status, Depends, UploadFile, File, Form, Header
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
    Industry, FunctionalArea, JobProfile, CandidateMatch, SearchQuery, ActivityLog
)
from auth import verify_password, get_password_hash, create_access_token, verify_token
from atlas_service import atlas_service
from document_parser import DocumentParser

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create uploads directory
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


async def require_role(required_roles: List[UserRole]):
    """Decorator to check user role"""
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
    """Upload resume and optionally create/link candidate"""
    
    # Validate file type
    if not file.filename.lower().endswith(('.pdf', '.docx', '.doc')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos PDF y DOCX"
        )
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    file_ext = Path(file.filename).suffix
    safe_filename = f"{file_id}{file_ext}"
    
    # Create candidate directory if needed
    if candidate_id:
        upload_path = UPLOAD_DIR / candidate_id
    else:
        upload_path = UPLOAD_DIR / "pending"
    
    upload_path.mkdir(parents=True, exist_ok=True)
    file_path = upload_path / safe_filename
    
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Extract text from document
    try:
        extracted_text = DocumentParser.extract_text(str(file_path))
    except Exception as e:
        logger.error(f"Error extracting text: {str(e)}")
        extracted_text = ""
    
    # Parse resume with Atlas AI
    try:
        parsed_data = await atlas_service.parse_resume(extracted_text)
    except Exception as e:
        logger.error(f"Error parsing resume with Atlas: {str(e)}")
        parsed_data = {"full_name": "Desconocido", "error": str(e)}
    
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
        
        # Save candidate
        candidate_doc = candidate.model_dump()
        candidate_doc['created_at'] = candidate_doc['created_at'].isoformat()
        candidate_doc['updated_at'] = candidate_doc['updated_at'].isoformat()
        
        for note in candidate_doc.get('notes', []):
            note['created_at'] = note['created_at'].isoformat()
        
        if candidate_doc.get('ai_classification'):
            candidate_doc['ai_classification']['classified_at'] = candidate_doc['ai_classification']['classified_at'].isoformat()
        
        await db.candidates.insert_one(candidate_doc)
        
        # Move file to candidate folder
        new_path = UPLOAD_DIR / candidate_id
        new_path.mkdir(parents=True, exist_ok=True)
        new_file_path = new_path / safe_filename
        shutil.move(str(file_path), str(new_file_path))
        file_path = new_file_path
    
    # Add resume file to candidate
    resume_file = ResumeFile(
        file_name=file.filename,
        file_path=str(file_path.relative_to(ROOT_DIR)),
        file_type=file_ext,
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
        "message": "CV procesado exitosamente",
        "candidate_id": candidate_id,
        "parsed_data": parsed_data
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
