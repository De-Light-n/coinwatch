import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch, call
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4


# ─── helpers ─────────────────────────────────────────────────────

def make_watch_row(**kwargs):
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "asset": "bitcoin",
        "condition_type": "price_above",
        "threshold": Decimal("1000"),
        "is_active": True,
        "cooldown_seconds": 1800,
        "interval_seconds": 60,
        "last_triggered_at": None,
    }
    defaults.update(kwargs)
    return defaults


# ─── condition evaluation ────────────────────────────────────────

def evaluate_condition(condition_type, current_price, threshold, prev_price=None):
    triggered = False
    current_value = current_price

    if condition_type == "price_above":
        triggered = current_price > threshold
    elif condition_type == "price_below":
        triggered = current_price < threshold
    elif condition_type == "percent_change":
        if prev_price and prev_price > 0:
            change = abs(current_price - prev_price) / prev_price * 100
            current_value = change
            triggered = change > threshold
    elif condition_type == "market_cap_rank":
        current_value = int(current_price)
        triggered = int(current_price) <= threshold

    return triggered, current_value


class TestConditionEvaluation:
    # ── price_above ───────────────────────────────────────────────
    def test_price_above_triggered(self):
        triggered, _ = evaluate_condition("price_above", 95000, Decimal("1000"))
        assert triggered is True

    def test_price_above_not_triggered(self):
        triggered, _ = evaluate_condition("price_above", 500, Decimal("1000"))
        assert triggered is False

    def test_price_above_equal_threshold_not_triggered(self):
        """Boundary: price == threshold should NOT trigger (strictly greater)."""
        triggered, _ = evaluate_condition("price_above", 1000, Decimal("1000"))
        assert triggered is False

    # ── price_below ───────────────────────────────────────────────
    def test_price_below_triggered(self):
        triggered, _ = evaluate_condition("price_below", 500, Decimal("1000"))
        assert triggered is True

    def test_price_below_not_triggered(self):
        triggered, _ = evaluate_condition("price_below", 95000, Decimal("1000"))
        assert triggered is False

    def test_price_below_equal_threshold_not_triggered(self):
        triggered, _ = evaluate_condition("price_below", 1000, Decimal("1000"))
        assert triggered is False

    # ── percent_change ────────────────────────────────────────────
    def test_percent_change_triggered(self):
        triggered, value = evaluate_condition("percent_change", 110, Decimal("5"), prev_price=100)
        assert triggered is True
        assert value == pytest.approx(10.0)

    def test_percent_change_not_triggered(self):
        triggered, _ = evaluate_condition("percent_change", 102, Decimal("5"), prev_price=100)
        assert triggered is False

    def test_percent_change_no_prev_price(self):
        triggered, _ = evaluate_condition("percent_change", 102, Decimal("5"), prev_price=None)
        assert triggered is False

    def test_percent_change_prev_price_zero(self):
        """Zero prev_price must not cause ZeroDivisionError and must not trigger."""
        triggered, _ = evaluate_condition("percent_change", 100, Decimal("5"), prev_price=0)
        assert triggered is False

    def test_percent_change_price_drop(self):
        """Drop counts as abs change."""
        triggered, value = evaluate_condition("percent_change", 90, Decimal("5"), prev_price=100)
        assert triggered is True
        assert value == pytest.approx(10.0)

    def test_percent_change_exactly_at_threshold_not_triggered(self):
        """Strictly greater — change == threshold should not trigger."""
        triggered, _ = evaluate_condition("percent_change", 105, Decimal("5"), prev_price=100)
        assert triggered is False

    # ── market_cap_rank ───────────────────────────────────────────
    def test_market_cap_rank_triggered(self):
        triggered, _ = evaluate_condition("market_cap_rank", 1, Decimal("5"))
        assert triggered is True

    def test_market_cap_rank_not_triggered(self):
        triggered, _ = evaluate_condition("market_cap_rank", 10, Decimal("5"))
        assert triggered is False

    def test_market_cap_rank_equal_threshold_triggered(self):
        """Rank == threshold should trigger (rank <= threshold)."""
        triggered, _ = evaluate_condition("market_cap_rank", 5, Decimal("5"))
        assert triggered is True

    def test_market_cap_rank_current_value_is_int(self):
        _, value = evaluate_condition("market_cap_rank", 3, Decimal("10"))
        assert isinstance(value, int)

    # ── unknown condition ─────────────────────────────────────────
    def test_unknown_condition_never_triggers(self):
        triggered, _ = evaluate_condition("unknown_type", 99999, Decimal("1"))
        assert triggered is False


