"""Per-user CV admission and shared Mongo leases, across upload and recheck workers."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

CVS_PER_USER = 2
QUEUED_BATCHES_PER_USER = 2
FILES_PER_BATCH = 50
LEASE_SECONDS = 600
HEARTBEAT_SECONDS = 20
_heartbeats = {}


def _now():
    return datetime.now(timezone.utc)


def _live(field, now):
    return {'$filter': {'input': {'$ifNull': [f'${field}', []]}, 'as': 'entry', 'cond': {'$gt': ['$$entry.expires_at', now]}}}


def quota_error():
    return HTTPException(429, 'Límite de procesamiento: 2 CVs simultáneos y 2 lotes en espera por usuario. Espera a que termine un lote; se admiten hasta 50 CVs por lote.', headers={'Retry-After': '30'})


async def _batch_heartbeat(db, user_id, batch_id, kind):
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            result = await db.ai_user_workloads.update_one({'_id': user_id, 'batches.batch_id': batch_id},
                {'$set': {'batches.$.expires_at': _now() + timedelta(seconds=LEASE_SECONDS)}})
            if not result.matched_count:
                break
            if kind == 'upload':
                await db.upload_jobs.update_many({'batch_id': batch_id, 'status': 'pending'}, {'$set': {'updated_at': _now().isoformat()}})
    except (asyncio.CancelledError, Exception):
        return


async def reserve_batch(db, user_id, batch_id, kind, count):
    if not 1 <= count <= FILES_PER_BATCH:
        raise HTTPException(400, 'Máximo 50 CVs por lote')
    try:
        await db.ai_user_workloads.update_one({'_id': user_id}, {'$setOnInsert': {'batches': [], 'leases': []}}, upsert=True)
    except DuplicateKeyError:
        pass
    now = _now()
    live = _live('batches', now)
    existing = await db.ai_user_workloads.find_one({'_id': user_id, 'batches': {'$elemMatch': {'batch_id': batch_id, 'expires_at': {'$gt': now}}}}, {'_id': 0, 'batches.batch_id': 1})
    if not existing:
        item = {'batch_id': batch_id, 'kind': kind, 'expires_at': now + timedelta(seconds=LEASE_SECONDS)}
        result = await db.ai_user_workloads.find_one_and_update(
            {'_id': user_id, '$expr': {'$and': [
                {'$lt': [{'$size': live}, 1 + QUEUED_BATCHES_PER_USER]},
                {'$not': [{'$in': [batch_id, {'$map': {'input': live, 'as': 'batch', 'in': '$$batch.batch_id'}}]}]},
            ]}},
            [{'$set': {'batches': {'$concatArrays': [live, [item]]}, 'leases': _live('leases', now)}}],
            projection={'_id': 0, 'batches.batch_id': 1}, return_document=ReturnDocument.AFTER)
        if result is None:
            concurrent = await db.ai_user_workloads.find_one({'_id': user_id, 'batches': {'$elemMatch': {'batch_id': batch_id, 'expires_at': {'$gt': now}}}}, {'_id': 0, 'batches.batch_id': 1})
            if not concurrent:
                raise quota_error()
    key = (id(db.client), db.name, user_id, batch_id)
    if key not in _heartbeats or _heartbeats[key].done():
        task = asyncio.create_task(_batch_heartbeat(db, user_id, batch_id, kind))
        _heartbeats[key] = task
        task.add_done_callback(lambda finished: _heartbeats.pop(key, None) if _heartbeats.get(key) is finished else None)


async def release_batch(db, user_id, batch_id):
    task = _heartbeats.pop((id(db.client), db.name, user_id, batch_id), None)
    if task:
        task.cancel()
    await db.ai_user_workloads.update_one({'_id': user_id}, {'$pull': {'batches': {'batch_id': batch_id}, 'leases': {'batch_id': batch_id}}})


class CVLease:
    def __init__(self, db, user_id, token):
        self.db, self.user_id, self.token = db, user_id, token
        self.heartbeat = asyncio.create_task(self.renew())

    async def renew(self):
        try:
            while True:
                await asyncio.sleep(HEARTBEAT_SECONDS)
                result = await self.db.ai_user_workloads.update_one({'_id': self.user_id, 'leases.token': self.token},
                    {'$set': {'leases.$.expires_at': _now() + timedelta(seconds=LEASE_SECONDS)}})
                if not result.matched_count:
                    break
        except (asyncio.CancelledError, Exception):
            return

    async def release(self):
        self.heartbeat.cancel()
        await self.db.ai_user_workloads.update_one({'_id': self.user_id}, {'$pull': {'leases': {'token': self.token}}})

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.release()


async def try_cv_slot(db, user_id, batch_id):
    now, token = _now(), str(uuid4())
    batches, leases = _live('batches', now), _live('leases', now)
    first_batch = {'$arrayElemAt': [{'$map': {'input': batches, 'as': 'batch', 'in': '$$batch.batch_id'}}, 0]}
    result = await db.ai_user_workloads.find_one_and_update(
        {'_id': user_id, '$expr': {'$and': [{'$eq': [first_batch, batch_id]}, {'$lt': [{'$size': leases}, CVS_PER_USER]}]}},
        [{'$set': {'leases': {'$concatArrays': [leases, [{'token': token, 'batch_id': batch_id, 'expires_at': now + timedelta(seconds=LEASE_SECONDS)}]]}}}],
        projection={'_id': 0, 'leases.token': 1}, return_document=ReturnDocument.AFTER)
    return CVLease(db, user_id, token) if result else None


async def wait_cv_slot(db, user_id, batch_id):
    while True:
        lease = await try_cv_slot(db, user_id, batch_id)
        if lease:
            return lease
        await asyncio.sleep(.5)


@asynccontextmanager
async def immediate_cv_slot(db, user_id):
    batch_id = str(uuid4())
    await reserve_batch(db, user_id, batch_id, 'interactive', 1)
    try:
        lease = await try_cv_slot(db, user_id, batch_id)
        if not lease:
            raise quota_error()
        async with lease:
            yield
    finally:
        await release_batch(db, user_id, batch_id)