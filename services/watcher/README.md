Watcher Service
Мікросервіс для моніторингу цін криптовалют. Створює watches з умовами (price_above, price_below, percent_change, market_cap_rank), перевіряє їх за розкладом через Celery і публікує алерти в RabbitMQ.
Архітектура
#mermaid-r2s3-r1{font-family:"Anthropic Sans",system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:16px;fill:#E5E5E5;}@keyframes edge-animation-frame{from{stroke-dashoffset:0;}}@keyframes dash{to{stroke-dashoffset:0;}}#mermaid-r2s3-r1 .edge-animation-slow{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 50s linear infinite;stroke-linecap:round;}#mermaid-r2s3-r1 .edge-animation-fast{stroke-dasharray:9,5!important;stroke-dashoffset:900;animation:dash 20s linear infinite;stroke-linecap:round;}#mermaid-r2s3-r1 .error-icon{fill:#CC785C;}#mermaid-r2s3-r1 .error-text{fill:#3387a3;stroke:#3387a3;}#mermaid-r2s3-r1 .edge-thickness-normal{stroke-width:1px;}#mermaid-r2s3-r1 .edge-thickness-thick{stroke-width:3.5px;}#mermaid-r2s3-r1 .edge-pattern-solid{stroke-dasharray:0;}#mermaid-r2s3-r1 .edge-thickness-invisible{stroke-width:0;fill:none;}#mermaid-r2s3-r1 .edge-pattern-dashed{stroke-dasharray:3;}#mermaid-r2s3-r1 .edge-pattern-dotted{stroke-dasharray:2;}#mermaid-r2s3-r1 .marker{fill:#A1A1A1;stroke:#A1A1A1;}#mermaid-r2s3-r1 .marker.cross{stroke:#A1A1A1;}#mermaid-r2s3-r1 svg{font-family:"Anthropic Sans",system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:16px;}#mermaid-r2s3-r1 p{margin:0;}#mermaid-r2s3-r1 .label{font-family:"Anthropic Sans",system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#E5E5E5;}#mermaid-r2s3-r1 .cluster-label text{fill:#3387a3;}#mermaid-r2s3-r1 .cluster-label span{color:#3387a3;}#mermaid-r2s3-r1 .cluster-label span p{background-color:transparent;}#mermaid-r2s3-r1 .label text,#mermaid-r2s3-r1 span{fill:#E5E5E5;color:#E5E5E5;}#mermaid-r2s3-r1 .node rect,#mermaid-r2s3-r1 .node circle,#mermaid-r2s3-r1 .node ellipse,#mermaid-r2s3-r1 .node polygon,#mermaid-r2s3-r1 .node path{fill:transparent;stroke:#A1A1A1;stroke-width:1px;}#mermaid-r2s3-r1 .rough-node .label text,#mermaid-r2s3-r1 .node .label text,#mermaid-r2s3-r1 .image-shape .label,#mermaid-r2s3-r1 .icon-shape .label{text-anchor:middle;}#mermaid-r2s3-r1 .node .katex path{fill:#000;stroke:#000;stroke-width:1px;}#mermaid-r2s3-r1 .rough-node .label,#mermaid-r2s3-r1 .node .label,#mermaid-r2s3-r1 .image-shape .label,#mermaid-r2s3-r1 .icon-shape .label{text-align:center;}#mermaid-r2s3-r1 .node.clickable{cursor:pointer;}#mermaid-r2s3-r1 .root .anchor path{fill:#A1A1A1!important;stroke-width:0;stroke:#A1A1A1;}#mermaid-r2s3-r1 .arrowheadPath{fill:#0b0b0b;}#mermaid-r2s3-r1 .edgePath .path{stroke:#A1A1A1;stroke-width:1px;}#mermaid-r2s3-r1 .flowchart-link{stroke:#A1A1A1;fill:none;}#mermaid-r2s3-r1 .edgeLabel{background-color:transparent;text-align:center;}#mermaid-r2s3-r1 .edgeLabel p{background-color:transparent;}#mermaid-r2s3-r1 .edgeLabel rect{opacity:0.5;background-color:transparent;fill:transparent;}#mermaid-r2s3-r1 .labelBkg{background-color:rgba(0, 0, 0, 0.5);}#mermaid-r2s3-r1 .cluster rect{fill:#CC785C;stroke:hsl(15, 12.3364485981%, 48.0392156863%);stroke-width:1px;}#mermaid-r2s3-r1 .cluster text{fill:#3387a3;}#mermaid-r2s3-r1 .cluster span{color:#3387a3;}#mermaid-r2s3-r1 div.mermaidTooltip{position:absolute;text-align:center;max-width:200px;padding:2px;font-family:"Anthropic Sans",system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;font-size:12px;background:#CC785C;border:1px solid hsl(15, 12.3364485981%, 48.0392156863%);border-radius:2px;pointer-events:none;z-index:100;}#mermaid-r2s3-r1 .flowchartTitleText{text-anchor:middle;font-size:18px;fill:#E5E5E5;}#mermaid-r2s3-r1 rect.text{fill:none;stroke-width:0;}#mermaid-r2s3-r1 .icon-shape,#mermaid-r2s3-r1 .image-shape{background-color:transparent;text-align:center;}#mermaid-r2s3-r1 .icon-shape p,#mermaid-r2s3-r1 .image-shape p{background-color:transparent;padding:2px;}#mermaid-r2s3-r1 .icon-shape .label rect,#mermaid-r2s3-r1 .image-shape .label rect{opacity:0.5;background-color:transparent;fill:transparent;}#mermaid-r2s3-r1 .label-icon{display:inline-block;height:1em;overflow:visible;vertical-align:-0.125em;}#mermaid-r2s3-r1 .node .label-icon path{fill:currentColor;stroke:revert;stroke-width:revert;}#mermaid-r2s3-r1 .node .neo-node{stroke:#A1A1A1;}#mermaid-r2s3-r1 [data-look="neo"].node rect,#mermaid-r2s3-r1 [data-look="neo"].cluster rect,#mermaid-r2s3-r1 [data-look="neo"].node polygon{stroke:url(#mermaid-r2s3-r1-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#mermaid-r2s3-r1 [data-look="neo"].node path{stroke:url(#mermaid-r2s3-r1-gradient);stroke-width:1px;}#mermaid-r2s3-r1 [data-look="neo"].node .outer-path{filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#mermaid-r2s3-r1 [data-look="neo"].node .neo-line path{stroke:#A1A1A1;filter:none;}#mermaid-r2s3-r1 [data-look="neo"].node circle{stroke:url(#mermaid-r2s3-r1-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#mermaid-r2s3-r1 [data-look="neo"].node circle .state-start{fill:#000000;}#mermaid-r2s3-r1 [data-look="neo"].icon-shape .icon{fill:url(#mermaid-r2s3-r1-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#mermaid-r2s3-r1 [data-look="neo"].icon-shape .icon-neo path{stroke:url(#mermaid-r2s3-r1-gradient);filter:drop-shadow( 1px 2px 2px rgba(185,185,185,1));}#mermaid-r2s3-r1 :root{--mermaid-font-family:"Anthropic Sans",system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}query DBget planwatcher_highwatcher_normalwatcher_lowget pricesave alertalert.triggeredCelery Beat(every 30s)dispatch_due_checkstaskPostgreSQLRediscacheQueuewatcher_high(Business)Queuewatcher_normal(Pro)Queuewatcher_low(Free)check_watchworkerCoinGecko APIRabbitMQwatcher.events
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