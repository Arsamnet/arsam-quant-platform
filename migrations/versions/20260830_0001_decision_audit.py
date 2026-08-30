"""Create durable decision audit records.

Revision ID: 20260830_0001
Revises: None
Create Date: 2026-08-30
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260830_0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create the initial idempotent audit table and lookup indexes."""
    op.create_table(
        "decision_audit_records",
        sa.Column("decision_id", sa.Uuid(), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("node_id", sa.String(length=64), nullable=False),
        sa.Column("market_snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("strategy_name", sa.String(length=128), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("signal_id", sa.Uuid(), nullable=True),
        sa.Column("ai_status", sa.String(length=32), nullable=False),
        sa.Column("risk_decision_id", sa.Uuid(), nullable=True),
        sa.Column("risk_approved", sa.Boolean(), nullable=False),
        sa.Column("risk_reasons", sa.JSON(), nullable=False),
        sa.Column("execution_id", sa.Uuid(), nullable=True),
        sa.Column("execution_status", sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.UniqueConstraint("nonce"),
    )
    op.create_index(
        op.f("ix_decision_audit_records_node_id"),
        "decision_audit_records",
        ["node_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_decision_audit_records_symbol"),
        "decision_audit_records",
        ["symbol"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the initial audit table."""
    op.drop_index(op.f("ix_decision_audit_records_symbol"), table_name="decision_audit_records")
    op.drop_index(op.f("ix_decision_audit_records_node_id"), table_name="decision_audit_records")
    op.drop_table("decision_audit_records")
