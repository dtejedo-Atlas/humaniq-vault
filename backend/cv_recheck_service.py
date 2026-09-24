"""In-place CV rechecks. Durable jobs/results; original files and history untouched."""
import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from pydantic import BaseModel, Field
from fastapi import HTTPException
from document_parser import DocumentParser
from pdf_extraction import EXTRACTION_VERSION
from storage_service import storage_service
from classification_refinement import second_pass, SECOND_PASS_VERSION, MANUAL_MESSAGE
from ai_workload_limits import reserve_batch, release_batch, wait_cv_slot, FILES_PER_BATCH

_tasks = set()
_parallel = asyncio.Semaphore(2)
ROOT = Path(__file__).parent


class RecheckRequest(BaseModel):
    candidate_ids: list[str] = Field(min_length=1, max_length=FILES_PER_BATCH)


class RecheckJobResult(BaseModel):
    candidate_id: str
    name: str = ''
    status: str
    review_status: str | None = None
    message: str = ''
    confidence_score: float | None = None
    cache_hit: bool = False


class RecheckBatchResult(BaseModel):
    batch_id: str
    total: int
    completed: int
    failed: int
    is_complete: bool
    jobs: list[RecheckJobResult]


async def current_resume(db, candidate):
    version = await db.cv_versions.find_one({'candidate_id': candidate['id'], 'is_current': True, 'is_active': True}, {'_id': 0})
    if version and version.get('file_key'):
        return {'key': version['file_key'], 'type': version.get('file_type') or version.get('mime_type') or Path(version.get('file_name') or version['file_key']).suffix.lstrip('.'), 'version': version.get('id')}
    files = candidate.get('resume_files') or []
    if not files:
        raise ValueError('Este candidato no tiene un CV adjunto para revisar.')
    resume = max(enumerate(files), key=lambda item: (str(item[1].get('upload_date') or item[1].get('uploaded_at') or ''), item[0]))[1]
    return {'key': resume.get('file_path'), 'type': resume.get('file_type') or Path(resume.get('file_name') or '').suffix.lstrip('.'), 'version': resume.get('id')}


def download_original(reference):
    key = reference.get('key')
    if not key:
        raise ValueError('No se encontró la referencia al archivo original.')
    local = (ROOT / key).resolve()
    if local.is_relative_to((ROOT / 'uploads').resolve()) and local.is_file():
        return local.read_bytes()
    data, _ = storage_service.get_object(key)
    return data


async def recheck_candidate(db, cid):
    before = await db.candidates.find_one({'id': cid, 'is_deleted': {'$ne': True}}, {'_id': 0})
    if not before:
        raise ValueError('Candidato no encontrado.')
    old_ai = before.get('ai_classification') or {}
    if old_ai.get('approved_by_recruiter'):
        raise ValueError('La clasificación ya fue aprobada manualmente; no se sobrescribió.')
    reference = await current_resume(db, before)
    raw = await asyncio.to_thread(download_original, reference)
    file_hash = hashlib.sha256(raw).hexdigest()
    extraction_key = f'{EXTRACTION_VERSION}:{file_hash}'
    cached = await db.cv_text_extractions.find_one({'_id': extraction_key}, {'_id': 0})
    if cached:
        extraction = cached['extraction']
    else:
        try:
            extraction = await asyncio.to_thread(DocumentParser.extract_with_details, raw, reference['type'])
        except Exception:
            extraction = {'text': '', 'text_chars': 0, 'readable': False, 'pages': [], 'warnings': [MANUAL_MESSAGE], 'version': EXTRACTION_VERSION}
        await db.cv_text_extractions.update_one({'_id': extraction_key}, {'$set': {'extraction': extraction}}, upsert=True)
    result = await second_pass(db, extraction['text'], before.get('country') or 'México', retry_failed=True)
    manual = old_ai.get('manual_fields', {})
    updates = {key: manual[key] if key in manual else result.get(key) for key in ('industry', 'functional_area', 'seniority', 'years_experience')}
    if result['review_status'] == 'manual_capture':
        updates = {key: before.get(key) for key in updates}
    ai = {**old_ai, **{key: value for key, value in result.items() if key not in ('review_status', 'review_message', 'cache_hit')},
          **updates, 'manual_fields': manual, 'source': SECOND_PASS_VERSION, 'approved_by_recruiter': False,
          'classified_at': datetime.now(timezone.utc).isoformat()}
    if any(updates[key] is None for key in updates):
        ai['confidence_score'] = min(ai['confidence_score'], .74)
    status = result['review_status'] if result['review_status'] == 'manual_capture' else ('classified' if ai['confidence_score'] >= .75 else 'pending_review')
    updates.update({'ai_classification': ai, 'review_status': status, 'review_message': result.get('review_message', ''),
                    'cv_extraction': {key: value for key, value in extraction.items() if key != 'text'}, 'updated_at': datetime.now(timezone.utc).isoformat()})
    latest_source = await db.candidates.find_one({'id': cid, 'is_deleted': {'$ne': True}}, {'_id': 0, 'id': 1, 'resume_files': 1})
    if not latest_source or (await current_resume(db, latest_source)) != reference:
        raise ValueError('Cambió la versión activa del CV; no se aplicó el resultado anterior.')
    saved = await db.candidates.update_one({'id': cid, 'updated_at': before.get('updated_at'), 'resume_files': before.get('resume_files', []), 'is_deleted': {'$ne': True}}, {'$set': updates})
    if saved.matched_count != 1:
        latest = await db.candidates.find_one({'id': cid}, {'_id': 0, 'ai_classification.second_pass.cache_key': 1})
        if not result.get('second_pass') or ((latest or {}).get('ai_classification') or {}).get('second_pass', {}).get('cache_key') != result['second_pass']['cache_key']:
            raise ValueError('La ficha cambió durante la revisión. Se conservaron los cambios recientes.')
    return {'candidate_id': cid, 'name': before['full_name'], 'status': 'completed', 'review_status': status,
            'message': result.get('review_message', ''), 'confidence_score': ai['confidence_score'], 'cache_hit': result.get('cache_hit', False)}


