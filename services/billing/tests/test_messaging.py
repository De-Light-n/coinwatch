# tests/test_messaging.py
import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.messaging.publisher import EventPublisher, get_event_publisher


class TestEventPublisher:
    @patch("app.messaging.publisher.aio_pika.connect_robust")
    async def test_connect(self, mock_connect):
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connect.return_value = mock_connection

        publisher = EventPublisher()
        await publisher.connect()

        assert publisher._connection is not None
        mock_connect.assert_called_once()

    @patch("app.messaging.publisher.aio_pika.connect_robust")
    async def test_publish(self, mock_connect):
        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)

        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        mock_connect.return_value = mock_connection

        publisher = EventPublisher()
        await publisher.publish("subscription.changed", {"user_id": 1, "plan": "pro"})

        mock_exchange.publish.assert_called_once()
        call_args = mock_exchange.publish.call_args
        message = call_args[0][0]
        routing_key = call_args[1]["routing_key"]

        assert routing_key == "subscription.changed"
        assert message.delivery_mode == 2  # PERSISTENT
        assert message.content_type == "application/json"

        body = json.loads(message.body.decode())
        assert body["version"] == 1
        assert "event_id" in body
        assert "timestamp" in body
        assert body["user_id"] == 1
        assert body["plan"] == "pro"

    @patch("app.messaging.publisher.aio_pika.connect_robust")
    async def test_close(self, mock_connect):
        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connect.return_value = mock_connection

        publisher = EventPublisher()
        await publisher.connect()
        await publisher.close()

        mock_connection.close.assert_called_once()
        assert publisher._connection is None

    @patch("app.messaging.publisher.aio_pika.connect_robust")
    async def test_publish_auto_connect(self, mock_connect):
        """publish() should auto-connect if not already connected."""
        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)

        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        mock_connect.return_value = mock_connection

        publisher = EventPublisher()
        # Do NOT call connect() explicitly
        await publisher.publish("invoice.paid", {"amount_paid": 100})

        mock_connect.assert_called_once()
        mock_exchange.publish.assert_called_once()

    @patch("app.messaging.publisher.aio_pika.connect_robust")
    async def test_get_event_publisher_dependency(self, mock_connect):
        mock_exchange = AsyncMock()
        mock_channel = AsyncMock()
        mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)

        mock_connection = AsyncMock()
        mock_connection.is_closed = False
        mock_connection.channel = AsyncMock(return_value=mock_channel)
        mock_connect.return_value = mock_connection

        publisher = await get_event_publisher()
        assert isinstance(publisher, EventPublisher)
        assert publisher._connection is not None
