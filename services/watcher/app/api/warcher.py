from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, status, Query
from app.deps import get_watch_service, get_current_user
from app.schemas.watcher import WatcherCreate, WatcherUpdate, WatchResponseSchema
from app.services.watch_service import WatchService

router = APIRouter(prefix="/watches", tags=["Watches"])

@router.post("/", response_model=WatchResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_watch(
    data: WatcherCreate,
    watch_service: WatchService = Depends(get_watch_service),
    current_user = Depends(get_current_user)
):
    return await watch_service.create_watch(data=data, user_id=str(current_user.id))

@router.get("/", response_model=List[WatchResponseSchema])
async def get_watches(
    is_active: Optional[bool] = Query(None),
    asset: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    watch_service: WatchService = Depends(get_watch_service),
    current_user = Depends(get_current_user)
):
    return await watch_service.get_user_watches(
        user_id=str(current_user.id),
        is_active=is_active,
        asset=asset,
        limit=limit,
        offset=offset
    )

@router.get("/{id}", response_model=WatchResponseSchema)
async def get_watch_details(
    id: UUID,
    watch_service: WatchService = Depends(get_watch_service),
    current_user = Depends(get_current_user)
):
    return await watch_service.get_watch_or_404(watch_id=id, user_id=str(current_user.id))

@router.patch("/{id}", response_model=WatchResponseSchema)
async def update_watch(
    id: UUID,
    data: WatcherUpdate,
    watch_service: WatchService = Depends(get_watch_service),
    current_user = Depends(get_current_user)
):
    return await watch_service.update_watch(watch_id=id, user_id=str(current_user.id), data=data)

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watch(
    id: UUID,
    watch_service: WatchService = Depends(get_watch_service),
    current_user = Depends(get_current_user)
):
    await watch_service.delete_watch(watch_id=id, user_id=str(current_user.id))
    return None

@router.get("/coins/search")
async def search_coins(
    q: str = Query(..., min_length=1),
    watch_service: WatchService = Depends(get_watch_service),
    current_user = Depends(get_current_user)
):
    return await watch_service.search_coins(query=q)