"""Cuota de lotes: los leases de lotes terminados, fallidos o huérfanos se liberan siempre.

Usa una base local aislada (no toca Atlas).
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException

sys.path.insert(0, '/app/backend')
import ai_workload_limits as limits  # noqa: E402
from background_processor import BackgroundProcessor, JobStatus  # noqa: E402

DB_NAME = 'test_batch_quota_selfheal'
USER = 'user-selfheal'


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def seed_batch(db, batch_id, *, submission_complete=True, job_statuses=()):
    await db.upload_batches.insert_one({
        'batch_id': batch_id, 'user_id': USER, 'total_files': len(job_statuses) or 1,
        'jobs': [], 'submission_complete': submission_complete, 'quota_managed': True,
        'created_at': now_iso(),
    })
    for index, status in enumerate(job_statuses):
        await db.upload_jobs.insert_one({
            'job_id': f'{batch_id}-{index}', 'batch_id': batch_id, 'file_name': f'cv{index}.pdf',
            'file_size': 10, 'status': status, 'progress': 0, 'current_stage': 'queued',
            'errors': [], 'warnings': [], 'created_at': now_iso(), 'updated_at': now_iso(),
        })


async def live_batches(db):
    doc = await db.ai_user_workloads.find_one({'_id': USER}) or {}
    now = datetime.now(timezone.utc)
    out = []
    for entry in doc.get('batches') or []:
        expires = entry['expires_at']
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires > now:
            out.append(entry['batch_id'])
    return out


async def age_entries(db):
    """Envejece las reservas para saltar la gracia de huérfanos."""
    doc = await db.ai_user_workloads.find_one({'_id': USER})
    old = datetime.now(timezone.utc) - timedelta(seconds=limits.ORPHAN_GRACE_SECONDS + 60)
    for index, _ in enumerate(doc.get('batches') or []):
        await db.ai_user_workloads.update_one({'_id': USER}, {'$set': {f'batches.{index}.reserved_at': old}})


async def main():
    client = AsyncIOMotorClient(os.environ.get('TEST_MONGO_URL', 'mongodb://localhost:27017'))
    await client.drop_database(DB_NAME)
    db = client[DB_NAME]
    results = []

    # 1. Tres lotes terminados ocupan la cuota; el cuarto se admite tras el barrido automático.
    for index in range(3):
        batch_id = f'done-{index}'
        await limits.reserve_batch(db, USER, batch_id, 'upload', 2)
        await seed_batch(db, batch_id, job_statuses=('completed', 'failed'))
    await age_entries(db)
    assert len(await live_batches(db)) == 3
    await limits.reserve_batch(db, USER, 'nuevo-1', 'upload', 3)
    live = await live_batches(db)
    results.append(('cuota liberada para lotes terminados', 'nuevo-1' in live and len(live) == 1))

    # 2. Un lote con trabajo pendiente real sí bloquea (429) y no se libera por error.
    await client.drop_database(DB_NAME)
    db = client[DB_NAME]
    for index in range(3):
        batch_id = f'busy-{index}'
        await limits.reserve_batch(db, USER, batch_id, 'upload', 2)
        await seed_batch(db, batch_id, job_statuses=('pending', 'processing'))
    await age_entries(db)
    try:
        await limits.reserve_batch(db, USER, 'nuevo-2', 'upload', 1)
        results.append(('429 con lotes realmente en proceso', False))
    except HTTPException as error:
        results.append(('429 con lotes realmente en proceso', error.status_code == 429))

    # 3. Lote huérfano (sin documento de lote) se libera.
    await client.drop_database(DB_NAME)
    db = client[DB_NAME]
    await limits.reserve_batch(db, USER, 'huerfano', 'upload', 1)
    await age_entries(db)
    await limits.release_idle_batches(db, USER)
    results.append(('lote huérfano sin documento liberado', await live_batches(db) == []))

    # 4. get_batch_status libera la cuota de un lote ya terminado y marca huérfanos.
    await client.drop_database(DB_NAME)
    db = client[DB_NAME]
    processor = BackgroundProcessor()
    processor.db = db
    await limits.reserve_batch(db, USER, 'poll-1', 'upload', 1)
    await seed_batch(db, 'poll-1', job_statuses=('completed',))
    status = await processor.get_batch_status('poll-1')
    results.append(('polling libera cuota de lote terminado',
                    status['is_complete'] and await live_batches(db) == []))

    # 5. Un job cuyos bytes ya no están en memoria queda fallido (no pendiente eterno).
    await limits.reserve_batch(db, USER, 'poll-2', 'upload', 1)
    await seed_batch(db, 'poll-2', job_statuses=('pending',))
    await processor._mark_orphan_job('poll-2-0')
    doc = await db.upload_jobs.find_one({'job_id': 'poll-2-0'})
    results.append(('job huérfano marcado fallido y cuota liberada',
                    doc['status'] == JobStatus.FAILED.value and await live_batches(db) == []))

    # 6. El heartbeat no revive jobs que no están en memoria de esta réplica.
    await db.upload_jobs.update_one({'job_id': 'poll-2-0'}, {'$set': {'status': 'pending'}})
    stamp = (await db.upload_jobs.find_one({'job_id': 'poll-2-0'}))['updated_at']
    limits.HEARTBEAT_SECONDS = 0.2
    task = asyncio.create_task(limits._batch_heartbeat(db, USER, 'poll-2', 'upload', processor.owned_job_ids))
    await asyncio.sleep(0.6)
    task.cancel()
    after = (await db.upload_jobs.find_one({'job_id': 'poll-2-0'}))['updated_at']
    results.append(('heartbeat no revive jobs huérfanos', stamp == after))

    await client.drop_database(DB_NAME)
    for name, ok in results:
        print(('PASS  ' if ok else 'FAIL  ') + name)
    print('\nTOTAL', sum(1 for _, ok in results if ok), '/', len(results))
    return 0 if all(ok for _, ok in results) else 1


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
