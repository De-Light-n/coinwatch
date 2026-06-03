import json
import uuid
from datetime import datetime, timezone
from typing import Optional

import aio_pika
from aio_pika import DeliveryMode, ExchangeType

from app.config import settings


class EventPublisher:
    """Async RabbitMQ event publisher with auto-reconnect support."""

    def __init__(self):
        self._connection: Optional[aio_pika.RobustConnection] = None
        self._channel: Optional[aio_pika.RobustChannel] = None
        self._exchange: Optional[aio_pika.Exchange] = None

    async def connect(self) -> None:
        """Establish robust connection and declare the topic exchange."""
        if self._connection and not self._connection.is_closed:
            return

        self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            "billing.events", ExchangeType.TOPIC, durable=True
        )

    async def publish(self, routing_key: str, payload: dict) -> None:
        """Publish a persistent JSON message to the billing.events exchange."""
        if not self._exchange:
            await self.connect()

        message_body = {
            "event_id": str(uuid.uuid4()),
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **payload,
        }

        message = aio_pika.Message(
            body=json.dumps(message_body).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
        )
        await self._exchange.publish(message, routing_key=routing_key)

    async def close(self) -> None:
        """Gracefully close the connection."""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
        self._exchange = None
        self._channel = None
        self._connection = None


# Singleton instance used by service layer and FastAPI dependency.
_publisher_instance: Optional[EventPublisher] = None


async def get_publisher() -> EventPublisher:
    """Return the global EventPublisher singleton (lazy-connect)."""
    global _publisher_instance
    if _publisher_instance is None:
        _publisher_instance = EventPublisher()
        await _publisher_instance.connect()
    return _publisher_instance


async def get_event_publisher() -> EventPublisher:
    """FastAPI dependency wrapper for EventPublisher."""
    return await get_publisher()
