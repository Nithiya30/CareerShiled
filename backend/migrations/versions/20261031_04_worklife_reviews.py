"""Add user-submitted WorkLife reviews and moderation records."""
from alembic import op
import sqlalchemy as sa


revision = "20261031_04"
down_revision = "20261024_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "worklife_companies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name"),
    )
    op.create_index(
        "ix_worklife_companies_normalized_name",
        "worklife_companies",
        ["normalized_name"],
        unique=True,
    )

    rating_columns = (
        "work_life_balance",
        "salary_satisfaction",
        "management_rating",
        "career_growth",
        "learning_opportunities",
        "work_pressure",
        "job_security",
        "overall_rating",
    )
    constraints = [
        sa.CheckConstraint(
            "employment_status IN ('current', 'former')",
            name="ck_worklife_review_employment_status",
        ),
        sa.CheckConstraint(
            "moderation_status IN ('pending', 'approved', 'rejected', 'withdrawn')",
            name="ck_worklife_review_moderation_status",
        ),
        *[
            sa.CheckConstraint(
                f"{column} IS NULL OR ({column} >= 1 AND {column} <= 5)",
                name=f"ck_worklife_review_{column}",
            )
            for column in rating_columns
        ],
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["worklife_companies.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["moderated_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "user_id",
            name="uq_worklife_review_company_user",
        ),
    ]
    op.create_table(
        "worklife_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("job_role", sa.String(length=150), nullable=False),
        sa.Column("department", sa.String(length=150), nullable=True),
        sa.Column("employment_status", sa.String(length=16), nullable=False),
        *[
            sa.Column(column, sa.Integer(), nullable=False)
            for column in rating_columns
        ],
        sa.Column("review_text", sa.Text(), nullable=False),
        sa.Column("moderation_status", sa.String(length=16), nullable=False),
        sa.Column("sentiment", sa.String(length=16), nullable=True),
        sa.Column("topics", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("moderated_at", sa.DateTime(), nullable=True),
        sa.Column("moderated_by", sa.String(length=36), nullable=True),
        sa.Column("moderation_note", sa.String(length=500), nullable=True),
        *constraints,
    )
    for column in ("company_id", "user_id", "moderation_status"):
        op.create_index(
            f"ix_worklife_reviews_{column}",
            "worklife_reviews",
            [column],
            unique=False,
        )

    op.create_table(
        "worklife_review_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.Integer(), nullable=False),
        sa.Column("reporter_user_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("details", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'reviewed', 'dismissed')",
            name="ck_worklife_review_report_status",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["worklife_reviews.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reporter_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "review_id",
            "reporter_user_id",
            name="uq_worklife_review_report_review_reporter",
        ),
    )
    for column in ("review_id", "reporter_user_id", "status"):
        op.create_index(
            f"ix_worklife_review_reports_{column}",
            "worklife_review_reports",
            [column],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    counts = {
        table: bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        for table in (
            "worklife_review_reports",
            "worklife_reviews",
            "worklife_companies",
        )
    }
    if any(counts.values()):
        raise RuntimeError(
            "Refusing to drop WorkLife review data; export or back it up first."
        )
    for column in ("review_id", "reporter_user_id", "status"):
        op.drop_index(
            f"ix_worklife_review_reports_{column}",
            table_name="worklife_review_reports",
        )
    op.drop_table("worklife_review_reports")
    for column in ("company_id", "user_id", "moderation_status"):
        op.drop_index(
            f"ix_worklife_reviews_{column}",
            table_name="worklife_reviews",
        )
    op.drop_table("worklife_reviews")
    op.drop_index(
        "ix_worklife_companies_normalized_name",
        table_name="worklife_companies",
    )
    op.drop_table("worklife_companies")
