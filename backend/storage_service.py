import os
import requests
import uuid
import time
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


class ResumeStorageError(Exception):
    """A remote upload was not confirmed; never represents a successful local fallback."""
    def __init__(self, attempts):
        self.attempts = attempts
        super().__init__('No se pudo confirmar el guardado remoto del CV original. Vuelve a subir el archivo.')

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
    def put_object(path: str, data: bytes, content_type: str, timeout=120) -> dict:
        """Upload file to object storage"""
        key = init_storage()
        
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=timeout
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
        
        # Keep one key across retries: a lost acknowledgement must not create several objects.
        for attempt in range(1, 4):
            try:
                result = StorageService.put_object(storage_path, file_data, content_type, timeout=(10, 30))
                if not isinstance(result.get('path'), str) or not result['path'].startswith(f'{APP_NAME}/'):
                    raise ValueError('Storage returned an invalid object reference')
                break
            except Exception as error:
                code = getattr(getattr(error, 'response', None), 'status_code', None)
                logger.warning('Remote CV upload attempt %s/3 failed for candidate %s (%s, HTTP %s)',
                               attempt, candidate_id, type(error).__name__, code)
                # Authentication, access and quota errors cannot be repaired by retries.
                if attempt == 3 or code in (400, 401, 402, 403, 439):
                    logger.error('Remote CV upload not confirmed for candidate %s; no local file saved', candidate_id)
                    raise ResumeStorageError(attempt) from error
                time.sleep(0.5 * attempt)
        
        return {
            "storage_path": result["path"],
            "original_filename": filename,
            "content_type": content_type,
            "size": result.get("size", len(file_data)),
            "file_uuid": file_uuid
        }

storage_service = StorageService()