from fastapi import APIRouter, Depends
from pydantic import BaseModel
from models import User
from cv_recheck_service import RecheckRequest, RecheckBatchResult, enqueue_rechecks, batch_status


class RecheckStarted(BaseModel):
    batch_id: str
    total: int


class LatestRecheck(BaseModel):
    batch_id: str | None = None


def create_recheck_router(auth_dependency, database, admin_dependency):
    router = APIRouter(prefix='/api/atlas/classifications')

    @router.post('/recheck', status_code=202, response_model=RecheckStarted)
    async def start(body: RecheckRequest, user: User = Depends(admin_dependency)):
        return await enqueue_rechecks(database(), body.candidate_ids, user.id)

    @router.get('/rechecks/latest', response_model=LatestRecheck)
    async def latest(user: User = Depends(auth_dependency)):
        item = await database().cv_recheck_batches.find_one({'user_id': user.id}, {'_id': 0, 'batch_id': 1}, sort=[('created_at', -1)])
        return LatestRecheck(batch_id=item['batch_id'] if item else None)

    @router.get('/rechecks/{batch_id}', response_model=RecheckBatchResult)
    async def progress(batch_id: str, user: User = Depends(auth_dependency)):
        return await batch_status(database(), batch_id, user.id)

    return router