"""
Sistema de Procesamiento en Background para CVs
===============================================

Permite subir múltiples CVs y procesarlos de forma asíncrona,
mostrando el estado de cada archivo en tiempo real.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel
import uuid
import logging

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Estados posibles de un trabajo de procesamiento"""
    PENDING = "pending"          # En cola, esperando procesamiento
    PROCESSING = "processing"    # Procesándose activamente
    COMPLETED = "completed"      # Terminado exitosamente
    PARTIAL = "partial"          # Terminado con advertencias
    FAILED = "failed"            # Fallido
    CANCELLED = "cancelled"      # Cancelado por usuario


class ProcessingJob(BaseModel):
    """Representa un trabajo de procesamiento de CV"""
    job_id: str
    batch_id: str                # ID del lote al que pertenece
    file_name: str
    file_size: int
    status: JobStatus = JobStatus.PENDING
    progress: int = 0            # 0-100
    current_stage: str = "queued"
    candidate_id: Optional[str] = None
    errors: List[Dict] = []
    warnings: List[str] = []
    created_at: datetime = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None
    extracted_name: Optional[str] = None
    extracted_email: Optional[str] = None
    retry_count: int = 0
    
    def __init__(self, **data):
        if data.get('created_at') is None:
            data['created_at'] = datetime.now(timezone.utc)
        super().__init__(**data)
    
    def to_dict(self) -> Dict:
        return {
            "job_id": self.job_id,
            "batch_id": self.batch_id,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "status": self.status.value,
            "progress": self.progress,
            "current_stage": self.current_stage,
            "candidate_id": self.candidate_id,
            "errors": self.errors,
            "warnings": self.warnings,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "processing_time_ms": self.processing_time_ms,
            "extracted_name": self.extracted_name,
            "extracted_email": self.extracted_email,
            "retry_count": self.retry_count
        }


