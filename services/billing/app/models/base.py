from datetime import datetime, timezone
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def utc_now() -> datetime:
    """Return current UTC datetime as naive (no tzinfo) for PostgreSQL TIMESTAMP columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