# ─── cooldown logic ──────────────────────────────────────────────

class TestCooldownLogic:
    def _can_trigger(self, last_triggered_at, cooldown_seconds):
        if last_triggered_at is None:
            return True
        cooldown = timedelta(seconds=cooldown_seconds or 1800)
        return datetime.utcnow() - last_triggered_at >= cooldown

    def test_no_previous_trigger(self):
        assert self._can_trigger(None, 1800) is True

    def test_within_cooldown(self):
        recent = datetime.utcnow() - timedelta(seconds=100)
        assert self._can_trigger(recent, 1800) is False

    def test_cooldown_expired(self):
        old = datetime.utcnow() - timedelta(seconds=2000)
        assert self._can_trigger(old, 1800) is True

    def test_zero_cooldown_uses_default(self):
        """cooldown_seconds=0 should fall back to 1800."""
        recent = datetime.utcnow() - timedelta(seconds=100)
        assert self._can_trigger(recent, 0) is False

    def test_none_cooldown_uses_default(self):
        recent = datetime.utcnow() - timedelta(seconds=100)
        assert self._can_trigger(recent, None) is False

    def test_exactly_at_cooldown_boundary(self):
        """Exactly at cooldown boundary should be allowed (>=)."""
        exactly = datetime.utcnow() - timedelta(seconds=1800)
        assert self._can_trigger(exactly, 1800) is True

    def test_very_short_cooldown(self):
        old = datetime.utcnow() - timedelta(seconds=10)
        assert self._can_trigger(old, 5) is True


# ─── publish_rabbitmq_event payload ──────────────────────────────

def _make_mock_connection():
    """Returns (mock_conn, captured) — captured['payload'] filled on publish."""
    captured = {}

    def fake_publish(payload, **kwargs):
        captured["payload"] = payload

    mock_producer = MagicMock()
    mock_producer.publish = fake_publish

    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.Producer.return_value.__enter__ = MagicMock(return_value=mock_producer)
    mock_conn.Producer.return_value.__exit__ = MagicMock(return_value=False)

    return mock_conn, captured