class BatchUpload(BaseModel):
    """Representa un lote de uploads"""
    batch_id: str
    user_id: str
    total_files: int
    jobs: List[str] = []          # Lista de job_ids
    created_at: datetime = None
    
    def __init__(self, **data):
        if data.get('created_at') is None:
            data['created_at'] = datetime.now(timezone.utc)
        super().__init__(**data)
    
    def to_dict(self) -> Dict:
        return {
            "batch_id": self.batch_id,
            "user_id": self.user_id,
            "total_files": self.total_files,
            "jobs": self.jobs,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class BackgroundProcessor:
    """
    Gestor de procesamiento en background.
    
    Mantiene una cola de trabajos y procesa CVs de forma asíncrona.
    """
    
    def __init__(self, max_concurrent: int = 3):
        self.jobs: Dict[str, ProcessingJob] = {}
        self.batches: Dict[str, BatchUpload] = {}
        self.file_data: Dict[str, bytes] = {}  # Almacén temporal de archivos
        self.file_metadata: Dict[str, Dict] = {}  # Metadata de archivos
        self.queue: asyncio.Queue = None
        self.max_concurrent = max_concurrent
        self.workers_running = False
        self._processing_lock = asyncio.Lock()
    
    async def initialize(self):
        """Inicializar la cola y workers"""
        if self.queue is None:
            self.queue = asyncio.Queue()
            logger.info(f"Background processor initialized with {self.max_concurrent} workers")
    
    async def start_workers(self, process_func):
        """Iniciar workers de procesamiento"""
        if self.workers_running:
            return
        
        self.workers_running = True
        self._process_func = process_func
        
        # Crear workers
        for i in range(self.max_concurrent):
            asyncio.create_task(self._worker(i))
        
        logger.info(f"Started {self.max_concurrent} background workers")
    
    async def _worker(self, worker_id: int):
        """Worker que procesa jobs de la cola"""
        logger.info(f"Worker {worker_id} started")
        
        while self.workers_running:
            try:
                # Esperar por un job (con timeout para permitir shutdown)
                try:
                    job_id = await asyncio.wait_for(self.queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    continue
                
                job = self.jobs.get(job_id)
                if not job or job.status == JobStatus.CANCELLED:
                    self.queue.task_done()
                    continue
                
                # Procesar el job
                logger.info(f"Worker {worker_id} processing job {job_id}: {job.file_name}")
                
                try:
                    await self._process_job(job)
                except Exception as e:
                    logger.error(f"Error processing job {job_id}: {str(e)}")
                    job.status = JobStatus.FAILED
                    job.errors.append({
                        "type": "worker_error",
                        "stage": job.current_stage,
                        "message": f"Error interno: {str(e)}"
                    })
                finally:
                    job.completed_at = datetime.now(timezone.utc)
                    if job.started_at:
                        job.processing_time_ms = int(
                            (job.completed_at - job.started_at).total_seconds() * 1000
                        )
                    
                    # Limpiar datos del archivo de memoria
                    if job_id in self.file_data:
                        del self.file_data[job_id]
                    if job_id in self.file_metadata:
                        del self.file_metadata[job_id]
                    
                    self.queue.task_done()
                    
            except Exception as e:
                logger.error(f"Worker {worker_id} error: {str(e)}")
                await asyncio.sleep(1)
    
    async def _process_job(self, job: ProcessingJob):
        """Procesar un job individual"""
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        
        # Obtener datos del archivo
        file_data = self.file_data.get(job.job_id)
        file_metadata = self.file_metadata.get(job.job_id, {})
        
        if not file_data:
            job.status = JobStatus.FAILED
            job.errors.append({
                "type": "file_not_found",
                "stage": "processing",
                "message": "Datos del archivo no encontrados en memoria"
            })
            return
        
        # Llamar a la función de procesamiento real
        if self._process_func:
            result = await self._process_func(
                job=job,
                file_data=file_data,
                file_metadata=file_metadata
            )
            
            # Actualizar job con resultado
            if result:
                job.candidate_id = result.get('candidate_id')
                job.extracted_name = result.get('extracted_name')
                job.extracted_email = result.get('extracted_email')
                job.errors = result.get('errors', [])
                job.warnings = result.get('warnings', [])
                
                if result.get('status') == 'success':
                    job.status = JobStatus.COMPLETED
                elif result.get('status') == 'partial_success':
                    job.status = JobStatus.PARTIAL
                else:
                    job.status = JobStatus.FAILED
    
    def create_batch(self, user_id: str, file_count: int) -> BatchUpload:
        """Crear un nuevo lote de uploads"""
        batch = BatchUpload(
            batch_id=str(uuid.uuid4()),
            user_id=user_id,
            total_files=file_count
        )
        self.batches[batch.batch_id] = batch
        return batch
    
    async def add_job(
        self, 
        batch_id: str, 
        file_name: str, 
        file_data: bytes,
        content_type: str,
        user_id: str
    ) -> ProcessingJob:
        """Agregar un job a la cola"""
        job_id = str(uuid.uuid4())
        
        job = ProcessingJob(
            job_id=job_id,
            batch_id=batch_id,
            file_name=file_name,
            file_size=len(file_data)
        )
        
        # Guardar job
        self.jobs[job_id] = job
        
        # Guardar datos del archivo temporalmente
        self.file_data[job_id] = file_data
        self.file_metadata[job_id] = {
            "content_type": content_type,
            "user_id": user_id,
            "file_name": file_name
        }
        
        # Agregar a batch
        if batch_id in self.batches:
            self.batches[batch_id].jobs.append(job_id)
        
        # Encolar para procesamiento
        await self.queue.put(job_id)
        
        logger.info(f"Job {job_id} added to queue: {file_name}")
        return job
    
    def get_job(self, job_id: str) -> Optional[ProcessingJob]:
        """Obtener estado de un job"""
        return self.jobs.get(job_id)
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict]:
        """Obtener estado de un lote completo"""
        batch = self.batches.get(batch_id)
        if not batch:
            return None
        
        jobs = [self.jobs.get(jid) for jid in batch.jobs if jid in self.jobs]
        
        stats = {
            "pending": sum(1 for j in jobs if j and j.status == JobStatus.PENDING),
            "processing": sum(1 for j in jobs if j and j.status == JobStatus.PROCESSING),
            "completed": sum(1 for j in jobs if j and j.status == JobStatus.COMPLETED),
            "partial": sum(1 for j in jobs if j and j.status == JobStatus.PARTIAL),
            "failed": sum(1 for j in jobs if j and j.status == JobStatus.FAILED),
        }
        
        return {
            "batch_id": batch_id,
            "total_files": batch.total_files,
            "stats": stats,
            "is_complete": stats["pending"] == 0 and stats["processing"] == 0,
            "jobs": [j.to_dict() for j in jobs if j],
            "created_at": batch.created_at.isoformat() if batch.created_at else None
        }
    
    async def retry_job(self, job_id: str) -> bool:
        """Reintentar un job fallido"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status not in [JobStatus.FAILED, JobStatus.PARTIAL]:
            return False
        
        # Verificar que aún tenemos los datos (si no, necesitamos re-upload)
        if job_id not in self.file_data:
            logger.warning(f"Cannot retry job {job_id}: file data no longer in memory")
            return False
        
        # Reset job para reintento
        job.status = JobStatus.PENDING
        job.progress = 0
        job.current_stage = "queued"
        job.errors = []
        job.warnings = []
        job.started_at = None
        job.completed_at = None
        job.retry_count += 1
        
        # Re-encolar
        await self.queue.put(job_id)
        
        logger.info(f"Job {job_id} re-queued for retry (attempt {job.retry_count})")
        return True
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancelar un job pendiente"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            return True
        
        return False
    
    def get_queue_stats(self) -> Dict:
        """Obtener estadísticas de la cola"""
        return {
            "queue_size": self.queue.qsize() if self.queue else 0,
            "total_jobs": len(self.jobs),
            "active_batches": len(self.batches),
            "workers_running": self.workers_running
        }
    
    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Limpiar jobs antiguos de memoria"""
        now = datetime.now(timezone.utc)
        to_delete = []
        
        for job_id, job in self.jobs.items():
            if job.completed_at:
                age = (now - job.completed_at).total_seconds() / 3600
                if age > max_age_hours:
                    to_delete.append(job_id)
        
        for job_id in to_delete:
            del self.jobs[job_id]
            if job_id in self.file_data:
                del self.file_data[job_id]
            if job_id in self.file_metadata:
                del self.file_metadata[job_id]
        
        logger.info(f"Cleaned up {len(to_delete)} old jobs")


# Instancia global del processor
background_processor = BackgroundProcessor(max_concurrent=3)
