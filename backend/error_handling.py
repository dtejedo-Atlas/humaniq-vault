"""
Sistema de Manejo de Errores para Upload de CVs
===============================================

Proporciona errores detallados y trazables para cada etapa del procesamiento.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class ProcessingStage(str, Enum):
    """Etapas del procesamiento de CV"""
    UPLOAD = "upload"
    STORAGE = "storage"
    TEXT_EXTRACTION = "text_extraction"
    AI_PARSING = "ai_parsing"
    AI_CLASSIFICATION = "ai_classification"
    EMBEDDING_GENERATION = "embedding_generation"
    DUPLICATE_DETECTION = "duplicate_detection"
    DATABASE_SAVE = "database_save"
    COMPLETED = "completed"


class ErrorType(str, Enum):
    """Tipos de error con mensajes amigables"""
    # Errores de archivo
    UNSUPPORTED_FORMAT = "unsupported_format"
    FILE_CORRUPTED = "file_corrupted"
    FILE_TOO_LARGE = "file_too_large"
    FILE_EMPTY = "file_empty"
    
    # Errores de extracción
    NO_TEXT_EXTRACTABLE = "no_text_extractable"
    PDF_SCANNED_NO_OCR = "pdf_scanned_no_ocr"
    ENCODING_ERROR = "encoding_error"
    
    # Errores de AI
    AI_PARSING_FAILED = "ai_parsing_failed"
    AI_CLASSIFICATION_FAILED = "ai_classification_failed"
    AI_TIMEOUT = "ai_timeout"
    AI_INVALID_RESPONSE = "ai_invalid_response"
    
    # Errores de embedding
    EMBEDDING_GENERATION_FAILED = "embedding_generation_failed"
    EMBEDDING_API_ERROR = "embedding_api_error"
    
    # Errores de storage
    STORAGE_UPLOAD_FAILED = "storage_upload_failed"
    
    # Errores de base de datos
    DATABASE_SAVE_FAILED = "database_save_failed"
    VALIDATION_ERROR = "validation_error"
    
    # Genérico
    UNKNOWN_ERROR = "unknown_error"


# Mensajes amigables para el usuario
ERROR_MESSAGES = {
    ErrorType.UNSUPPORTED_FORMAT: "Formato de archivo no soportado. Solo se permiten PDF y DOCX.",
    ErrorType.FILE_CORRUPTED: "El archivo parece estar corrupto o dañado.",
    ErrorType.FILE_TOO_LARGE: "El archivo excede el tamaño máximo permitido (10MB).",
    ErrorType.FILE_EMPTY: "El archivo está vacío o no tiene contenido.",
    ErrorType.NO_TEXT_EXTRACTABLE: "No se pudo extraer texto del archivo. Verifica que no esté protegido.",
    ErrorType.PDF_SCANNED_NO_OCR: "El PDF parece ser una imagen escaneada. Se requiere OCR para procesarlo.",
    ErrorType.ENCODING_ERROR: "Error de codificación de caracteres en el archivo.",
    ErrorType.AI_PARSING_FAILED: "El sistema de IA no pudo extraer información del CV.",
    ErrorType.AI_CLASSIFICATION_FAILED: "Error al clasificar el perfil con IA.",
    ErrorType.AI_TIMEOUT: "Tiempo de espera agotado al procesar con IA. Intenta de nuevo.",
    ErrorType.AI_INVALID_RESPONSE: "La IA devolvió una respuesta inválida.",
    ErrorType.EMBEDDING_GENERATION_FAILED: "Error al generar vector de búsqueda. El candidato se guardó pero sin búsqueda semántica.",
    ErrorType.EMBEDDING_API_ERROR: "Error de API al generar embeddings. El candidato se guardó correctamente.",
    ErrorType.STORAGE_UPLOAD_FAILED: "Error al guardar el archivo. Se usó almacenamiento local.",
    ErrorType.DATABASE_SAVE_FAILED: "Error al guardar en base de datos.",
    ErrorType.VALIDATION_ERROR: "Datos incompletos o inválidos extraídos del CV.",
    ErrorType.UNKNOWN_ERROR: "Error desconocido durante el procesamiento.",
}


class ProcessingError(BaseModel):
    """Modelo de error detallado"""
    error_type: ErrorType
    stage: ProcessingStage
    message: str  # Mensaje amigable para usuario
    technical_details: Optional[str] = None  # Detalles técnicos para debugging
    recoverable: bool = False  # Si se puede reintentar
    timestamp: datetime = None
    
    def __init__(self, **data):
        if data.get('timestamp') is None:
            data['timestamp'] = datetime.now(timezone.utc)
        super().__init__(**data)


class ProcessingResult(BaseModel):
    """Resultado del procesamiento de un archivo"""
    file_name: str
    file_id: Optional[str] = None
    candidate_id: Optional[str] = None
    status: str  # "success", "partial_success", "failed"
    stage_reached: ProcessingStage
    errors: List[ProcessingError] = []
    warnings: List[str] = []
    processing_time_ms: Optional[int] = None
    
    # Datos extraídos (si hubo éxito parcial)
    extracted_name: Optional[str] = None
    extracted_email: Optional[str] = None
    
    def add_error(self, error_type: ErrorType, stage: ProcessingStage, 
                  technical_details: str = None, recoverable: bool = False):
        """Agregar un error al resultado"""
        error = ProcessingError(
            error_type=error_type,
            stage=stage,
            message=ERROR_MESSAGES.get(error_type, "Error desconocido"),
            technical_details=technical_details,
            recoverable=recoverable
        )
        self.errors.append(error)
        logger.error(f"[{self.file_name}] {stage.value}: {error.message} - {technical_details}")
    
    def add_warning(self, message: str):
        """Agregar una advertencia (no crítica)"""
        self.warnings.append(message)
        logger.warning(f"[{self.file_name}] Warning: {message}")
    
    def to_response(self) -> Dict[str, Any]:
        """Convertir a respuesta de API"""
        return {
            "file_name": self.file_name,
            "file_id": self.file_id,
            "candidate_id": self.candidate_id,
            "status": self.status,
            "stage_reached": self.stage_reached.value,
            "errors": [
                {
                    "type": e.error_type.value,
                    "stage": e.stage.value,
                    "message": e.message,
                    "recoverable": e.recoverable,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None
                }
                for e in self.errors
            ],
            "warnings": self.warnings,
            "processing_time_ms": self.processing_time_ms,
            "extracted_name": self.extracted_name,
            "extracted_email": self.extracted_email
        }


class BatchProcessingResult(BaseModel):
    """Resultado de procesamiento en lote"""
    total_files: int
    successful: int
    partial_success: int
    failed: int
    results: List[ProcessingResult]
    
    def to_response(self) -> Dict[str, Any]:
        """Convertir a respuesta de API"""
        return {
            "summary": {
                "total_files": self.total_files,
                "successful": self.successful,
                "partial_success": self.partial_success,
                "failed": self.failed,
                "success_rate": f"{((self.successful + self.partial_success) / self.total_files * 100):.1f}%" if self.total_files > 0 else "0%"
            },
            "results": [r.to_response() for r in self.results]
        }


def detect_error_type(exception: Exception, stage: ProcessingStage) -> ErrorType:
    """Detectar tipo de error basado en la excepción y etapa"""
    error_str = str(exception).lower()
    
    # Errores de formato
    if "formato" in error_str or "unsupported" in error_str or "msword" in error_str:
        return ErrorType.UNSUPPORTED_FORMAT
    
    # Errores de archivo corrupto
    if "corrupt" in error_str or "invalid" in error_str or "damaged" in error_str:
        return ErrorType.FILE_CORRUPTED
    
    # PDF escaneado
    if "no text" in error_str or ("pdf" in error_str and "empty" in error_str):
        return ErrorType.PDF_SCANNED_NO_OCR
    
    # Errores de encoding
    if "encoding" in error_str or "decode" in error_str or "utf" in error_str:
        return ErrorType.ENCODING_ERROR
    
    # Errores de timeout
    if "timeout" in error_str or "timed out" in error_str:
        return ErrorType.AI_TIMEOUT
    
    # Errores de API
    if "401" in error_str or "api key" in error_str or "unauthorized" in error_str:
        return ErrorType.EMBEDDING_API_ERROR
    
    # Errores de validación
    if "validation" in error_str or "pydantic" in error_str:
        return ErrorType.VALIDATION_ERROR
    
    # Por etapa si no se detecta específico
    stage_defaults = {
        ProcessingStage.TEXT_EXTRACTION: ErrorType.NO_TEXT_EXTRACTABLE,
        ProcessingStage.AI_PARSING: ErrorType.AI_PARSING_FAILED,
        ProcessingStage.AI_CLASSIFICATION: ErrorType.AI_CLASSIFICATION_FAILED,
        ProcessingStage.EMBEDDING_GENERATION: ErrorType.EMBEDDING_GENERATION_FAILED,
        ProcessingStage.STORAGE: ErrorType.STORAGE_UPLOAD_FAILED,
        ProcessingStage.DATABASE_SAVE: ErrorType.DATABASE_SAVE_FAILED,
    }
    
    return stage_defaults.get(stage, ErrorType.UNKNOWN_ERROR)
