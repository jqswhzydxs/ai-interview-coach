"""add persistent workflow queue

Revision ID: d84f5a6b7c8d
Revises: c72e3f4a5b6c
Create Date: 2026-10-26 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d84f5a6b7c8d"
down_revision: str | Sequence[str] | None = "c72e3f4a5b6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_type = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
uuid_type = sa.Uuid()


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "workflow_jobs",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workflow_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("outcome_mode", sa.String(20), nullable=True),
        sa.Column("progress_stage", sa.String(80), nullable=False),
        sa.Column("progress_current", sa.Integer(), nullable=False),
        sa.Column("progress_total", sa.Integer(), nullable=False),
        sa.Column("input_resource_type", sa.String(50), nullable=False),
        sa.Column("input_resource_id", uuid_type, nullable=False),
        sa.Column("idempotency_key_digest", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_token", uuid_type, nullable=True),
        sa.Column("lease_owner_id", sa.String(128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("absolute_deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("safe_failure_category", sa.String(50), nullable=True),
        sa.Column("safe_failure_code", sa.String(80), nullable=True),
        sa.Column("agent_run_ids_json", json_type, nullable=False),
        *_timestamps(),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "idempotency_key_digest", name="uq_workflow_job_idempotency"),
    )
    op.create_index("idx_workflow_jobs_claim", "workflow_jobs", ["status", "available_at", "created_at"])
    op.create_index("idx_workflow_jobs_lease", "workflow_jobs", ["status", "lease_expires_at"])

    op.create_table(
        "workflow_job_attempts",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("workflow_job_id", uuid_type, sa.ForeignKey("workflow_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("lease_token", uuid_type, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("failure_category", sa.String(50), nullable=True),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("provider_call_count", sa.Integer(), nullable=False),
        sa.Column("successful_input_tokens", sa.Integer(), nullable=True),
        sa.Column("successful_output_tokens", sa.Integer(), nullable=True),
        sa.Column("successful_total_tokens", sa.Integer(), nullable=True),
        sa.Column("billing_usage_complete", sa.Boolean(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("workflow_job_id", "attempt_number", name="uq_workflow_attempt_number"),
    )
    op.create_index("idx_workflow_attempts_job", "workflow_job_attempts", ["workflow_job_id", "attempt_number"])

    op.create_table(
        "workflow_job_stages",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("workflow_job_id", uuid_type, sa.ForeignKey("workflow_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stable_stage_id", sa.String(160), nullable=False, unique=True),
        sa.Column("stage_key", sa.String(80), nullable=False),
        sa.Column("stage_order", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("external_effect_state", sa.String(20), nullable=False),
        sa.Column("agent_run_id", uuid_type, sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("workflow_job_id", "stage_key", name="uq_workflow_stage_key"),
    )
    op.create_index("idx_workflow_stages_job_order", "workflow_job_stages", ["workflow_job_id", "stage_order"])

    op.create_table(
        "workflow_job_results",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("workflow_job_id", uuid_type, sa.ForeignKey("workflow_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", uuid_type, nullable=False),
        sa.Column("resource_href", sa.String(300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workflow_job_id", "relation", name="uq_workflow_result_relation"),
    )

    op.create_table(
        "prep_package_requests",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("resume_id", uuid_type, sa.ForeignKey("resumes.id"), nullable=False),
        sa.Column("job_description_id", uuid_type, sa.ForeignKey("job_descriptions.id"), nullable=False),
        sa.Column("interview_experience_ids_json", json_type, nullable=False),
        sa.Column("preparation_goal", sa.String(500), nullable=False),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "answer_submissions",
        sa.Column("id", uuid_type, primary_key=True),
        sa.Column("user_id", uuid_type, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question_db_id", uuid_type, sa.ForeignKey("interview_questions.id"), nullable=True),
        sa.Column("custom_question_text", sa.Text(), nullable=True),
        sa.Column("user_answer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    for table in (
        "resume_profiles",
        "jd_profiles",
        "interview_prep_packages",
        "answer_evaluations",
    ):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("originating_workflow_job_id", uuid_type, nullable=True))
            batch_op.create_foreign_key(
                f"fk_{table}_originating_workflow_job",
                "workflow_jobs",
                ["originating_workflow_job_id"],
                ["id"],
            )
            batch_op.create_unique_constraint(
                f"uq_{table}_originating_workflow_job",
                ["originating_workflow_job_id"],
            )
    with op.batch_alter_table("experience_profiles") as batch_op:
        batch_op.add_column(sa.Column("originating_workflow_job_id", uuid_type, nullable=True))
        batch_op.create_foreign_key(
            "fk_experience_profiles_originating_workflow_job",
            "workflow_jobs",
            ["originating_workflow_job_id"],
            ["id"],
        )
        batch_op.create_unique_constraint(
            "uq_experience_profiles_workflow_experience",
            ["originating_workflow_job_id", "interview_experience_id"],
        )


def downgrade() -> None:
    for table in (
        "answer_evaluations",
        "interview_prep_packages",
        "jd_profiles",
        "resume_profiles",
    ):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(f"uq_{table}_originating_workflow_job", type_="unique")
            batch_op.drop_constraint(f"fk_{table}_originating_workflow_job", type_="foreignkey")
            batch_op.drop_column("originating_workflow_job_id")

    with op.batch_alter_table("experience_profiles") as batch_op:
        batch_op.drop_constraint("uq_experience_profiles_workflow_experience", type_="unique")
        batch_op.drop_constraint(
            "fk_experience_profiles_originating_workflow_job", type_="foreignkey"
        )
        batch_op.drop_column("originating_workflow_job_id")

    op.drop_table("answer_submissions")
    op.drop_table("prep_package_requests")
    op.drop_table("workflow_job_results")
    op.drop_index("idx_workflow_stages_job_order", table_name="workflow_job_stages")
    op.drop_table("workflow_job_stages")
    op.drop_index("idx_workflow_attempts_job", table_name="workflow_job_attempts")
    op.drop_table("workflow_job_attempts")
    op.drop_index("idx_workflow_jobs_lease", table_name="workflow_jobs")
    op.drop_index("idx_workflow_jobs_claim", table_name="workflow_jobs")
    op.drop_table("workflow_jobs")
