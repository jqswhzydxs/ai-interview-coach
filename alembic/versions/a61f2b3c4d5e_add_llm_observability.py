"""add llm acceptance observability fields

Revision ID: a61f2b3c4d5e
Revises: 9c8951c88817
Create Date: 2026-10-15 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a61f2b3c4d5e"
down_revision: str | Sequence[str] | None = "9c8951c88817"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


json_type = sa.JSON().with_variant(
    postgresql.JSONB(astext_type=sa.Text()),
    "postgresql",
)


def upgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(
            sa.Column("provider", sa.String(length=50), nullable=False, server_default="mock")
        )
        batch_op.add_column(
            sa.Column(
                "execution_mode",
                sa.String(length=20),
                nullable=False,
                server_default="mock",
            )
        )
        batch_op.add_column(
            sa.Column("real_call_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("latency_ms", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("input_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("output_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("total_tokens", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "fallback_reason_json",
                json_type,
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "failure_counts_json",
                json_type,
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
        batch_op.create_index(
            "idx_agent_runs_provider_mode",
            ["provider", "execution_mode"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_index("idx_agent_runs_provider_mode")
        batch_op.drop_column("failure_counts_json")
        batch_op.drop_column("fallback_reason_json")
        batch_op.drop_column("total_tokens")
        batch_op.drop_column("output_tokens")
        batch_op.drop_column("input_tokens")
        batch_op.drop_column("latency_ms")
        batch_op.drop_column("retry_count")
        batch_op.drop_column("real_call_count")
        batch_op.drop_column("execution_mode")
        batch_op.drop_column("provider")
