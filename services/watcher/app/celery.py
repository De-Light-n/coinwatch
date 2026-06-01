from celery import Celery
from kombu import Queue, Exchange, Connection
from datetime import datetime
import uuid
import logging
 
from app.config import settings
 
logger = logging.getLogger(__name__)
 
celery = Celery(
    "watcher",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL_BACKEND,
)
 
celery.conf.task_acks_late = True
celery.conf.task_reject_on_worker_lost = True
celery.conf.worker_prefetch_multiplier = 1
 
celery.conf.task_queues = (
    Queue('watcher_high', routing_key='watcher_high'),
    Queue('watcher_normal', routing_key='watcher_normal'),
    Queue('watcher_low', routing_key='watcher_low'),
)
celery.conf.task_default_queue = "watcher_low"
 
celery.conf.beat_schedule = {
    'dispatch-monitoring-checks-every-30s': {
        'task': 'app.tasks.dispatch_due_checks',
        'schedule': 30.0,
    },
}
celery.conf.timezone = 'UTC'
 
PLAN_TO_QUEUE = {
    'business': 'watcher_high',
    'pro': 'watcher_normal',
    'free': 'watcher_low'
}
 
watcher_exchange = Exchange('watcher.events', type='topic')
 
 
def publish_rabbitmq_event(watch: dict, current_value: float, triggered_at: datetime):
    condition_mapping = {
        "price_above": ">",
        "price_below": "<",
        "percent_change": "Δ%",
        "market_cap_rank": "#"
    }
    symbol = condition_mapping.get(watch["condition_type"], watch["condition_type"])
    thresh = int(watch['threshold']) if float(watch['threshold']).is_integer() else float(watch['threshold'])
    watch_name = f"{watch['asset'].upper()} {symbol} {thresh}"
 
    payload = {
        "event_id": str(uuid.uuid4()),
        "version": 1,
        "watch_id": str(watch["id"]),
        "user_id": str(watch["user_id"]),
        "watch_name": watch_name,
        "asset": watch["asset"],
        "condition": {
            "type": watch["condition_type"],
            "threshold": float(watch["threshold"])
        },
        "current_value": float(current_value),
        "triggered_at": triggered_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    }
 
    with Connection(settings.RABBITMQ_URL) as conn:
        with conn.Producer() as producer:
            producer.publish(
                payload,
                exchange=watcher_exchange,
                routing_key="alert.triggered",
                declare=[watcher_exchange]
            )
    logger.info(f"Published RabbitMQ event for watch {watch['id']}")


import app.tasks  