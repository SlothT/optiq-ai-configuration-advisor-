"""phase1 core schema

Revision ID: 0001_phase1_core
Revises:
Create Date: 2026-08-03 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001_phase1_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("user_id", sa.String(length=32), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_projects_user_id"), "projects", ["user_id"], unique=False)

    op.create_table(
        "provider_keys",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("ollama_base_url", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "provider_name", name="uq_provider_keys_project_provider"),
    )
    op.create_index(op.f("ix_provider_keys_project_id"), "provider_keys", ["project_id"], unique=False)

    op.create_table(
        "prompts",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_prompt_id", sa.String(length=32), sa.ForeignKey("prompts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("quality_score", sa.Float(), nullable=True),
        sa.Column("estimated_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("judge_model", sa.String(length=128), nullable=True),
        sa.Column("analysis_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_prompts_project_id"), "prompts", ["project_id"], unique=False)

    op.create_table(
        "experiments",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mlflow_run_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("prompt_ids_json", sa.JSON(), nullable=False),
        sa.Column("model_ids_json", sa.JSON(), nullable=False),
        sa.Column("test_inputs_json", sa.JSON(), nullable=True),
        sa.Column("results_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_experiments_project_id"), "experiments", ["project_id"], unique=False)

    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("experiment_id", sa.String(length=32), sa.ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("recommended_config", sa.JSON(), nullable=False),
        sa.Column("excluded_options", sa.JSON(), nullable=False),
        sa.Column("ranked_options", sa.JSON(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(op.f("ix_recommendations_project_id"), "recommendations", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_recommendations_project_id"), table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_index(op.f("ix_experiments_project_id"), table_name="experiments")
    op.drop_table("experiments")
    op.drop_index(op.f("ix_prompts_project_id"), table_name="prompts")
    op.drop_table("prompts")
    op.drop_index(op.f("ix_provider_keys_project_id"), table_name="provider_keys")
    op.drop_table("provider_keys")
    op.drop_index(op.f("ix_projects_user_id"), table_name="projects")
    op.drop_table("projects")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
