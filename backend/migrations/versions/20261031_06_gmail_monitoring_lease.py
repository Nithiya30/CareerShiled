"""Add a database-backed lease for Gmail monitoring polls.

Revision ID: 20261031_06
Revises: 20261031_05
"""
from alembic import op
import sqlalchemy as sa


revision = "20261031_06"
down_revision = "20261031_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("email_monitoring_settings") as batch_op:
        batch_op.add_column(sa.Column("poll_lock_token", sa.String(length=64)))
        batch_op.add_column(sa.Column("poll_lock_expires_at", sa.DateTime()))
        batch_op.create_check_constraint(
            "ck_email_monitoring_settings_poll_lock_pair",
            "(poll_lock_token IS NULL AND poll_lock_expires_at IS NULL) OR "
            "(poll_lock_token IS NOT NULL AND poll_lock_expires_at IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("email_monitoring_settings") as batch_op:
        batch_op.drop_constraint(
            "ck_email_monitoring_settings_poll_lock_pair",
            type_="check",
        )
        batch_op.drop_column("poll_lock_expires_at")
        batch_op.drop_column("poll_lock_token")
