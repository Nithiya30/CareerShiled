"""Add leases and bounded retries to external verification runs.

Revision ID: 20261031_08
Revises: 20261031_07
"""
from alembic import op
import sqlalchemy as sa


revision = "20261031_08"
down_revision = "20261031_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "external_verification_consents",
        sa.Column("execution_lease_expires_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "external_verification_consents",
        sa.Column("execution_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "external_verification_consents",
        sa.Column(
            "execution_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "external_verification_consents",
        sa.Column("failure_reason", sa.String(length=64), nullable=True),
    )
    op.execute(
        "UPDATE external_verification_consents "
        "SET execution_attempts = 1 "
        "WHERE status IN ('running', 'partial', 'failed')"
    )


def downgrade() -> None:
    bind = op.get_bind()
    attempts = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM external_verification_consents "
            "WHERE execution_attempts > 0 OR execution_lease_expires_at IS NOT NULL "
            "OR execution_id IS NOT NULL OR failure_reason IS NOT NULL"
        )
    ).scalar_one()
    if attempts:
        raise RuntimeError(
            "Refusing to remove external verification run recovery history."
        )
    op.drop_column("external_verification_consents", "failure_reason")
    op.drop_column("external_verification_consents", "execution_attempts")
    op.drop_column("external_verification_consents", "execution_id")
    op.drop_column(
        "external_verification_consents", "execution_lease_expires_at"
    )