class TestPublishPayload:
    def _publish(self, watch, current_value):
        from app.celery import publish_rabbitmq_event
        mock_conn, captured = _make_mock_connection()
        with patch("app.celery.Connection", return_value=mock_conn):
            publish_rabbitmq_event(watch, current_value, datetime.utcnow())
        assert captured, "publish() was never called — mock setup is broken"
        return captured["payload"]

    # ── price_above ───────────────────────────────────────────────
    def test_watch_name_price_above(self):
        watch = {
            "id": uuid4(), "user_id": uuid4(),
            "asset": "bitcoin", "condition_type": "price_above",
            "threshold": Decimal("70000"),
        }
        payload = self._publish(watch, 75000.0)
        assert payload["watch_name"] == "BITCOIN > 70000"
        assert payload["asset"] == "bitcoin"
        assert payload["version"] == 1
        assert "event_id" in payload
        assert payload["condition"]["type"] == "price_above"
        assert payload["condition"]["threshold"] == 70000.0
        assert payload["current_value"] == 75000.0

    # ── price_below ───────────────────────────────────────────────
    def test_watch_name_price_below(self):
        watch = {
            "id": uuid4(), "user_id": uuid4(),
            "asset": "ethereum", "condition_type": "price_below",
            "threshold": Decimal("2000"),
        }
        payload = self._publish(watch, 1800.0)
        assert payload["watch_name"] == "ETHEREUM < 2000"

    # ── percent_change ────────────────────────────────────────────
    def test_watch_name_percent_change(self):
        watch = {
            "id": uuid4(), "user_id": uuid4(),
            "asset": "ethereum", "condition_type": "percent_change",
            "threshold": Decimal("5"),
        }
        payload = self._publish(watch, 7.5)
        assert "Δ%" in payload["watch_name"]
        assert payload["current_value"] == 7.5

    # ── market_cap_rank ───────────────────────────────────────────
    def test_watch_name_market_cap_rank(self):
        watch = {
            "id": uuid4(), "user_id": uuid4(),
            "asset": "bitcoin", "condition_type": "market_cap_rank",
            "threshold": Decimal("5"),
        }
        payload = self._publish(watch, 1)
        assert "#" in payload["watch_name"]

    # ── float threshold (non-integer) ────────────────────────────
    def test_threshold_float_preserved(self):
        watch = {
            "id": uuid4(), "user_id": uuid4(),
            "asset": "bitcoin", "condition_type": "price_above",
            "threshold": Decimal("69999.50"),
        }
        payload = self._publish(watch, 70000.0)
        assert payload["condition"]["threshold"] == 69999.5

    # ── integer threshold rendered without .0 ────────────────────
    def test_threshold_integer_rendered_without_decimal(self):
        watch = {
            "id": uuid4(), "user_id": uuid4(),
            "asset": "bitcoin", "condition_type": "price_above",
            "threshold": Decimal("70000"),
        }
        payload = self._publish(watch, 71000.0)
        assert "." not in payload["watch_name"] or payload["watch_name"].endswith("70000")

    # ── required fields always present ───────────────────────────
    def test_required_fields_always_present(self):
        watch = {
            "id": uuid4(), "user_id": uuid4(),
            "asset": "solana", "condition_type": "price_above",
            "threshold": Decimal("100"),
        }
        payload = self._publish(watch, 120.0)
        for field in ("event_id", "version", "watch_id", "user_id", "watch_name",
                      "asset", "condition", "current_value", "triggered_at"):
            assert field in payload, f"Missing field: {field}"

    # ── triggered_at format ───────────────────────────────────────
    def test_triggered_at_format(self):
        watch = {
            "id": uuid4(), "user_id": uuid4(),
            "asset": "bitcoin", "condition_type": "price_above",
            "threshold": Decimal("1000"),
        }
        payload = self._publish(watch, 2000.0)
        # Must be parseable ISO format
        datetime.strptime(payload["triggered_at"], "%Y-%m-%dT%H:%M:%SZ")

    # ── rabbitmq connection error ─────────────────────────────────
    def test_rabbitmq_connection_error_raises(self):
        from app.celery import publish_rabbitmq_event
        watch = {
            "id": uuid4(), "user_id": uuid4(),
            "asset": "bitcoin", "condition_type": "price_above",
            "threshold": Decimal("1000"),
        }
        with patch("app.celery.Connection", side_effect=Exception("Connection refused")):
            with pytest.raises(Exception, match="Connection refused"):
                publish_rabbitmq_event(watch, 2000.0, datetime.utcnow())


# ─── dispatch_due_checks ─────────────────────────────────────────

