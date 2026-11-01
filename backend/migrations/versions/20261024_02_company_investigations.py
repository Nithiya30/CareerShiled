"""Add private company investigations and evidence."""
from alembic import op
import sqlalchemy as sa


revision = "20261024_02"
down_revision = "20261024_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_investigations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("contact_domain", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_company_investigations_user_id",
        "company_investigations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_company_investigations_normalized_name",
        "company_investigations",
        ["normalized_name"],
        unique=False,
    )

    op.create_table(
        "investigation_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("investigation_id", sa.String(length=36), nullable=False),
        sa.Column("finding", sa.Text(), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("retrieved_at", sa.String(length=40), nullable=True),
        sa.Column("factual_summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_reliability", sa.String(length=32), nullable=False),
        sa.Column("relevance", sa.String(length=32), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("limitations", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "status IN ('supported', 'contradicted', 'inconclusive', 'unavailable')",
            name="ck_investigation_evidence_status",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["company_investigations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investigation_evidence_investigation_id",
        "investigation_evidence",
        ["investigation_id"],
        unique=False,
    )
    op.create_index(
        "ix_investigation_evidence_content_hash",
        "investigation_evidence",
        ["content_hash"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    evidence_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM investigation_evidence")
    ).scalar_one()
    investigation_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM company_investigations")
    ).scalar_one()
    if evidence_count or investigation_count:
        raise RuntimeError(
            "Refusing to drop saved company investigations; export or back up this data first."
        )
    op.drop_index(
        "ix_investigation_evidence_content_hash",
        table_name="investigation_evidence",
    )
    op.drop_index(
        "ix_investigation_evidence_investigation_id",
        table_name="investigation_evidence",
    )
    op.drop_table("investigation_evidence")
    op.drop_index(
        "ix_company_investigations_normalized_name",
        table_name="company_investigations",
    )
    op.drop_index(
        "ix_company_investigations_user_id",
        table_name="company_investigations",
    )
    op.drop_table("company_investigations")
