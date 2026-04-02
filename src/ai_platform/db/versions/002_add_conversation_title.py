"""Add title column to conversations.

Revision ID: 002
Revises: 001
Create Date: 2026-04-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("title", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "title")