class TestDispatchDueChecks:
    def _run_dispatch(self, watches, user_plan="free"):
        """Helper: patches DB + Redis + auth, runs dispatch_due_checks synchronously."""
        from app.tasks import dispatch_due_checks

        mock_quota = MagicMock()
        mock_quota.plan = user_plan

        async def fake_run():
            return watches

        with patch("app.tasks.async_session_factory") as mock_sf, \
             patch("app.tasks.redis") as mock_redis, \
             patch("app.tasks.auth_client") as mock_auth, \
             patch("app.tasks.check_watch") as mock_task:

            # DB session mock
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.all.return_value = [
                MagicMock(_mapping=w) for w in watches
            ]
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

            # Redis: no cached plan
            mock_redis.get = AsyncMock(return_value=None)
            mock_redis.set = AsyncMock()
            mock_redis.initialize = AsyncMock()

            # Auth quota
            mock_auth.get_user_quota = AsyncMock(return_value=mock_quota)

            # Celery task
            mock_task.apply_async = MagicMock()

            result = dispatch_due_checks()
            return result, mock_task

    def test_no_due_watches_returns_early(self):
        result, mock_task = self._run_dispatch([])
        assert "No watches" in result
        mock_task.apply_async.assert_not_called()

    def test_dispatches_correct_number_of_tasks(self):
        user_id = uuid4()
        watches = [
            {"id": uuid4(), "asset": "bitcoin", "condition_type": "price_above",
             "threshold": Decimal("1000"), "user_id": user_id},
            {"id": uuid4(), "asset": "ethereum", "condition_type": "price_below",
             "threshold": Decimal("2000"), "user_id": user_id},
        ]
        result, mock_task = self._run_dispatch(watches)
        assert mock_task.apply_async.call_count == 2
        assert "2" in result

    def test_business_plan_uses_high_queue(self):
        user_id = uuid4()
        watches = [
            {"id": uuid4(), "asset": "bitcoin", "condition_type": "price_above",
             "threshold": Decimal("1000"), "user_id": user_id},
        ]
        _, mock_task = self._run_dispatch(watches, user_plan="business")
        call_kwargs = mock_task.apply_async.call_args
        assert call_kwargs[1]["queue"] == "watcher_high"

    def test_free_plan_uses_low_queue(self):
        user_id = uuid4()
        watches = [
            {"id": uuid4(), "asset": "bitcoin", "condition_type": "price_above",
             "threshold": Decimal("1000"), "user_id": user_id},
        ]
        _, mock_task = self._run_dispatch(watches, user_plan="free")
        call_kwargs = mock_task.apply_async.call_args
        assert call_kwargs[1]["queue"] == "watcher_low"

    def test_unknown_plan_falls_back_to_low_queue(self):
        user_id = uuid4()
        watches = [
            {"id": uuid4(), "asset": "bitcoin", "condition_type": "price_above",
             "threshold": Decimal("1000"), "user_id": user_id},
        ]
        _, mock_task = self._run_dispatch(watches, user_plan="enterprise_unknown")
        call_kwargs = mock_task.apply_async.call_args
        assert call_kwargs[1]["queue"] == "watcher_low"

    def test_multiple_users_grouped_correctly(self):
        user_a, user_b = uuid4(), uuid4()
        watches = [
            {"id": uuid4(), "asset": "bitcoin", "condition_type": "price_above",
             "threshold": Decimal("1000"), "user_id": user_a},
            {"id": uuid4(), "asset": "ethereum", "condition_type": "price_below",
             "threshold": Decimal("2000"), "user_id": user_b},
            {"id": uuid4(), "asset": "solana", "condition_type": "price_above",
             "threshold": Decimal("100"), "user_id": user_a},
        ]
        _, mock_task = self._run_dispatch(watches)
        assert mock_task.apply_async.call_count == 3


# ─── check_watch task ────────────────────────────────────────────

def make_db_watch(**kwargs):
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "asset": "bitcoin",
        "condition_type": "price_above",
        "threshold": Decimal("1000"),
        "is_active": True,
        "cooldown_seconds": 1800,
        "interval_seconds": 60,
        "last_triggered_at": None,
    }
    defaults.update(kwargs)
    return defaults


def make_coin_data(price=50000.0, rank=1):
    return [{"current_price": price, "market_cap_rank": rank}]


