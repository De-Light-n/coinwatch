import json
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from celery.signals import worker_process_init
from sqlalchemy import text

from app.db import async_session_factory, redis
from app.coingecko.exceptions import CoinGeckoUnavailableError, CoinGeckoInvalidCoinError, CoinGeckoRateLimitError
from app.clients.auth import AuthClient
from app.coingecko.coingecko import CoinGeckoClient
from app.celery import celery, PLAN_TO_QUEUE, publish_rabbitmq_event

logger = logging.getLogger(__name__)

worker_loop = None
auth_client = AuthClient()


@worker_process_init.connect
def init_worker_loop(**kwargs):
    global worker_loop
    worker_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(worker_loop)


def run_async(coro):
    global worker_loop
    if worker_loop is None:
        worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(worker_loop)
    return worker_loop.run_until_complete(coro)


@celery.task(name="app.tasks.dispatch_due_checks")
def dispatch_due_checks():
    async def _run():
        await redis.initialize() if hasattr(redis, "initialize") else None
        async with async_session_factory() as session:
            select_query = text("""
                SELECT id, asset, condition_type, threshold, user_id 
                FROM watches 
                WHERE is_active = True 
                  AND (
                    last_checked_at IS NULL 
                    OR now() - last_checked_at >= interval_seconds * interval '1 second'
                  );
            """)
            result = await session.execute(select_query)
            due_watches = [dict(row._mapping) for row in result.all()]

            if not due_watches:
                return "No watches due for checking right now."

            grouped_watches = defaultdict(list)
            for watch in due_watches:
                grouped_watches[watch['user_id']].append(watch)

            for user_id, watches in grouped_watches.items():
                redis_key = f"user:{user_id}:plan"
                user_plan = await redis.get(redis_key)
                if not user_plan:
                    try:
                        quota = await auth_client.get_user_quota(user_id)
                        user_plan = quota.plan
                        await redis.set(redis_key, user_plan, ex=300)
                    except Exception:
                        user_plan = 'free'
                queue_name = PLAN_TO_QUEUE.get(user_plan, 'watcher_low')
                for watch in watches:
                    check_watch.apply_async(args=[watch['id']], queue=queue_name)

            dispatched = sum(len(w) for w in grouped_watches.values())
            return f"Successfully dispatched {dispatched} checks."

    return run_async(_run())


@celery.task(
    name="app.tasks.check_watch",
    autoretry_for=(CoinGeckoUnavailableError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3
)
def check_watch(watch_id: int):
    async def _run():
        await redis.initialize() if hasattr(redis, "initialize") else None
        coingecko_client = CoinGeckoClient(redis=redis)
        async with async_session_factory() as session:
            select_query = text("""
                SELECT id, asset, condition_type, threshold, user_id, is_active, cooldown_seconds, interval_seconds, last_triggered_at
                FROM watches
                WHERE id = :watch_id;
            """)
            result = await session.execute(select_query, {"watch_id": watch_id})
            watch = result.mappings().first()

            if not watch or not watch["is_active"]:
                return f"Watch {watch_id} inactive."

            lock_key = f"lock:watch:{watch_id}"
            lock_ttl = watch["interval_seconds"] or 30
            is_locked = await redis.set(lock_key, "true", ex=lock_ttl, nx=True)
            if not is_locked:
                return f"Watch {watch_id} skipped."

            try:
                try:
                    market_data = await coingecko_client.get_market_data(coin_ids=[watch["asset"]])
                    if not market_data:
                        return "Asset not found."
                    coin_details = market_data[0]
                    current_price = float(coin_details["current_price"])
                    market_rank = int(coin_details["market_cap_rank"])
                except CoinGeckoInvalidCoinError:
                    logger.warning(f"Watch {watch_id}: invalid asset '{watch['asset']}', skipping.")
                    return f"Watch {watch_id}: invalid asset."
                except CoinGeckoRateLimitError:
                    logger.warning(f"Watch {watch_id}: rate limit hit, will retry next cycle.")
                    return f"Watch {watch_id}: rate limited."
                except Exception:
                    raise CoinGeckoUnavailableError()

                triggered = False
                current_value = current_price
                if watch["condition_type"] == "price_above":
                    if current_price > watch["threshold"]:
                        triggered = True
                elif watch["condition_type"] == "price_below":
                    if current_price < watch["threshold"]:
                        triggered = True
                elif watch["condition_type"] == "percent_change":
                    price_key = f"watch:{watch_id}:last_price"
                    prev_price_str = await redis.get(price_key)
                    if prev_price_str:
                        prev_price = float(prev_price_str)
                        if prev_price > 0:
                            change = abs(current_price - prev_price) / prev_price * 100
                            current_value = change
                            if change > watch["threshold"]:
                                triggered = True
                    else:
                        logger.info(f"Watch {watch_id}: no previous price, skipping percent_change check.")
                    await redis.set(price_key, str(current_price))
                elif watch["condition_type"] == "market_cap_rank":
                    current_value = market_rank
                    if market_rank <= watch["threshold"]:
                        triggered = True

                now = datetime.now(timezone.utc)

                if triggered:
                    can_trigger = True
                    if watch["last_triggered_at"]:
                        last = watch["last_triggered_at"]
                        # Ensure last_triggered_at is timezone-aware (PostgreSQL returns aware)
                        if last.tzinfo is None:
                            last = last.replace(tzinfo=timezone.utc)
                        cooldown = timedelta(seconds=watch["cooldown_seconds"] or 1800)
                        if now - last < cooldown:
                            can_trigger = False
                    if can_trigger:
                        await session.execute(
                            text("""
                                INSERT INTO alerts (watch_id, user_id, triggered_at, condition_value, payload)
                                VALUES (:w, :u, :t, :v, :p)
                            """),
                            {
                                "w": watch_id,
                                "u": watch["user_id"],
                                "t": now,
                                "v": current_value,
                                "p": json.dumps({
                                    "event_id": str(uuid.uuid4()),
                                    "version": 1,
                                    "watch_id": str(watch_id),
                                    "user_id": str(watch["user_id"]),
                                    "asset": watch["asset"],
                                    "condition": {
                                        "type": watch["condition_type"],
                                        "threshold": float(watch["threshold"])
                                    },
                                    "current_value": float(current_value),
                                    "triggered_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")
                                })
                            }
                        )
                        await session.execute(
                            text("UPDATE watches SET last_triggered_at = :now, last_checked_at = :now WHERE id = :id"),
                            {"now": now, "id": watch_id}
                        )
                        await session.commit()
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, publish_rabbitmq_event, dict(watch), current_value, now)
                        return "Triggered."

                await session.execute(
                    text("UPDATE watches SET last_checked_at = :now WHERE id = :id"),
                    {"now": now, "id": watch_id}
                )
                await session.commit()
                return "Checked."
            finally:
                await redis.delete(lock_key)

    return run_async(_run())