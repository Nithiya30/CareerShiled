import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import engine as application_engine
from app.models import (
    Analysis,
    ConnectedGmailAccount,
    EmailMonitoringSetting,
    GmailOAuthState,
    LinkedInVerification,
    ProcessedGmailMessage,
    SuspiciousEmailAlert,
    User,
)


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _feature_engine(path):
    engine = create_engine(f"sqlite:///{path}")
    event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    tables = [
        User.__table__,
        Analysis.__table__,
        GmailOAuthState.__table__,
        ConnectedGmailAccount.__table__,
        EmailMonitoringSetting.__table__,
        ProcessedGmailMessage.__table__,
        SuspiciousEmailAlert.__table__,
        LinkedInVerification.__table__,
    ]
    User.metadata.create_all(engine, tables=tables)
    return engine


def _user(user_id):
    return User(
        id=user_id,
        email=f"{user_id}@example.test",
        name="Test User",
        password_hash="test-hash",
    )


def _account(user_id):
    return ConnectedGmailAccount(
        id=str(uuid.uuid4()),
        user_id=user_id,
        google_subject=f"google-{user_id}",
        gmail_address=f"{user_id}@gmail.test",
        refresh_token_ciphertext="ciphertext",
        token_key_version="test-key-v1",
        granted_scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )


def _create_legacy_analysis_table(engine):
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE analyses ("
                "id INTEGER PRIMARY KEY, "
                "job_title VARCHAR(255) NOT NULL, "
                "job_description TEXT NOT NULL, "
                "trust_score FLOAT NOT NULL, "
                "risk_level VARCHAR(50) NOT NULL, "
                "fraud_probability FLOAT NOT NULL, "
                "confidence FLOAT NOT NULL)"
            )
        )


def test_email_feature_schema_is_sqlite_compatible_and_minimizes_content(tmp_path):
    engine = _feature_engine(tmp_path / "feature-schema.db")
    try:
        inspector = inspect(engine)
        expected_tables = {
            "gmail_oauth_states",
            "connected_gmail_accounts",
            "email_monitoring_settings",
            "processed_gmail_messages",
            "suspicious_email_alerts",
            "linkedin_verifications",
        }
        assert expected_tables <= set(inspector.get_table_names())

        message_columns = {
            column["name"] for column in inspector.get_columns("processed_gmail_messages")
        }
        alert_columns = {
            column["name"] for column in inspector.get_columns("suspicious_email_alerts")
        }
        assert not any(
            "body" in column or "raw_email" in column
            for column in message_columns | alert_columns
        )
        assert "refresh_token_ciphertext" in {
            column["name"] for column in inspector.get_columns("connected_gmail_accounts")
        }
        message_unique_constraints = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("processed_gmail_messages")
        }
        assert ("account_id", "gmail_message_id") in message_unique_constraints
        alert_unique_constraints = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints("suspicious_email_alerts")
        }
        assert ("processed_message_id",) in alert_unique_constraints
        account_foreign_keys = inspector.get_foreign_keys("processed_gmail_messages")
        assert any(
            fk["constrained_columns"] == ["account_id", "user_id"]
            and fk["referred_columns"] == ["id", "user_id"]
            for fk in account_foreign_keys
        )
    finally:
        engine.dispose()


