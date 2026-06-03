import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException

from app.services.watch_service import WatchService
from app.models.watch import Watch, ConditionType


# ─── helpers ─────────────────────────────────────────────────────

def make_quota(max_watches=10, interval=60, plan="free"):
    quota = MagicMock()
    quota.max_watches = max_watches
    quota.check_interval_seconds = interval
    quota.plan = plan
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

    # Patch at the import location used inside watch_service
    with patch("app.tasks.check_watch") as mock_task:
        mock_task.apply_async = MagicMock()
        result = await service.create_watch(data, str(uuid4()))

    assert result == created
    service.repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_create_watch_schedules_eager_check(service):
    """An immediate check_watch task must be dispatched after creation."""
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
        await service.create_watch(data, str(uuid4()))
        mock_task.apply_async.assert_called_once()
        _, kwargs = mock_task.apply_async.call_args
        assert kwargs.get("queue") == "watcher_high"


@pytest.mark.asyncio
async def test_create_watch_eager_check_failure_does_not_raise(service):
    """If the eager dispatch fails, create_watch must still return the watch."""
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
        mock_task.apply_async = MagicMock(side_effect=Exception("broker down"))
        result = await service.create_watch(data, str(uuid4()))

    assert result == created


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
async def test_create_watch_quota_exactly_at_limit_rejected(service):
    """active_count == max_watches should be rejected (>=)."""
    service.auth_client.get_user_quota.return_value = make_quota(max_watches=5)
    service.repo.count_active_by_user.return_value = 5

    data = MagicMock()
    data.asset = "bitcoin"

    with pytest.raises(HTTPException) as exc:
        await service.create_watch(data, str(uuid4()))

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_watch_one_below_quota_allowed(service):
    service.auth_client.get_user_quota.return_value = make_quota(max_watches=5)
    service.repo.count_active_by_user.return_value = 4
    service.coingecko_client.validate_asset.return_value = True
    service.repo.create.return_value = make_watch()

    data = MagicMock()
    data.asset = "bitcoin"
    data.name = "BTC > 1000"
    data.condition_type = ConditionType.price_above
    data.threshold = Decimal("1000")

    with patch("app.tasks.check_watch") as mock_task:
        mock_task.apply_async = MagicMock()
        result = await service.create_watch(data, str(uuid4()))

    assert result is not None


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
    assert "fakecoin" in exc.value.detail


@pytest.mark.asyncio
async def test_create_watch_auth_service_down_propagates(service):
    service.auth_client.get_user_quota.side_effect = HTTPException(status_code=503, detail="auth down")

    data = MagicMock()
    data.asset = "bitcoin"

    with pytest.raises(HTTPException) as exc:
        await service.create_watch(data, str(uuid4()))

    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_create_watch_interval_from_quota(service):
    """interval_seconds on the created watch must come from the quota."""
    service.auth_client.get_user_quota.return_value = make_quota(interval=30)
    service.repo.count_active_by_user.return_value = 0
    service.coingecko_client.validate_asset.return_value = True

    captured_watch = {}

    async def capture_create(watch):
        captured_watch["watch"] = watch
        return watch

    service.repo.create.side_effect = capture_create

    data = MagicMock()
    data.asset = "bitcoin"
    data.name = "BTC > 1000"
    data.condition_type = ConditionType.price_above
    data.threshold = Decimal("1000")

    with patch("app.tasks.check_watch") as mock_task:
        mock_task.apply_async = MagicMock()
        await service.create_watch(data, str(uuid4()))

    assert captured_watch["watch"].interval_seconds == 30


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


@pytest.mark.asyncio
async def test_get_watch_or_404_wrong_user_returns_404(service):
    """Watch exists but belongs to a different user — must return 404, not 403."""
    service.repo.get_by_id_and_user.return_value = None  # repo already filters by user

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


@pytest.mark.asyncio
async def test_delete_watch_not_found_raises_404(service):
    service.repo.get_by_id_and_user.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.delete_watch(uuid4(), str(uuid4()))

    assert exc.value.status_code == 404
    service.repo.delete.assert_not_called()


# ─── update_watch ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_watch_threshold(service):
    watch = make_watch()
    service.repo.get_by_id_and_user.return_value = watch
    service.repo.update.return_value = watch

    data = MagicMock()
    data.model_dump.return_value = {"threshold": Decimal("2000")}

    result = await service.update_watch(watch.id, str(watch.user_id), data)
    assert result == watch
    assert watch.threshold == Decimal("2000")


@pytest.mark.asyncio
async def test_update_watch_multiple_fields(service):
    watch = make_watch()
    service.repo.get_by_id_and_user.return_value = watch
    service.repo.update.return_value = watch

    data = MagicMock()
    data.model_dump.return_value = {
        "threshold": Decimal("5000"),
        "is_active": False,
        "name": "BTC > 5000",
    }

    await service.update_watch(watch.id, str(watch.user_id), data)

    assert watch.threshold == Decimal("5000")
    assert watch.is_active is False
    assert watch.name == "BTC > 5000"


@pytest.mark.asyncio
async def test_update_watch_not_found_raises_404(service):
    service.repo.get_by_id_and_user.return_value = None

    data = MagicMock()
    data.model_dump.return_value = {"threshold": Decimal("2000")}

    with pytest.raises(HTTPException) as exc:
        await service.update_watch(uuid4(), str(uuid4()), data)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_update_watch_empty_payload_no_changes(service):
    """model_dump with exclude_unset=True returns {} — watch must be unchanged."""
    watch = make_watch()
    original_threshold = watch.threshold
    service.repo.get_by_id_and_user.return_value = watch
    service.repo.update.return_value = watch

    data = MagicMock()
    data.model_dump.return_value = {}

    await service.update_watch(watch.id, str(watch.user_id), data)

    assert watch.threshold == original_threshold


# ─── get_user_watches ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_user_watches_delegates_to_repo(service):
    watches = [make_watch(), make_watch()]
    service.repo.get_multi.return_value = watches
    user_id = str(uuid4())

    result = await service.get_user_watches(
        user_id=user_id, is_active=True, asset="bitcoin", limit=10, offset=0
    )

    assert result == watches
    service.repo.get_multi.assert_called_once_with(
        user_id=user_id, is_active=True, asset="bitcoin", limit=10, offset=0
    )


@pytest.mark.asyncio
async def test_get_user_watches_empty(service):
    service.repo.get_multi.return_value = []
    result = await service.get_user_watches(
        user_id=str(uuid4()), is_active=None, asset=None, limit=10, offset=0
    )
    assert result == []


# ─── search_coins ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_coins_delegates_to_coingecko(service):
    coins = [{"id": "bitcoin", "name": "Bitcoin"}]
    service.coingecko_client.search_coins.return_value = coins

    result = await service.search_coins("bit")

    assert result == coins
    service.coingecko_client.search_coins.assert_called_once_with("bit")


@pytest.mark.asyncio
async def test_search_coins_propagates_exception(service):
    service.coingecko_client.search_coins.side_effect = Exception("CoinGecko down")

    with pytest.raises(Exception, match="CoinGecko down"):
        await service.search_coins("bitcoin")