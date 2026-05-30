import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from uuid import uuid4
 
from fastapi import HTTPException
 
from app.services.watch_service import WatchService
from app.models.watch import Watch, ConditionType
 
 
def make_quota(max_watches=10, interval=60):
    quota = MagicMock()
    quota.max_watches = max_watches
    quota.check_interval_seconds = interval
    return quota
 
 
def make_watch(**kwargs):
    defaults = dict(
        id=uuid4(),
        user_id=uuid4(),
        name="BTC > 1000",
        asset="bitcoin",
        condition_type=ConditionType.price_above,
        threshold=Decimal("1000"),
        interval_seconds=60,
        is_active=True,
        cooldown_seconds=1800,
        last_triggered_at=None,
    )
    defaults.update(kwargs)
    w = MagicMock(spec=Watch)
    for k, v in defaults.items():
        setattr(w, k, v)
    w.__dict__.update(defaults)
    return w
 
 
@pytest.fixture
def service():
    repo = AsyncMock()
    auth_client = AsyncMock()
    coingecko_client = AsyncMock()
    return WatchService(repo=repo, auth_client=auth_client, coingecko_client=coingecko_client)
 
 
# ─── create_watch ────────────────────────────────────────────────
 
@pytest.mark.asyncio
async def test_create_watch_success(service):
    service.auth_client.get_user_quota.return_value = make_quota()
    service.repo.count_active_by_user.return_value = 0
    service.coingecko_client.validate_asset.return_value = True
 
    created = make_watch()
    service.repo.create.return_value = created
 
    data = MagicMock()
    data.asset = "bitcoin"
    data.name = "BTC > 1000"
    data.condition_type = ConditionType.price_above
    data.threshold = Decimal("1000")
 
    with patch("app.tasks.check_watch") as mock_task:
        mock_task.apply_async = MagicMock()
        result = await service.create_watch(data, str(uuid4()))
 
    assert result == created
    service.repo.create.assert_called_once()
 
 
@pytest.mark.asyncio
async def test_create_watch_quota_exceeded(service):
    service.auth_client.get_user_quota.return_value = make_quota(max_watches=2)
    service.repo.count_active_by_user.return_value = 2
 
    data = MagicMock()
    data.asset = "bitcoin"
 
    with pytest.raises(HTTPException) as exc:
        await service.create_watch(data, str(uuid4()))
 
    assert exc.value.status_code == 403
 
 
@pytest.mark.asyncio
async def test_create_watch_invalid_asset(service):
    service.auth_client.get_user_quota.return_value = make_quota()
    service.repo.count_active_by_user.return_value = 0
    service.coingecko_client.validate_asset.return_value = False
 
    data = MagicMock()
    data.asset = "fakecoin"
 
    with pytest.raises(HTTPException) as exc:
        await service.create_watch(data, str(uuid4()))
 
    assert exc.value.status_code == 422
 
 
# ─── get_watch_or_404 ────────────────────────────────────────────
 
@pytest.mark.asyncio
async def test_get_watch_or_404_found(service):
    watch = make_watch()
    service.repo.get_by_id_and_user.return_value = watch
 
    result = await service.get_watch_or_404(watch.id, str(watch.user_id))
    assert result == watch
 
 
@pytest.mark.asyncio
async def test_get_watch_or_404_not_found(service):
    service.repo.get_by_id_and_user.return_value = None
 
    with pytest.raises(HTTPException) as exc:
        await service.get_watch_or_404(uuid4(), str(uuid4()))
 
    assert exc.value.status_code == 404
 
 
# ─── delete_watch ────────────────────────────────────────────────
 
@pytest.mark.asyncio
async def test_delete_watch_soft_delete(service):
    watch = make_watch()
    service.repo.get_by_id_and_user.return_value = watch
 
    await service.delete_watch(watch.id, str(watch.user_id))
 
    service.repo.delete.assert_called_once_with(watch, hard_delete=False)
 
 
# ─── update_watch ────────────────────────────────────────────────
 
@pytest.mark.asyncio
async def test_update_watch(service):
    watch = make_watch()
    service.repo.get_by_id_and_user.return_value = watch
    service.repo.update.return_value = watch
 
    data = MagicMock()
    data.model_dump.return_value = {"threshold": Decimal("2000")}
 
    result = await service.update_watch(watch.id, str(watch.user_id), data)
    assert result == watch
    assert watch.threshold == Decimal("2000")