def test_application_sqlite_engine_enforces_foreign_keys():
    if not settings.DATABASE_URL.startswith("sqlite"):
        pytest.skip("SQLite foreign-key enforcement is only applicable to SQLite.")
    with application_engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_gmail_message_and_alert_duplicates_are_rejected(tmp_path):
    engine = _feature_engine(tmp_path / "duplicate-message.db")
    account_user_id = str(uuid.uuid4())
    account = _account(account_user_id)
    try:
        with Session(engine) as session:
            session.add_all([_user(account_user_id), account])
            session.flush()
            message = ProcessedGmailMessage(
                id=str(uuid.uuid4()),
                account_id=account.id,
                user_id=account_user_id,
                gmail_message_id="gmail-message-1",
                status="analyzed",
            )
            session.add(message)
            session.commit()

            session.add(
                ProcessedGmailMessage(
                    id=str(uuid.uuid4()),
                    account_id=account.id,
                    user_id=account_user_id,
                    gmail_message_id="gmail-message-1",
                    status="processing",
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            session.add(
                SuspiciousEmailAlert(
                    id=str(uuid.uuid4()),
                    user_id=account_user_id,
                    processed_message_id=message.id,
                    severity="high",
                    risk_level="Likely Fraudulent",
                    trust_score=25.0,
                    indicators=["Upfront fee request"],
                    explanation="Multiple risk indicators were detected.",
                )
            )
            session.commit()
            session.add(
                SuspiciousEmailAlert(
                    id=str(uuid.uuid4()),
                    user_id=account_user_id,
                    processed_message_id=message.id,
                    severity="high",
                    risk_level="Likely Fraudulent",
                    trust_score=25.0,
                    indicators=["Upfront fee request"],
                    explanation="Duplicate alert.",
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        engine.dispose()


def test_monitoring_and_alert_composite_foreign_keys_enforce_account_owner(tmp_path):
    engine = _feature_engine(tmp_path / "owner-constraints.db")
    owner_id = str(uuid.uuid4())
    other_user_id = str(uuid.uuid4())
    account = _account(owner_id)
    try:
        with Session(engine) as session:
            session.add_all([_user(owner_id), _user(other_user_id), account])
            session.commit()
            session.add(
                EmailMonitoringSetting(
                    user_id=other_user_id,
                    account_id=account.id,
                    enabled=False,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            message = ProcessedGmailMessage(
                id=str(uuid.uuid4()),
                account_id=account.id,
                user_id=owner_id,
                gmail_message_id="gmail-message-owner-check",
                status="analyzed",
            )
            session.add(message)
            session.commit()
            session.add(
                SuspiciousEmailAlert(
                    id=str(uuid.uuid4()),
                    user_id=other_user_id,
                    processed_message_id=message.id,
                    severity="medium",
                    risk_level="Needs Verification",
                    trust_score=60.0,
                    indicators=[],
                    explanation="Owner constraint check.",
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        engine.dispose()


def test_enabled_monitoring_requires_recorded_consent(tmp_path):
    engine = _feature_engine(tmp_path / "consent-constraint.db")
    user_id = str(uuid.uuid4())
    account = _account(user_id)
    try:
        with Session(engine) as session:
            session.add_all([_user(user_id), account])
            session.flush()
            session.add(
                EmailMonitoringSetting(
                    user_id=user_id,
                    account_id=account.id,
                    enabled=True,
                )
            )
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()
    finally:
        engine.dispose()


def test_alembic_upgrade_adds_feature_tables_to_existing_sqlite_schema(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "migration.db"
    legacy_engine = create_engine(f"sqlite:///{database_path}")
    try:
        _create_legacy_analysis_table(legacy_engine)
    finally:
        legacy_engine.dispose()

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "backend" / "migrations"))
    command.upgrade(config, "head")

    migrated_engine = create_engine(f"sqlite:///{database_path}")
    try:
        inspector = inspect(migrated_engine)
        tables = set(inspector.get_table_names())
        assert {
            "gmail_oauth_states",
            "connected_gmail_accounts",
            "email_monitoring_settings",
            "processed_gmail_messages",
            "suspicious_email_alerts",
            "linkedin_verifications",
        } <= tables
        assert any(
            fk["constrained_columns"] == ["account_id", "user_id"]
            and fk["referred_columns"] == ["id", "user_id"]
            for fk in inspector.get_foreign_keys("email_monitoring_settings")
        )
        assert any(
            fk["constrained_columns"] == ["processed_message_id", "user_id"]
            and fk["referred_columns"] == ["id", "user_id"]
            for fk in inspector.get_foreign_keys("suspicious_email_alerts")
        )
        setting_columns = {
            column["name"]
            for column in inspector.get_columns("email_monitoring_settings")
        }
        assert {"poll_lock_token", "poll_lock_expires_at"} <= setting_columns
    finally:
        migrated_engine.dispose()


def test_gmail_monitoring_lease_migration_preserves_existing_settings(
    tmp_path, monkeypatch
):
    database_path = tmp_path / "monitoring-lease.db"
    legacy_engine = create_engine(f"sqlite:///{database_path}")
    try:
        _create_legacy_analysis_table(legacy_engine)
    finally:
        legacy_engine.dispose()

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "backend" / "migrations"))
    command.upgrade(config, "20261031_05")

    user_id = str(uuid.uuid4())
    account_id = str(uuid.uuid4())
    migration_engine = create_engine(f"sqlite:///{database_path}")
    try:
        with migration_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, email, name, password_hash, created_at) "
                    "VALUES (:id, :email, :name, :password_hash, :created_at)"
                ),
                {
                    "id": user_id,
                    "email": f"{user_id}@example.test",
                    "name": "Lease Migration",
                    "password_hash": "test-hash",
                    "created_at": "2026-10-31 00:00:00",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO connected_gmail_accounts "
                    "(id, user_id, google_subject, gmail_address, "
                    "refresh_token_ciphertext, token_key_version, granted_scopes, "
                    "status, connected_at, updated_at) "
                    "VALUES (:id, :user_id, :google_subject, :gmail_address, "
                    ":ciphertext, :key_version, :scopes, :status, :connected_at, :updated_at)"
                ),
                {
                    "id": account_id,
                    "user_id": user_id,
                    "google_subject": f"google-{user_id}",
                    "gmail_address": f"{user_id}@gmail.test",
                    "ciphertext": "encrypted-placeholder",
                    "key_version": "test-v1",
                    "scopes": '["https://www.googleapis.com/auth/gmail.readonly"]',
                    "status": "connected",
                    "connected_at": "2026-10-31 00:00:00",
                    "updated_at": "2026-10-31 00:00:00",
                },
            )
            connection.execute(
                text(
                    "INSERT INTO email_monitoring_settings "
                    "(user_id, account_id, enabled, consent_version, consented_at, "
                    "baseline_history_id, last_history_id, last_polled_at, "
                    "last_successful_sync_at, scanned_count, recruitment_count, "
                    "suspicious_count, last_error_code, created_at, updated_at) "
                    "VALUES (:user_id, :account_id, 0, 'consent-v1', "
                    "'2026-10-30 00:00:00', '987', '991', NULL, NULL, 4, 3, 1, "
                    "NULL, '2026-10-30 00:00:00', '2026-10-30 00:00:00')"
                ),
                {"user_id": user_id, "account_id": account_id},
            )
    except Exception:
        migration_engine.dispose()
        raise

    command.upgrade(config, "head")
    try:
        with migration_engine.connect() as connection:
            setting = connection.execute(
                text(
                    "SELECT baseline_history_id, last_history_id, scanned_count, "
                    "recruitment_count, suspicious_count, poll_lock_token, "
                    "poll_lock_expires_at FROM email_monitoring_settings "
                    "WHERE user_id = :user_id"
                ),
                {"user_id": user_id},
            ).one()
        assert tuple(setting) == ("987", "991", 4, 3, 1, None, None)
    finally:
        migration_engine.dispose()
