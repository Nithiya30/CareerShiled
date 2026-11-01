"""Add per-analysis external verification consent and results.

Revision ID: 20261031_07
Revises: 20261031_06
"""
from alembic import op
import sqlalchemy as sa


revision = "20261031_07"
down_revision = "20261031_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "analyses" in tables:
        analysis_columns = {
            column["name"] for column in sa.inspect(bind).get_columns("analyses")
        }
        if "analysis_mode" not in analysis_columns:
            op.add_column(
                "analyses",
                sa.Column(
                    "analysis_mode",
                    sa.String(length=20),
                    nullable=False,
                    server_default="job",
                )
            )

    op.create_table(
        "external_verification_consents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("selected_checks", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("consented_at", sa.DateTime(), nullable=True),
        sa.Column("execution_started_at", sa.DateTime(), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('declined', 'consented', 'running', 'completed', 'partial', 'failed')",
            name="ck_external_verification_consents_status",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_id"], ["analyses.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "analysis_id", name="uq_external_verification_analysis_id"
        ),
    )
    op.create_index(
        "ix_external_verification_consents_analysis_id",
        "external_verification_consents",
        ["analysis_id"],
        unique=False,
    )
    op.create_index(
        "ix_external_verification_consents_user_id",
        "external_verification_consents",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    row_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM external_verification_consents")
    ).scalar_one()
    if row_count:
        raise RuntimeError(
            "Refusing to drop external verification consent records; "
            "export or back them up first."
        )
    op.drop_index(
        "ix_external_verification_consents_user_id",
        table_name="external_verification_consents",
    )
    op.drop_index(
        "ix_external_verification_consents_analysis_id",
        table_name="external_verification_consents",
    )
    op.drop_table("external_verification_consents")
    # Keep analysis_mode: the application may have bootstrapped it after this
    # migration ran on a fresh SQLite database, and dropping it could lose data.
