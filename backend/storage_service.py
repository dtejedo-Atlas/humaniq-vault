import os
import requests
import uuid
from pathlib import Path
from dotenv import load_dotenv
import logging

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

logger = logging.getLogger(__name__)

STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get('EMERGENT_LLM_KEY')
APP_NAME = "atlas-talent-vault"

# Module-level storage key (reusable)
storage_key = None

def init_storage():
    """Initialize storage connection. Call once at startup."""
    global storage_key
    if storage_key:
        return storage_key
    
    try:
        resp = requests.post(
            f"{STORAGE_URL}/init",
            json={"emergent_key": EMERGENT_KEY},
            timeout=30
        )
        resp.raise_for_status()
        storage_key = resp.json()["storage_key"]
        logger.info("✓ Storage initialized successfully")
        return storage_key
    except Exception as e:
        logger.error(f"Storage initialization failed: {str(e)}")
        raise

class StorageService:
    @staticmethod
    def put_object(path: str, data: bytes, content_type: str) -> dict:
        """Upload file to object storage"""
        key = init_storage()
        
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120
        )
        resp.raise_for_status()
        return resp.json()
    
    @staticmethod
    def get_object(path: str) -> tuple:
        """Download file from object storage"""
        key = init_storage()
        
        resp = requests.get(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key},
            timeout=60
        )
        resp.raise_for_status()
        return resp.content, resp.headers.get("Content-Type", "application/octet-stream")
    
    @staticmethod
    def upload_resume(file_data: bytes, candidate_id: str, filename: str, content_type: str) -> dict:
        """Upload resume to storage with proper path structure"""
        ext = filename.split(".")[-1] if "." in filename else "bin"
        file_uuid = str(uuid.uuid4())
        storage_path = f"{APP_NAME}/resumes/{candidate_id}/{file_uuid}.{ext}"
        
        result = StorageService.put_object(storage_path, file_data, content_type)
        
        return {
            "storage_path": result["path"],
            "original_filename": filename,
            "content_type": content_type,
            "size": result.get("size", len(file_data)),
            "file_uuid": file_uuid
        }

storage_service = StorageService()