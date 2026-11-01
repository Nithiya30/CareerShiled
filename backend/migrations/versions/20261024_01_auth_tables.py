"""Add users and server-side authentication sessions.

Revision ID: 20261024_01
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = "20261024_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "analyses" in tables:
        columns = {column["name"] for column in inspector.get_columns("analyses")}
        if "user_id" not in columns:
            op.add_column("analyses", sa.Column("user_id", sa.String(length=120), nullable=True))
            inspector = sa.inspect(bind)
        indexes = {index["name"] for index in inspector.get_indexes("analyses")}
        if "ix_analyses_user_id" not in indexes:
            op.create_index("ix_analyses_user_id", "analyses", ["user_id"], unique=False)

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("email", sa.String(length=320), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("password_hash", sa.String(length=255), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("email"),
        )
    user_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}
    if "ix_users_email" not in user_indexes:
        op.create_index("ix_users_email", "users", ["email"], unique=False)

    tables = set(sa.inspect(bind).get_table_names())
    if "auth_sessions" not in tables:
        op.create_table(
            "auth_sessions",
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("token_hash"),
        )
    session_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("auth_sessions")
    }
    if "ix_auth_sessions_user_id" not in session_indexes:
        op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)
    if "ix_auth_sessions_expires_at" not in session_indexes:
        op.create_index(
            "ix_auth_sessions_expires_at",
            "auth_sessions",
            ["expires_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "users" in tables:
        user_count = bind.execute(sa.text("SELECT COUNT(*) FROM users")).scalar_one()
        if user_count:
            raise RuntimeError(
                "Refusing to remove authentication data; back up and migrate accounts manually."
            )
    if "auth_sessions" in tables:
        op.drop_table("auth_sessions")
    if "users" in tables:
        op.drop_index("ix_users_email", table_name="users")
        op.drop_table("users")
