import uuid
from fastapi import APIRouter, Depends, Query

from app.deps import get_watcher_service, get_current_user_id
from app.schemas.watcher import WatcherCreate, WatcherUpdate, WatchResponseSchema
from app.services.watcher import WatcherService

router = APIRouter(prefix="/watcher", tags=["Watcher"])


@router.post("/watches", response_model=WatchResponseSchema)
async def create_watch(
    payload: WatcherCreate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: WatcherService = Depends(get_watcher_service),
):
    return await service.create_watch(user_id, payload)


@router.get("/watches", response_model=list[WatchResponseSchema])
async def list_watches(
    user_id: uuid.UUID = Depends(get_current_user_id),
    asset: str | None = None,
    is_active: bool | None = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    service: WatcherService = Depends(get_watcher_service),
):
    return await service.list_watches(user_id, asset, is_active, limit, offset)


@router.get("/watches/{watch_id}", response_model=WatchResponseSchema)
async def get_watch(
    watch_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: WatcherService = Depends(get_watcher_service),
):
    return await service.get_watch(user_id, watch_id)


@router.patch("/watches/{watch_id}", response_model=WatchResponseSchema)
async def update_watch(
    watch_id: uuid.UUID,
    payload: WatcherUpdate,
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: WatcherService = Depends(get_watcher_service),
):
    return await service.update_watch(user_id, watch_id, payload)


@router.delete("/watches/{watch_id}")
async def delete_watch(
    watch_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: WatcherService = Depends(get_watcher_service),
):
    return await service.delete_watch(user_id, watch_id)


@router.get("/watches/{watch_id}/alerts")
async def watch_alerts(
    watch_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    service: WatcherService = Depends(get_watcher_service),
):
    return await service.get_alerts(user_id, watch_id)


@router.get("/coins/search")
async def search_coins(
    q: str,
    service: WatcherService = Depends(get_watcher_service),
):
    return await service.search_coins(q)