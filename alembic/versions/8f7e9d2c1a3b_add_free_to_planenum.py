"""Add 'free' to PlanEnum

Revision ID: 8f7e9d2c1a3b
Revises: 152c8bfb6114
Create Date: 2026-05-30 02:08:44.205743

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f7e9d2c1a3b"
down_revision: Union[str, Sequence[str], None] = "152c8bfb6114"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE planenum ADD VALUE 'free'")


def downgrade() -> None:
    """Downgrade schema."""
    # PostgreSQL does not support removing enum values directly.
    # A full rebuild would be required; skipped for simplicity.
    pass
