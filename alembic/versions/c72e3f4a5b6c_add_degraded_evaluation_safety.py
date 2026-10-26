"""add degraded evaluation safety fields

Revision ID: c72e3f4a5b6c
Revises: a61f2b3c4d5e
Create Date: 2026-10-17 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c72e3f4a5b6c"
down_revision: str | Sequence[str] | None = "a61f2b3c4d5e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()),
    "postgresql",
)


def upgrade() -> None:
    with op.batch_alter_table("answer_evaluations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "evaluation_mode",
                sa.String(length=20),
                nullable=False,
                server_default="standard",
            )
        )
        batch_op.add_column(
            sa.Column(
                "score_available",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "source_quality",
                sa.String(length=20),
                nullable=False,
                server_default="unknown",
            )
        )
        batch_op.add_column(
            sa.Column(
                "source_context_json",
                json_type,
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "degradation_reasons_json",
                json_type,
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )
        for column_name in _SCORE_COLUMNS:
            batch_op.alter_column(
                column_name,
                existing_type=sa.Numeric(precision=5, scale=2),
                nullable=True,
            )


def downgrade() -> None:
    connection = op.get_bind()
    null_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM answer_evaluations "
            "WHERE total_score IS NULL OR relevance_score IS NULL "
            "OR technical_accuracy_score IS NULL OR project_specificity_score IS NULL "
            "OR structure_score IS NULL OR communication_score IS NULL "
            "OR risk_control_score IS NULL"
        )
    ).scalar_one()
    if null_count:
        raise RuntimeError(
            "Cannot downgrade while degraded evaluations with null scores exist"
        )

    with op.batch_alter_table("answer_evaluations") as batch_op:
        for column_name in _SCORE_COLUMNS:
            batch_op.alter_column(
                column_name,
                existing_type=sa.Numeric(precision=5, scale=2),
                nullable=False,
            )
        batch_op.drop_column("degradation_reasons_json")
        batch_op.drop_column("source_context_json")
        batch_op.drop_column("source_quality")
        batch_op.drop_column("score_available")
        batch_op.drop_column("evaluation_mode")


_SCORE_COLUMNS = (
    "total_score",
    "relevance_score",
    "technical_accuracy_score",
    "project_specificity_score",
    "structure_score",
    "communication_score",
    "risk_control_score",
)
