"""add email verification columns on users

Revision ID: 0003_email_verified
Revises: 0002_user_auth_provider
Create Date: 2026-09-04 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0003_email_verified"
down_revision = "0002_user_auth_provider"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("users", sa.Column("email_verify_token_hash", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("email_verify_expires_at", sa.DateTime(timezone=True), nullable=True))
    if op.get_bind().dialect.name != "sqlite":
        op.alter_column("users", "email_verified", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "email_verify_expires_at")
    op.drop_column("users", "email_verify_token_hash")
    op.drop_column("users", "email_verified")