async def _run_batch(db, batch_id):
    batch = await db.cv_recheck_batches.find_one({'batch_id': batch_id}, {'_id': 0})
    if not batch:
        return
    if batch.get('quota_managed'):
        await reserve_batch(db, batch['user_id'], batch_id, 'recheck', len(batch['candidate_ids']))
    await db.cv_recheck_batches.update_one({'batch_id': batch_id}, {'$set': {'status': 'processing'}})

    async def run(cid):
        lease = await wait_cv_slot(db, batch['user_id'], batch_id) if batch.get('quota_managed') else None
        async with _parallel:
            existing = await db.cv_recheck_jobs.find_one({'batch_id': batch_id, 'candidate_id': cid}, {'_id': 0})
            if existing and existing['status'] in ('completed', 'failed'):
                if lease:
                    await lease.release()
                return
            await db.cv_recheck_jobs.update_one({'batch_id': batch_id, 'candidate_id': cid}, {'$set': {'status': 'processing'}})
            try:
                result = await recheck_candidate(db, cid)
            except Exception as error:
                # Only intentional validation messages may reach the UI, not provider/storage exceptions.
                message = str(error) if isinstance(error, ValueError) else 'No se pudo completar la revisión. Los datos anteriores se conservan.'
                result = {'candidate_id': cid, 'status': 'failed', 'message': message}
            await db.cv_recheck_jobs.update_one({'batch_id': batch_id, 'candidate_id': cid}, {'$set': result})
            if lease:
                await lease.release()

    await asyncio.gather(*(run(cid) for cid in batch['candidate_ids']))
    await db.cv_recheck_batches.update_one({'batch_id': batch_id}, {'$set': {'status': 'completed'}})
    if batch.get('quota_managed'):
        await release_batch(db, batch['user_id'], batch_id)


def launch_batch(db, batch_id):
    task = asyncio.create_task(_run_batch(db, batch_id))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def enqueue_rechecks(db, ids, user_id):
    ids = list(dict.fromkeys(ids))
    batch_id = str(uuid4())
    await reserve_batch(db, user_id, batch_id, 'recheck', len(ids))
    try:
        await db.cv_recheck_batches.insert_one({'batch_id': batch_id, 'user_id': user_id, 'candidate_ids': ids, 'status': 'queued', 'quota_managed': True, 'created_at': datetime.now(timezone.utc).isoformat()})
        await db.cv_recheck_jobs.insert_many([{'batch_id': batch_id, 'candidate_id': cid, 'status': 'queued'} for cid in ids])
    except Exception:
        await release_batch(db, user_id, batch_id)
        raise
    launch_batch(db, batch_id)
    return {'batch_id': batch_id, 'total': len(ids)}


async def batch_status(db, batch_id, user_id):
    batch = await db.cv_recheck_batches.find_one({'batch_id': batch_id, 'user_id': user_id}, {'_id': 0})
    if not batch:
        raise HTTPException(404, 'Lote de revisión no encontrado.')
    jobs = [RecheckJobResult.model_validate(row) async for row in db.cv_recheck_jobs.find({'batch_id': batch_id}, {'_id': 0})]
    completed = sum(job.status == 'completed' for job in jobs)
    failed = sum(job.status == 'failed' for job in jobs)
    return RecheckBatchResult(batch_id=batch_id, total=len(batch['candidate_ids']), completed=completed, failed=failed,
                              is_complete=completed + failed == len(batch['candidate_ids']), jobs=jobs)