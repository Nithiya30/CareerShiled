"""Add investigation-scoped entities and evidence-backed relationships."""
from alembic import op
import sqlalchemy as sa


revision = "20261024_03"
down_revision = "20261024_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigation_entities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("investigation_id", sa.String(length=36), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=500), nullable=False),
        sa.Column("normalized_value", sa.String(length=1000), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "entity_type IN ('company', 'domain', 'contact_domain', 'evidence_source')",
            name="ck_investigation_entity_type",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["company_investigations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "investigation_id",
            "entity_type",
            "normalized_value",
            name="uq_investigation_entity_value",
        ),
    )
    op.create_index(
        "ix_investigation_entities_investigation_id",
        "investigation_entities",
        ["investigation_id"],
        unique=False,
    )

    op.create_table(
        "investigation_relationships",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("investigation_id", sa.String(length=36), nullable=False),
        sa.Column("source_entity_id", sa.String(length=36), nullable=False),
        sa.Column("target_entity_id", sa.String(length=36), nullable=False),
        sa.Column("relationship_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("limitations", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status IN ('supported', 'contradicted', 'inconclusive', 'unavailable')",
            name="ck_investigation_relationship_status",
        ),
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["company_investigations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_id"],
            ["investigation_entities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"],
            ["investigation_entities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("investigation_id", "source_entity_id", "target_entity_id"):
        op.create_index(
            f"ix_investigation_relationships_{column}",
            "investigation_relationships",
            [column],
            unique=False,
        )

    op.create_table(
        "investigation_relationship_evidence",
        sa.Column("relationship_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["relationship_id"],
            ["investigation_relationships.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["investigation_evidence.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("relationship_id", "evidence_id"),
    )
    op.create_index(
        "ix_investigation_relationship_evidence_evidence_id",
        "investigation_relationship_evidence",
        ["evidence_id"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    counts = {
        table: bind.execute(
            sa.text(f"SELECT COUNT(*) FROM {table}")
        ).scalar_one()
        for table in (
            "investigation_relationship_evidence",
            "investigation_relationships",
            "investigation_entities",
        )
    }
    if any(counts.values()):
        raise RuntimeError(
            "Refusing to drop saved investigation graph data; export or back it up first."
        )
    op.drop_index(
        "ix_investigation_relationship_evidence_evidence_id",
        table_name="investigation_relationship_evidence",
    )
    op.drop_table("investigation_relationship_evidence")
    for column in ("investigation_id", "source_entity_id", "target_entity_id"):
        op.drop_index(
            f"ix_investigation_relationships_{column}",
            table_name="investigation_relationships",
        )
    op.drop_table("investigation_relationships")
    op.drop_index(
        "ix_investigation_entities_investigation_id",
        table_name="investigation_entities",
    )
    op.drop_table("investigation_entities")