class TestCheckWatch:
    """
    Tests for the check_watch Celery task.
    All external I/O (DB, Redis, CoinGecko, RabbitMQ) is mocked.
    """

    def _run(self, watch_row, coin_data=None, redis_overrides=None, lock_acquired=True):
        """
        Runs check_watch synchronously with full mocking.
        Returns (result_str, mock_session, mock_redis, mock_publish).
        """
        from app.tasks import check_watch

        if coin_data is None:
            coin_data = make_coin_data()

        mock_session = AsyncMock()

        # DB returns watch row
        mock_db_result = MagicMock()
        mock_db_result.mappings.return_value.first.return_value = watch_row
        mock_session.execute = AsyncMock(return_value=mock_db_result)
        mock_session.commit = AsyncMock()

        mock_redis = AsyncMock()
        mock_redis.initialize = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(return_value=lock_acquired)  # nx=True lock
        mock_redis.delete = AsyncMock()
        if redis_overrides:
            for attr, val in redis_overrides.items():
                setattr(mock_redis, attr, val)

        mock_cg = AsyncMock()
        mock_cg.get_market_data = AsyncMock(return_value=coin_data)

        with patch("app.tasks.async_session_factory") as mock_sf, \
             patch("app.tasks.redis", mock_redis), \
             patch("app.tasks.CoinGeckoClient", return_value=mock_cg), \
             patch("app.tasks.publish_rabbitmq_event") as mock_publish:

            mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)

            result = check_watch(str(watch_row["id"]))

        return result, mock_session, mock_redis, mock_publish

    # ── inactive watch ────────────────────────────────────────────
    def test_inactive_watch_skipped(self):
        watch = make_db_watch(is_active=False)
        result, _, _, mock_publish = self._run(watch)
        assert "inactive" in result.lower()
        mock_publish.assert_not_called()

    def test_watch_not_found_skipped(self):
        from app.tasks import check_watch
        mock_session = AsyncMock()
        mock_db_result = MagicMock()
        mock_db_result.mappings.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_db_result)

        mock_redis = AsyncMock()
        mock_redis.initialize = AsyncMock()

        with patch("app.tasks.async_session_factory") as mock_sf, \
             patch("app.tasks.redis", mock_redis), \
             patch("app.tasks.CoinGeckoClient"):
            mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = check_watch(str(uuid4()))

        assert "inactive" in result.lower()

    # ── distributed lock ──────────────────────────────────────────
    def test_lock_held_by_another_worker_skips(self):
        watch = make_db_watch()
        result, _, _, mock_publish = self._run(watch, lock_acquired=False)
        assert "skipped" in result.lower()
        mock_publish.assert_not_called()

    def test_lock_released_after_execution(self):
        watch = make_db_watch()
        _, _, mock_redis, _ = self._run(watch)
        mock_redis.delete.assert_called_once_with(f"lock:watch:{watch['id']}")

    def test_lock_released_even_when_condition_not_triggered(self):
        watch = make_db_watch(condition_type="price_above", threshold=Decimal("999999"))
        _, _, mock_redis, _ = self._run(watch, coin_data=make_coin_data(price=100.0))
        mock_redis.delete.assert_called_once()

    # ── price_above triggers ──────────────────────────────────────
    def test_price_above_triggers_alert(self):
        watch = make_db_watch(condition_type="price_above", threshold=Decimal("1000"))
        result, mock_session, _, mock_publish = self._run(
            watch, coin_data=make_coin_data(price=50000.0)
        )
        assert result == "Triggered."
        mock_publish.assert_called_once()
        # Alert INSERT was executed
        assert mock_session.execute.call_count >= 2
        assert mock_session.commit.called

    def test_price_above_not_triggered(self):
        watch = make_db_watch(condition_type="price_above", threshold=Decimal("999999"))
        result, _, _, mock_publish = self._run(watch, coin_data=make_coin_data(price=100.0))
        assert result == "Checked."
        mock_publish.assert_not_called()

    # ── price_below triggers ──────────────────────────────────────
    def test_price_below_triggers_alert(self):
        watch = make_db_watch(condition_type="price_below", threshold=Decimal("60000"))
        result, _, _, mock_publish = self._run(watch, coin_data=make_coin_data(price=50000.0))
        assert result == "Triggered."
        mock_publish.assert_called_once()

    def test_price_below_not_triggered(self):
        watch = make_db_watch(condition_type="price_below", threshold=Decimal("1000"))
        result, _, _, mock_publish = self._run(watch, coin_data=make_coin_data(price=50000.0))
        assert result == "Checked."
        mock_publish.assert_not_called()

    # ── percent_change ────────────────────────────────────────────
    def test_percent_change_no_prev_price_not_triggered(self):
        watch = make_db_watch(condition_type="percent_change", threshold=Decimal("5"))
        # redis.get returns None — no previous price stored
        result, _, _, mock_publish = self._run(watch, coin_data=make_coin_data(price=110.0))
        assert result == "Checked."
        mock_publish.assert_not_called()

    def test_percent_change_with_prev_price_triggers(self):
        watch = make_db_watch(condition_type="percent_change", threshold=Decimal("5"))
        redis_overrides = {"get": AsyncMock(return_value="100.0")}
        result, _, _, mock_publish = self._run(
            watch,
            coin_data=make_coin_data(price=115.0),
            redis_overrides=redis_overrides,
        )
        assert result == "Triggered."
        mock_publish.assert_called_once()

    def test_percent_change_stores_current_price_in_redis(self):
        watch = make_db_watch(condition_type="percent_change", threshold=Decimal("5"))
        _, _, mock_redis, _ = self._run(watch, coin_data=make_coin_data(price=55000.0))
        price_key = f"watch:{watch['id']}:last_price"
        set_calls = [c for c in mock_redis.set.call_args_list if price_key in str(c)]
        assert set_calls, "Current price was not stored in Redis for percent_change"

    # ── market_cap_rank ───────────────────────────────────────────
    def test_market_cap_rank_triggers(self):
        watch = make_db_watch(condition_type="market_cap_rank", threshold=Decimal("5"))
        result, _, _, mock_publish = self._run(watch, coin_data=make_coin_data(rank=3))
        assert result == "Triggered."
        mock_publish.assert_called_once()

    def test_market_cap_rank_not_triggered(self):
        watch = make_db_watch(condition_type="market_cap_rank", threshold=Decimal("5"))
        result, _, _, mock_publish = self._run(watch, coin_data=make_coin_data(rank=10))
        assert result == "Checked."
        mock_publish.assert_not_called()

    # ── cooldown respected ────────────────────────────────────────
    def test_cooldown_prevents_retrigger(self):
        recent = datetime.utcnow() - timedelta(seconds=100)
        watch = make_db_watch(
            condition_type="price_above",
            threshold=Decimal("1000"),
            last_triggered_at=recent,
            cooldown_seconds=1800,
        )
        result, _, _, mock_publish = self._run(watch, coin_data=make_coin_data(price=50000.0))
        # Condition is met but cooldown blocks it — should check but not trigger
        assert result == "Checked."
        mock_publish.assert_not_called()

    def test_expired_cooldown_allows_retrigger(self):
        old = datetime.utcnow() - timedelta(seconds=2000)
        watch = make_db_watch(
            condition_type="price_above",
            threshold=Decimal("1000"),
            last_triggered_at=old,
            cooldown_seconds=1800,
        )
        result, _, _, mock_publish = self._run(watch, coin_data=make_coin_data(price=50000.0))
        assert result == "Triggered."
        mock_publish.assert_called_once()

    # ── asset not found ───────────────────────────────────────────
    def test_empty_market_data_returns_early(self):
        watch = make_db_watch()
        result, _, _, mock_publish = self._run(watch, coin_data=[])
        assert "not found" in result.lower()
        mock_publish.assert_not_called()

    # ── CoinGecko errors ──────────────────────────────────────────
    def test_invalid_coin_returns_early(self):
        from app.coingecko.exceptions import CoinGeckoInvalidCoinError
        from app.tasks import check_watch

        watch = make_db_watch(asset="fakecoin")

        mock_session = AsyncMock()
        mock_db_result = MagicMock()
        mock_db_result.mappings.return_value.first.return_value = watch
        mock_session.execute = AsyncMock(return_value=mock_db_result)

        mock_redis = AsyncMock()
        mock_redis.initialize = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        mock_cg = AsyncMock()
        mock_cg.get_market_data = AsyncMock(side_effect=CoinGeckoInvalidCoinError("not found"))

        with patch("app.tasks.async_session_factory") as mock_sf, \
             patch("app.tasks.redis", mock_redis), \
             patch("app.tasks.CoinGeckoClient", return_value=mock_cg), \
             patch("app.tasks.publish_rabbitmq_event") as mock_publish:
            mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
            result = check_watch(str(watch["id"]))

        assert "invalid asset" in result.lower()
        mock_publish.assert_not_called()

    def test_coingecko_unavailable_raises_for_celery_retry(self):
        """
        Non-CoinGeckoInvalidCoinError exceptions must be re-raised as
        CoinGeckoUnavailableError so Celery can auto-retry.
        """
        from app.coingecko.exceptions import CoinGeckoUnavailableError
        from app.tasks import check_watch

        watch = make_db_watch()

        mock_session = AsyncMock()
        mock_db_result = MagicMock()
        mock_db_result.mappings.return_value.first.return_value = watch
        mock_session.execute = AsyncMock(return_value=mock_db_result)

        mock_redis = AsyncMock()
        mock_redis.initialize = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.delete = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        mock_cg = AsyncMock()
        mock_cg.get_market_data = AsyncMock(side_effect=ConnectionError("timeout"))

        with patch("app.tasks.async_session_factory") as mock_sf, \
             patch("app.tasks.redis", mock_redis), \
             patch("app.tasks.CoinGeckoClient", return_value=mock_cg):
            mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_sf.return_value.__aexit__ = AsyncMock(return_value=False)
            with pytest.raises(CoinGeckoUnavailableError):
                check_watch(str(watch["id"]))

    # ── last_checked_at always updated ───────────────────────────
    def test_last_checked_at_updated_when_not_triggered(self):
        watch = make_db_watch(condition_type="price_above", threshold=Decimal("999999"))
        _, mock_session, _, _ = self._run(watch, coin_data=make_coin_data(price=100.0))
        assert mock_session.execute.call_count >= 2
        assert mock_session.commit.called