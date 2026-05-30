# === Етап 1: Збірка (Builder) ===
FROM python:3.12-slim AS builder

# Встановлюємо uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Копіюємо конфіги залежностей
COPY pyproject.toml uv.lock* ./

# Інсталюємо залежності у віртуальне оточення /app/.venv
RUN uv sync --frozen --no-dev --no-install-project

# === Етап 2: Запуск (Runtime) ===
FROM python:3.12-slim AS runtime

WORKDIR /app

# Встановлюємо curl для роботи healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Копіюємо віртуальне оточення з етапу builder
COPY --from=builder /app/.venv /app/.venv

# Копіюємо вихідний код застосунку
COPY app/ ./app/
COPY alembic.ini /app/
COPY alembic/ /app/alembic/

# Прокидаємо шлях до бінарників у VENV
ENV PATH="/app/.venv/bin:$PATH"

# Експонуємо порт
EXPOSE 8000

# Команда запуску (запускаємо через uvicorn)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]