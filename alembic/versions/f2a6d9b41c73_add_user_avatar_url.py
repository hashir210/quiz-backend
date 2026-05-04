"""add user avatar url

Revision ID: f2a6d9b41c73
Revises: dbc0f5433b4d
Create Date: 2026-05-04 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a6d9b41c73"
down_revision: Union[str, Sequence[str], None] = "dbc0f5433b4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
