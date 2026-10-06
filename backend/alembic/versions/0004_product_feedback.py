"""Store optional product feedback without account identifiers or prompt capture."""
import sqlalchemy as sa

from alembic import op

revision = "0004_product_feedback"
down_revision = "0003_email_verified"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_feedback",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("page", sa.String(100), nullable=False),
        sa.Column("rating", sa.String(20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("product_feedback")
