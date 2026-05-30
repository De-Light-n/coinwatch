import pytest
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
    """Helper that mirrors check_watch logic for unit testing conditions."""
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
    def test_price_above_triggered(self):
        triggered, _ = evaluate_condition("price_above", 95000, Decimal("1000"))
        assert triggered is True
 
    def test_price_above_not_triggered(self):
        triggered, _ = evaluate_condition("price_above", 500, Decimal("1000"))
        assert triggered is False
 
    def test_price_below_triggered(self):
        triggered, _ = evaluate_condition("price_below", 500, Decimal("1000"))
        assert triggered is True
 
    def test_price_below_not_triggered(self):
        triggered, _ = evaluate_condition("price_below", 95000, Decimal("1000"))
        assert triggered is False
 
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
 
    def test_market_cap_rank_triggered(self):
        triggered, _ = evaluate_condition("market_cap_rank", 1, Decimal("5"))
        assert triggered is True
 
    def test_market_cap_rank_not_triggered(self):
        triggered, _ = evaluate_condition("market_cap_rank", 10, Decimal("5"))
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
        recent = datetime.utcnow() - timedelta(seconds=100)
        assert self._can_trigger(recent, 0) is False
 
 
# ─── publish_rabbitmq_event payload ──────────────────────────────
 
class TestPublishPayload:
    def test_watch_name_price_above(self):
        from app.celery import publish_rabbitmq_event
        watch = {
            "id": uuid4(),
            "user_id": uuid4(),
            "asset": "bitcoin",
            "condition_type": "price_above",
            "threshold": Decimal("70000"),
        }
 
        captured = {}
 
        def fake_publish(payload, **kwargs):
            captured["payload"] = payload
 
        with patch("app.celery.Connection") as mock_conn:
            mock_producer = MagicMock()
            mock_producer.publish = fake_publish
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.return_value.Producer.return_value.__enter__ = MagicMock(return_value=mock_producer)
            mock_conn.return_value.Producer.return_value.__exit__ = MagicMock(return_value=False)
 
            publish_rabbitmq_event(watch, 75000.0, datetime.utcnow())
 
        payload = captured.get("payload", {})
        assert payload.get("watch_name") == "BITCOIN > 70000"
        assert payload.get("asset") == "bitcoin"
        assert payload.get("version") == 1
        assert "event_id" in payload
        assert payload["condition"]["type"] == "price_above"
 
    def test_watch_name_percent_change(self):
        from app.celery import publish_rabbitmq_event
        watch = {
            "id": uuid4(),
            "user_id": uuid4(),
            "asset": "ethereum",
            "condition_type": "percent_change",
            "threshold": Decimal("5"),
        }
 
        captured = {}
 
        def fake_publish(payload, **kwargs):
            captured["payload"] = payload
 
        with patch("app.celery.Connection") as mock_conn:
            mock_producer = MagicMock()
            mock_producer.publish = fake_publish
            mock_conn.return_value.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.return_value.__exit__ = MagicMock(return_value=False)
            mock_conn.return_value.Producer.return_value.__enter__ = MagicMock(return_value=mock_producer)
            mock_conn.return_value.Producer.return_value.__exit__ = MagicMock(return_value=False)
 
            publish_rabbitmq_event(watch, 7.5, datetime.utcnow())
 
        payload = captured.get("payload", {})
        assert "Δ%" in payload.get("watch_name", "")
        assert payload.get("current_value") == 7.5
