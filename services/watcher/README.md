Watcher Service
Мікросервіс для моніторингу цін криптовалют. Створює watches з умовами (price_above, price_below, percent_change, market_cap_rank), перевіряє їх за розкладом через Celery і публікує алерти в RabbitMQ.
Потік:

Beat кожні 30 сек запускає dispatch_due_checks
Диспетчер знаходить watches де now - last_checked_at >= interval_seconds
Для кожного user визначає план (Business/Pro/Free) через Auth Service (кешується в Redis на 5 хв)
Кидає check_watch таску у відповідну чергу
Worker отримує ціну з CoinGecko, оцінює умову
При тригері — зберігає alert в БД і публікує event в RabbitMQ


Як додати новий condition_type
1. Додати значення в enum (app/models/watch.py):
pythonclass ConditionType(str, enum.Enum):
    price_above = "price_above"
    price_below = "price_below"
    percent_change = "percent_change"
    market_cap_rank = "market_cap_rank"
    volume_above = "volume_above"  # новий
2. Додати логіку в check_watch (app/tasks.py):
pythonelif watch["condition_type"] == "volume_above":
    current_value = float(coin_details["total_volume"])
    if current_value > watch["threshold"]:
        triggered = True
3. Додати символ в publish_rabbitmq_event (app/celery.py):
pythoncondition_mapping = {
    ...
    "volume_above": "VOL>",
}
4. Зробити міграцію якщо enum в БД:
bashdocker compose exec watcher-api alembic revision --autogenerate -m "add volume_above condition"
docker compose exec watcher-api alembic upgrade head

CoinGecko rate limits і як ми їх обходимо
Ліміт безкоштовного плану: 25-30 запитів/хв (sliding window).
Що робимо:
МеханізмДеЯкSliding window counterCoinGeckoClient._check_rate_limitRedis ZSET, відхиляє запити при перевищенні 25 req/60sКеш цінget_pricesTTL 30s в Redis, не робить запит якщо є кешCircuit breakerpybreakerПісля 5 помилок підряд — блокує запити на 60sRetry з backofftenacity + Celery retry_backoffПри 429/5xx — exponential backoff, max 3 спробиRedis lockcheck_watchОдин watch не може виконуватись паралельно (TTL = interval_seconds)
Важливо при багатьох watches: всі воркери використовують спільний Redis лічильник, але при -P prefork --concurrency=4 чотири процеси можуть одночасно пройти перевірку. При великій кількості watches — зменшіть rate_limit_max до 6-8 або використовуйте платний CoinGecko план.

Troubleshooting
Tasks не виконуються
bash# перевірити чи worker живий
docker compose logs watcher-worker --tail=20

# перевірити чи таски реєструються
docker compose exec watcher-worker celery -A app.celery.celery inspect registered

# перевірити черги в Redis
docker compose exec redis redis-cli llen watcher_low
docker compose exec redis redis-cli llen watcher_high
Якщо Received unregistered task — перевірте що в app/celery.py є рядок import app.tasks.
Watch не тригериться
bash# перевірити стан watch
docker compose exec postgres psql -U postgres -d watcher_db -c \
  "SELECT id, is_active, last_checked_at, last_triggered_at, cooldown_seconds FROM watches;"

# якщо last_triggered_at свіжий — watch в cooldown (default 1800s = 30 хв)
# скинути cooldown для тесту:
docker compose exec postgres psql -U postgres -d watcher_db -c \
  "UPDATE watches SET last_triggered_at = NULL WHERE id = '<id>';"

# перевірити чи умова взагалі може спрацювати
# наприклад threshold має бути НИЖЧЕ поточної ціни для price_above
CoinGecko returns 429
bash# подивитись поточний лічильник в Redis
docker compose exec redis redis-cli zcard cg:ratelimit:window

# якщо > 25 — зачекати хвилину поки вікно скинеться
# або тимчасово деактивувати зайві watches:
docker compose exec postgres psql -U postgres -d watcher_db -c \
  "UPDATE watches SET is_active = false WHERE id != '<залишити один>';"
При систематичних 429 — розгляньте CoinGecko Pro план або збільшіть interval_seconds для watches.

Flower (моніторинг)
Відкрити: http://localhost:85/flower/
Логін/пароль: FLOWER_USER / FLOWER_PASSWORD з .env
Що дивитись:

Workers — активні воркери і які черги слухають
Tasks — історія виконань, результати (Triggered. / Checked. / No watches due)
Monitor — реалтайм throughput і failed tasks


Запуск локально
bash# запустити всі сервіси
cd infra
docker compose up -d

# міграції
docker compose exec watcher-api alembic upgrade head

# перевірити health
curl http://localhost:85/watcher/health