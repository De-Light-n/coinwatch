
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

RUN uv pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy asyncpg alembic httpx structlog pytest pytest-asyncio

FROM python:3.12-slim AS runtime

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]