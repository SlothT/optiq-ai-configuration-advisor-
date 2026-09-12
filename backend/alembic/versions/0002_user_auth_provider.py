"""add users.auth_provider for password vs google

Revision ID: 0002_user_auth_provider
Revises: 0001_phase1_core
Create Date: 2026-09-04 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_user_auth_provider"
down_revision = "0001_phase1_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(length=32), nullable=False, server_default="password"),
    )


def downgrade() -> None:
    op.drop_column("users", "auth_provider")
