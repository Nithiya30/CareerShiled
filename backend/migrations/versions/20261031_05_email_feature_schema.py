"""Add Gmail monitoring and LinkedIn verification records.

Revision ID: 20261031_05
Revises: 20261031_04
"""
from alembic import op
import sqlalchemy as sa


revision = "20261031_05"
down_revision = "20261031_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gmail_oauth_states",
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("state_hash"),
    )
    op.create_index(
        "ix_gmail_oauth_states_user_id",
        "gmail_oauth_states",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_gmail_oauth_states_expires_at",
        "gmail_oauth_states",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "connected_gmail_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("google_subject", sa.String(length=255), nullable=False),
        sa.Column("gmail_address", sa.String(length=320), nullable=False),
        sa.Column("refresh_token_ciphertext", sa.Text(), nullable=False),
        sa.Column("token_key_version", sa.String(length=64), nullable=False),
        sa.Column("granted_scopes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("connected_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('connected', 'reauth_required', 'revoked')",
            name="ck_connected_gmail_accounts_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_connected_gmail_accounts_user_id"),
        sa.UniqueConstraint(
            "google_subject",
            name="uq_connected_gmail_accounts_google_subject",
        ),
        sa.UniqueConstraint(
            "id",
            "user_id",
            name="uq_connected_gmail_accounts_id_user_id",
        ),
    )
    op.create_index(
        "ix_connected_gmail_accounts_user_id",
        "connected_gmail_accounts",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "email_monitoring_settings",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("consent_version", sa.String(length=64), nullable=True),
        sa.Column("consented_at", sa.DateTime(), nullable=True),
        sa.Column("baseline_history_id", sa.String(length=64), nullable=True),
        sa.Column("last_history_id", sa.String(length=64), nullable=True),
        sa.Column("last_polled_at", sa.DateTime(), nullable=True),
        sa.Column("last_successful_sync_at", sa.DateTime(), nullable=True),
        sa.Column("scanned_count", sa.Integer(), nullable=False),
        sa.Column("recruitment_count", sa.Integer(), nullable=False),
        sa.Column("suspicious_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "enabled = false OR (consented_at IS NOT NULL AND consent_version IS NOT NULL)",
            name="ck_email_monitoring_settings_enabled_has_consent",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["connected_gmail_accounts.id", "connected_gmail_accounts.user_id"],
            ondelete="CASCADE",
            name="fk_email_monitoring_settings_account_user",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
        sa.UniqueConstraint(
            "account_id",
            name="uq_email_monitoring_settings_account_id",
        ),
    )
    op.create_index(
        "ix_email_monitoring_settings_account_id",
        "email_monitoring_settings",
        ["account_id"],
        unique=False,
    )
    op.create_index(
        "ix_email_monitoring_settings_last_polled_at",
        "email_monitoring_settings",
        ["last_polled_at"],
        unique=False,
    )

    op.create_table(
        "processed_gmail_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_recruitment", sa.Boolean(), nullable=True),
        sa.Column("analysis_id", sa.Integer(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "status IN ('processing', 'not_recruitment', 'analyzed', 'failed', 'skipped')",
            name="ck_processed_gmail_messages_status",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["connected_gmail_accounts.id", "connected_gmail_accounts.user_id"],
            ondelete="CASCADE",
            name="fk_processed_gmail_messages_account_user",
        ),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "gmail_message_id",
            name="uq_processed_gmail_messages_account_message",
        ),
        sa.UniqueConstraint(
            "id",
            "user_id",
            name="uq_processed_gmail_messages_id_user_id",
        ),
    )
    for column in ("account_id", "user_id", "status", "analysis_id"):
        op.create_index(
            f"ix_processed_gmail_messages_{column}",
            "processed_gmail_messages",
            [column],
            unique=False,
        )

    op.create_table(
        "suspicious_email_alerts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("processed_message_id", sa.String(length=36), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("risk_level", sa.String(length=50), nullable=False),
        sa.Column("trust_score", sa.Float(), nullable=False),
        sa.Column("subject", sa.String(length=500), nullable=True),
        sa.Column("sender_email", sa.String(length=320), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("indicators", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "severity IN ('medium', 'high')",
            name="ck_suspicious_email_alerts_severity",
        ),
        sa.ForeignKeyConstraint(
            ["processed_message_id", "user_id"],
            ["processed_gmail_messages.id", "processed_gmail_messages.user_id"],
            ondelete="CASCADE",
            name="fk_suspicious_email_alerts_message_user",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "processed_message_id",
            name="uq_suspicious_email_alerts_processed_message_id",
        ),
    )
    op.create_index(
        "ix_suspicious_email_alerts_user_id",
        "suspicious_email_alerts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_suspicious_email_alerts_is_read",
        "suspicious_email_alerts",
        ["is_read"],
        unique=False,
    )
    for name, columns in (
        ("ix_suspicious_email_alerts_user_created", ["user_id", "created_at"]),
        (
            "ix_suspicious_email_alerts_user_read_created",
            ["user_id", "is_read", "created_at"],
        ),
        (
            "ix_suspicious_email_alerts_user_severity_created",
            ["user_id", "severity", "created_at"],
        ),
    ):
        op.create_index(name, "suspicious_email_alerts", columns, unique=False)

    op.create_table(
        "linkedin_verifications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("submitted_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("matched_job_title", sa.String(length=255), nullable=True),
        sa.Column("matched_company", sa.String(length=255), nullable=True),
        sa.Column("matched_location", sa.String(length=255), nullable=True),
        sa.Column("field_comparisons", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('MATCH FOUND', 'PARTIAL MATCH', 'NO MATCH FOUND', "
            "'UNAVAILABLE', 'INSUFFICIENT INFORMATION')",
            name="ck_linkedin_verifications_status",
        ),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_linkedin_verifications_user_id",
        "linkedin_verifications",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_linkedin_verifications_analysis_id",
        "linkedin_verifications",
        ["analysis_id"],
        unique=False,
    )
    op.create_index(
        "ix_linkedin_verifications_user_created",
        "linkedin_verifications",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_linkedin_verifications_analysis_created",
        "linkedin_verifications",
        ["analysis_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = (
        "linkedin_verifications",
        "suspicious_email_alerts",
        "processed_gmail_messages",
        "email_monitoring_settings",
        "connected_gmail_accounts",
        "gmail_oauth_states",
    )
    row_counts = {
        table: bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        for table in tables
    }
    if any(row_counts.values()):
        raise RuntimeError(
            "Refusing to drop Gmail or LinkedIn feature data; export or back it up first."
        )

    for name in (
        "ix_linkedin_verifications_analysis_created",
        "ix_linkedin_verifications_user_created",
        "ix_linkedin_verifications_analysis_id",
        "ix_linkedin_verifications_user_id",
    ):
        op.drop_index(name, table_name="linkedin_verifications")
    op.drop_table("linkedin_verifications")

    for name in (
        "ix_suspicious_email_alerts_user_severity_created",
        "ix_suspicious_email_alerts_user_read_created",
        "ix_suspicious_email_alerts_user_created",
        "ix_suspicious_email_alerts_is_read",
        "ix_suspicious_email_alerts_user_id",
    ):
        op.drop_index(name, table_name="suspicious_email_alerts")
    op.drop_table("suspicious_email_alerts")

    for column in ("analysis_id", "status", "user_id", "account_id"):
        op.drop_index(
            f"ix_processed_gmail_messages_{column}",
            table_name="processed_gmail_messages",
        )
    op.drop_table("processed_gmail_messages")

    op.drop_index(
        "ix_email_monitoring_settings_last_polled_at",
        table_name="email_monitoring_settings",
    )
    op.drop_index(
        "ix_email_monitoring_settings_account_id",
        table_name="email_monitoring_settings",
    )
    op.drop_table("email_monitoring_settings")

    op.drop_index(
        "ix_connected_gmail_accounts_user_id",
        table_name="connected_gmail_accounts",
    )
    op.drop_table("connected_gmail_accounts")

    op.drop_index("ix_gmail_oauth_states_expires_at", table_name="gmail_oauth_states")
    op.drop_index("ix_gmail_oauth_states_user_id", table_name="gmail_oauth_states")
    op.drop_table("gmail_oauth_states")
