"""
Sistema de Procesamiento en Background para CVs
===============================================

Permite subir múltiples CVs y procesarlos de forma asíncrona.
El ESTADO de lotes/jobs se persiste en MongoDB (colecciones upload_batches /
upload_jobs) para que cualquier réplica pueda responder el polling y un
reinicio del pod no pierda la información del lote.

Los bytes de los archivos permanecen en memoria de la réplica que recibió el
POST (solo esa réplica procesa). Si el pod muere a media carga, los jobs
huérfanos se marcan como fallidos vía detección de staleness en el polling.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
from pydantic import BaseModel
import uuid
import logging

logger = logging.getLogger(__name__)

# Umbrales de staleness (job sin heartbeat → se asume réplica muerta)
STALE_PROCESSING_MINUTES = 10   # un job en proceso actualiza updated_at en cada etapa
STALE_PENDING_MINUTES = 12      # tras 12 min en cola sin arrancar, se asume réplica muerta


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
    stage_timings: Dict[str, int] = {}

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
            "retry_count": self.retry_count,
            "stage_timings": self.stage_timings
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BackgroundProcessor:
    """
    Gestor de procesamiento en background.

    Cola de trabajo local (asyncio.Queue con bytes en memoria) + estado
    persistido en MongoDB para visibilidad multi-réplica.
    """

    def __init__(self, max_concurrent: int = 3):
        self.db = None  # inyectado por server.py al arrancar
        self.jobs: Dict[str, ProcessingJob] = {}   # objetos vivos de ESTA réplica
        self.file_data: Dict[str, bytes] = {}
        self.file_metadata: Dict[str, Dict] = {}
        self.queue: asyncio.Queue = None
        self.max_concurrent = max_concurrent
        self.workers_running = False

    async def initialize(self):
        if self.queue is None:
            self.queue = asyncio.Queue()
            logger.info(f"Background processor initialized with {self.max_concurrent} workers")

    async def persist_job(self, job: ProcessingJob):
        """Escribe (upsert) el estado del job en MongoDB. Heartbeat = updated_at."""
        try:
            doc = job.to_dict()
            doc["updated_at"] = _now_iso()
            await self.db.upload_jobs.update_one(
                {"job_id": job.job_id}, {"$set": doc}, upsert=True
            )
        except Exception as e:
            logger.warning(f"No se pudo persistir job {job.job_id}: {e}")

    async def start_workers(self, process_func):
        if self.workers_running:
            return

        self.workers_running = True
        self._process_func = process_func

        for i in range(self.max_concurrent):
            asyncio.create_task(self._worker(i))

        logger.info(f"Started {self.max_concurrent} background workers")

    async def _worker(self, worker_id: int):
        logger.info(f"Worker {worker_id} started")

        while self.workers_running:
            try:
                try:
                    job_id = await asyncio.wait_for(self.queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    continue

                job = self.jobs.get(job_id)
                if not job or job.status == JobStatus.CANCELLED:
                    self.queue.task_done()
                    continue

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

                    await self.persist_job(job)

                    if job_id in self.file_data:
                        del self.file_data[job_id]
                    if job_id in self.file_metadata:
                        del self.file_metadata[job_id]

                    self.queue.task_done()

            except Exception as e:
                logger.error(f"Worker {worker_id} error: {str(e)}")
                await asyncio.sleep(1)

    async def _process_job(self, job: ProcessingJob):
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        await self.persist_job(job)

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

        if self._process_func:
            result = await self._process_func(
                job=job,
                file_data=file_data,
                file_metadata=file_metadata
            )

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

    async def create_batch(self, user_id: str, file_count: int) -> BatchUpload:
        """Crear un nuevo lote (persistido en MongoDB)"""
        batch = BatchUpload(
            batch_id=str(uuid.uuid4()),
            user_id=user_id,
            total_files=file_count
        )
        await self.db.upload_batches.insert_one(batch.to_dict())
        return batch

    async def add_job(
        self,
        batch_id: str,
        file_name: str,
        file_data: bytes,
        content_type: str,
        user_id: str
    ) -> ProcessingJob:
        """Agregar un job a la cola (estado persistido en MongoDB)"""
        job_id = str(uuid.uuid4())

        job = ProcessingJob(
            job_id=job_id,
            batch_id=batch_id,
            file_name=file_name,
            file_size=len(file_data)
        )

        self.jobs[job_id] = job
        self.file_data[job_id] = file_data
        self.file_metadata[job_id] = {
            "content_type": content_type,
            "user_id": user_id,
            "file_name": file_name
        }

        await self.persist_job(job)
        await self.db.upload_batches.update_one(
            {"batch_id": batch_id}, {"$push": {"jobs": job_id}}
        )

        await self.queue.put(job_id)

        logger.info(f"Job {job_id} added to queue: {file_name}")
        return job

    async def get_job(self, job_id: str) -> Optional[Dict]:
        """Obtener estado de un job desde MongoDB (funciona en cualquier réplica)"""
        return await self.db.upload_jobs.find_one({"job_id": job_id}, {"_id": 0})

    async def _mark_stale_jobs(self, job_docs: List[Dict]) -> List[Dict]:
        """Marca como fallidos los jobs huérfanos de una réplica muerta (sin heartbeat)."""
        now = datetime.now(timezone.utc)
        updated = []
        for doc in job_docs:
            status = doc.get("status")
            if status not in (JobStatus.PENDING.value, JobStatus.PROCESSING.value):
                updated.append(doc)
                continue
            try:
                ref = doc.get("updated_at") or doc.get("created_at")
                last = datetime.fromisoformat(ref)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
                age_min = (now - last).total_seconds() / 60
            except Exception:
                age_min = 0
            limit = STALE_PROCESSING_MINUTES if status == JobStatus.PROCESSING.value else STALE_PENDING_MINUTES
            if age_min > limit:
                doc["status"] = JobStatus.FAILED.value
                doc["current_stage"] = "failed"
                doc["errors"] = (doc.get("errors") or []) + [{
                    "type": "server_restart",
                    "stage": doc.get("current_stage", "unknown"),
                    "message": "El servidor se reinició durante el procesamiento. Vuelve a subir este archivo.",
                    "recoverable": True
                }]
                doc["completed_at"] = _now_iso()
                await self.db.upload_jobs.update_one(
                    {"job_id": doc["job_id"]},
                    {"$set": {
                        "status": doc["status"],
                        "current_stage": doc["current_stage"],
                        "errors": doc["errors"],
                        "completed_at": doc["completed_at"],
                        "updated_at": _now_iso(),
                    }}
                )
                logger.warning(f"Job {doc['job_id']} marcado como fallido por staleness ({status}, {int(age_min)} min sin heartbeat)")
            updated.append(doc)
        return updated

    async def get_batch_status(self, batch_id: str) -> Optional[Dict]:
        """Estado del lote leído desde MongoDB (cualquier réplica puede responder)"""
        batch = await self.db.upload_batches.find_one({"batch_id": batch_id}, {"_id": 0})
        if not batch:
            return None

        job_docs = await self.db.upload_jobs.find(
            {"batch_id": batch_id}, {"_id": 0}
        ).to_list(length=200)

        job_docs = await self._mark_stale_jobs(job_docs)

        stats = {
            "pending": sum(1 for j in job_docs if j.get("status") == JobStatus.PENDING.value),
            "processing": sum(1 for j in job_docs if j.get("status") == JobStatus.PROCESSING.value),
            "completed": sum(1 for j in job_docs if j.get("status") == JobStatus.COMPLETED.value),
            "partial": sum(1 for j in job_docs if j.get("status") == JobStatus.PARTIAL.value),
            "failed": sum(1 for j in job_docs if j.get("status") in (JobStatus.FAILED.value, JobStatus.CANCELLED.value)),
        }

        return {
            "batch_id": batch_id,
            "total_files": batch.get("total_files"),
            "stats": stats,
            "is_complete": stats["pending"] == 0 and stats["processing"] == 0,
            "jobs": job_docs,
            "avg_stage_timings_ms": self._avg_stage_timings(job_docs),
            "created_at": batch.get("created_at")
        }

    @staticmethod
    def _avg_stage_timings(job_docs) -> Dict[str, int]:
        """Promedio de duración por etapa entre jobs con timings"""
        sums, counts = {}, {}
        for j in job_docs:
            if not j:
                continue
            for stage, ms in (j.get("stage_timings") or {}).items():
                sums[stage] = sums.get(stage, 0) + ms
                counts[stage] = counts.get(stage, 0) + 1
        return {s: int(sums[s] / counts[s]) for s in sums}

    async def retry_job(self, job_id: str) -> bool:
        """Reintentar un job fallido (solo si los bytes siguen en memoria de esta réplica)"""
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.status not in [JobStatus.FAILED, JobStatus.PARTIAL]:
            return False

        if job_id not in self.file_data:
            logger.warning(f"Cannot retry job {job_id}: file data no longer in memory")
            return False

        job.status = JobStatus.PENDING
        job.progress = 0
        job.current_stage = "queued"
        job.errors = []
        job.warnings = []
        job.started_at = None
        job.completed_at = None
        job.retry_count += 1

        await self.persist_job(job)
        await self.queue.put(job_id)

        logger.info(f"Job {job_id} re-queued for retry (attempt {job.retry_count})")
        return True

    async def cancel_job(self, job_id: str) -> bool:
        """Cancelar un job pendiente"""
        job = self.jobs.get(job_id)
        if not job:
            return False

        if job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            await self.persist_job(job)
            return True

        return False

    def get_queue_stats(self) -> Dict:
        """Estadísticas de la cola local de esta réplica"""
        return {
            "queue_size": self.queue.qsize() if self.queue else 0,
            "total_jobs": len(self.jobs),
            "workers_running": self.workers_running
        }

    def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Limpiar objetos de jobs antiguos de memoria (el histórico queda en MongoDB)"""
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
# max_concurrent=3: límite seguro para 1Gi RAM en producción (evita OOM en lotes grandes)
background_processor = BackgroundProcessor(max_concurrent=3)
