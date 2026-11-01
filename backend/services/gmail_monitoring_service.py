import asyncio
import base64
import logging
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import inspect, or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.models import (
    ConnectedGmailAccount,
    EmailMonitoringSetting,
    ProcessedGmailMessage,
    SuspiciousEmailAlert,
    User,
)
from app.schemas import JobAnalysisRequest
from services.gmail_oauth_service import (
    GMAIL_READONLY_SCOPE,
    GmailOAuthError,
    GmailOAuthUnavailable,
    GmailReauthRequired,
    GmailTokenEncryptionError,
    refresh_access_token,
)
from services.job_analysis_service import analyze_job_pipeline


logger = logging.getLogger(__name__)

GMAIL_API_BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"
GMAIL_API_TIMEOUT_SECONDS = 12.0
GMAIL_API_RETRIES = 3
GMAIL_API_RETRY_BASE_SECONDS = 0.5
GMAIL_POLL_INTERVAL_SECONDS = 60
GMAIL_POLL_MAX_MESSAGES = 25
GMAIL_HISTORY_PAGE_SIZE = 100
GMAIL_POLL_LEASE_SECONDS = 300
GMAIL_STALE_MESSAGE_SECONDS = 900
GMAIL_MAX_MESSAGE_BYTES = 1_000_000
GMAIL_MAX_BODY_CHARACTERS = 80_000
MONITORING_CONSENT_VERSION = "gmail-monitoring-v1"
RISK_LEVELS = {"Likely Legitimate", "Needs Verification", "Likely Fraudulent"}


class GmailMonitoringError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class GmailHistoryExpired(GmailMonitoringError):
    def __init__(self):
        super().__init__("history_cursor_expired")


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fragments: list[str] = []

    def handle_data(self, data: str) -> None:
        self.fragments.append(data)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def monitoring_schema_available() -> bool:
    inspector = inspect(engine)
    required_tables = {
        "connected_gmail_accounts",
        "email_monitoring_settings",
        "processed_gmail_messages",
        "suspicious_email_alerts",
    }
    if not required_tables.issubset(set(inspector.get_table_names())):
        return False
    settings_columns = {
        column["name"]
        for column in inspector.get_columns("email_monitoring_settings")
    }
    return {"poll_lock_token", "poll_lock_expires_at"} <= settings_columns


def _decode_base64url(value: str) -> str:
    try:
        padding = "=" * (-len(value) % 4)
        raw = base64.urlsafe_b64decode(value + padding)
        return raw.decode("utf-8", errors="replace")
    except (ValueError, UnicodeEncodeError):
        return ""


def _plain_text_from_payload(payload: dict[str, Any]) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    stack = [payload]
    while stack:
        part = stack.pop()
        if not isinstance(part, dict):
            continue
        mime_type = part.get("mimeType")
        body = part.get("body")
        encoded = body.get("data") if isinstance(body, dict) else None
        if isinstance(encoded, str) and mime_type in {"text/plain", "text/html"}:
            decoded = _decode_base64url(encoded)
            if mime_type == "text/plain":
                plain_parts.append(decoded)
            else:
                html_parts.append(decoded)
        children = part.get("parts")
        if isinstance(children, list):
            stack.extend(reversed(children))

    selected = "\n".join(plain_parts).strip()
    if not selected and html_parts:
        parser = _HTMLTextExtractor()
        for html in html_parts:
            parser.feed(html)
        selected = "\n".join(parser.fragments).strip()
    return selected[:GMAIL_MAX_BODY_CHARACTERS]


def _headers(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    headers = payload.get("headers")
    if not isinstance(headers, list):
        return {}
    values: dict[str, str] = {}
    for header in headers:
        if not isinstance(header, dict):
            continue
        name, value = header.get("name"), header.get("value")
        if isinstance(name, str) and isinstance(value, str):
            values.setdefault(name.lower(), value)
    return values


def _google_get(
    access_token: str,
    resource: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{GMAIL_API_BASE_URL}/{resource}"
    headers = {"Authorization": f"Bearer {access_token}"}
    for attempt in range(GMAIL_API_RETRIES):
        try:
            with httpx.Client(timeout=GMAIL_API_TIMEOUT_SECONDS) as client:
                response = client.get(url, headers=headers, params=params)
        except httpx.RequestError:
            if attempt + 1 == GMAIL_API_RETRIES:
                raise GmailMonitoringError("google_api_unavailable") from None
            time.sleep(GMAIL_API_RETRY_BASE_SECONDS * (2**attempt))
            continue

        if response.status_code == 404 and resource == "history":
            raise GmailHistoryExpired()
        if response.status_code in {429, 500, 502, 503, 504}:
            if attempt + 1 == GMAIL_API_RETRIES:
                raise GmailMonitoringError("google_api_rate_limited" if response.status_code == 429 else "google_api_unavailable")
            retry_after = response.headers.get("Retry-After")
            try:
                delay = min(float(retry_after), 10.0) if retry_after else GMAIL_API_RETRY_BASE_SECONDS * (2**attempt)
            except ValueError:
                delay = GMAIL_API_RETRY_BASE_SECONDS * (2**attempt)
            time.sleep(max(delay, 0.0))
            continue
        if response.status_code in {401, 403}:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            reasons = []
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    raw_errors = error.get("errors", [])
                    if not isinstance(raw_errors, list):
                        raw_errors = []
                    reasons = [
                        entry.get("reason")
                        for entry in raw_errors
                        if isinstance(entry, dict)
                    ]
            if response.status_code == 403 and any(
                reason in {"rateLimitExceeded", "userRateLimitExceeded"}
                for reason in reasons
            ):
                if attempt + 1 == GMAIL_API_RETRIES:
                    raise GmailMonitoringError("google_api_rate_limited")
                time.sleep(GMAIL_API_RETRY_BASE_SECONDS * (2**attempt))
                continue
            raise GmailReauthRequired("Reconnect the Google account to continue.")
        if response.status_code >= 400:
            raise GmailMonitoringError("google_api_unavailable")
        try:
            payload = response.json()
        except ValueError:
            raise GmailMonitoringError("google_api_invalid_response") from None
        if not isinstance(payload, dict):
            raise GmailMonitoringError("google_api_invalid_response")
        return payload
    raise GmailMonitoringError("google_api_unavailable")


def _profile_history_id(access_token: str) -> str:
    profile = _google_get(access_token, "profile")
    history_id = profile.get("historyId")
    if not isinstance(history_id, str) or not history_id.isdigit():
        raise GmailMonitoringError("google_api_invalid_response")
    return history_id


def establish_monitoring_baseline(
    db: Session,
    user_id: str,
) -> EmailMonitoringSetting:
    setting = (
        db.query(EmailMonitoringSetting)
        .filter(EmailMonitoringSetting.user_id == user_id)
        .first()
    )
    initial_setting_updated_at = (
        setting.updated_at if setting is not None else None
    )
    account = (
        db.query(ConnectedGmailAccount)
        .filter(ConnectedGmailAccount.user_id == user_id)
        .first()
    )
    if account is None:
        raise GmailMonitoringError("gmail_account_not_connected")
    if account.status != "connected":
        if setting is not None and setting.enabled:
            setting.enabled = False
            setting.poll_lock_token = None
            setting.poll_lock_expires_at = None
            setting.last_error_code = "reauth_required"
            db.commit()
        raise GmailReauthRequired("Reconnect the Google account to continue.")
    if GMAIL_READONLY_SCOPE not in (account.granted_scopes or []):
        if setting is not None and setting.enabled:
            setting.enabled = False
            setting.poll_lock_token = None
            setting.poll_lock_expires_at = None
            setting.last_error_code = "reauth_required"
            db.commit()
        raise GmailReauthRequired("Reconnect the Google account to continue.")
    if setting is not None and setting.enabled:
        return setting

    access_token = refresh_access_token(db, account)
    history_id = _profile_history_id(access_token)
    now = _utcnow()
    db.expire_all()
    account = (
        db.query(ConnectedGmailAccount)
        .filter(
            ConnectedGmailAccount.user_id == user_id,
            ConnectedGmailAccount.id == account.id,
        )
        .first()
    )
    if account is None or account.status != "connected":
        raise GmailMonitoringError("gmail_account_not_connected")
    current_setting = (
        db.query(EmailMonitoringSetting)
        .filter(EmailMonitoringSetting.user_id == user_id)
        .first()
    )
    if setting is not None and current_setting is None:
        raise GmailMonitoringError("gmail_account_not_connected")
    if (
        setting is not None
        and current_setting is not None
        and current_setting.updated_at != initial_setting_updated_at
    ):
        if current_setting.enabled:
            return current_setting
        raise GmailMonitoringError("monitoring_state_changed")
    if setting is None and current_setting is not None and current_setting.enabled:
        return current_setting
    setting = current_setting
    if setting is None:
        setting = EmailMonitoringSetting(
            user_id=user_id,
            account_id=account.id,
            enabled=False,
        )
        db.add(setting)

    setting.account_id = account.id
    setting.baseline_history_id = history_id
    setting.last_history_id = history_id
    setting.consented_at = now
    setting.consent_version = MONITORING_CONSENT_VERSION
    setting.enabled = True
    setting.last_error_code = None
    setting.poll_lock_token = None
    setting.poll_lock_expires_at = None
    setting.updated_at = now
    db.commit()
    db.refresh(setting)
    return setting


def _claim_poll_lease(
    db: Session,
    account_id: str,
    user_id: str,
) -> str | None:
    now = _utcnow()
    token = secrets.token_hex(32)
    claimed = (
        db.query(EmailMonitoringSetting)
        .filter(
            EmailMonitoringSetting.account_id == account_id,
            EmailMonitoringSetting.user_id == user_id,
            EmailMonitoringSetting.enabled.is_(True),
            or_(
                EmailMonitoringSetting.poll_lock_expires_at.is_(None),
                EmailMonitoringSetting.poll_lock_expires_at <= now,
            ),
        )
        .update(
            {
                EmailMonitoringSetting.poll_lock_token: token,
                EmailMonitoringSetting.poll_lock_expires_at: now
                + timedelta(seconds=GMAIL_POLL_LEASE_SECONDS),
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return token if claimed == 1 else None


def _renew_poll_lease(
    db: Session,
    account_id: str,
    user_id: str,
    lock_token: str,
) -> bool:
    renewed = (
        db.query(EmailMonitoringSetting)
        .filter(
            EmailMonitoringSetting.account_id == account_id,
            EmailMonitoringSetting.user_id == user_id,
            EmailMonitoringSetting.enabled.is_(True),
            EmailMonitoringSetting.poll_lock_token == lock_token,
        )
        .update(
            {
                EmailMonitoringSetting.poll_lock_expires_at: _utcnow()
                + timedelta(seconds=GMAIL_POLL_LEASE_SECONDS),
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return renewed == 1


def _lease_is_active(
    db: Session,
    account_id: str,
    user_id: str,
    lock_token: str,
    stop_event: threading.Event,
) -> bool:
    if stop_event.is_set():
        return False
    return (
        db.query(EmailMonitoringSetting.user_id)
        .filter(
            EmailMonitoringSetting.account_id == account_id,
            EmailMonitoringSetting.user_id == user_id,
            EmailMonitoringSetting.enabled.is_(True),
            EmailMonitoringSetting.poll_lock_token == lock_token,
            ConnectedGmailAccount.status == "connected",
        )
        .join(
            ConnectedGmailAccount,
            ConnectedGmailAccount.id == EmailMonitoringSetting.account_id,
        )
        .first()
        is not None
    )


def _claim_message(
    db: Session,
    *,
    account_id: str,
    user_id: str,
    gmail_message_id: str,
) -> ProcessedGmailMessage | None:
    now = _utcnow()
    message = ProcessedGmailMessage(
        id=str(uuid.uuid4()),
        account_id=account_id,
        user_id=user_id,
        gmail_message_id=gmail_message_id,
        status="processing",
        created_at=now,
    )
    db.add(message)
    try:
        db.commit()
        db.refresh(message)
        return message
    except IntegrityError:
        db.rollback()

    stale_before = now - timedelta(seconds=GMAIL_STALE_MESSAGE_SECONDS)
    reclaimed = (
        db.query(ProcessedGmailMessage)
        .filter(
            ProcessedGmailMessage.account_id == account_id,
            ProcessedGmailMessage.gmail_message_id == gmail_message_id,
            ProcessedGmailMessage.status == "processing",
            ProcessedGmailMessage.created_at <= stale_before,
        )
        .update(
            {
                ProcessedGmailMessage.status: "processing",
                ProcessedGmailMessage.created_at: now,
                ProcessedGmailMessage.last_error_code: None,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    if reclaimed != 1:
        return None
    return (
        db.query(ProcessedGmailMessage)
        .filter(
            ProcessedGmailMessage.account_id == account_id,
            ProcessedGmailMessage.gmail_message_id == gmail_message_id,
        )
        .first()
    )


def _finish_message(
    db: Session,
    message: ProcessedGmailMessage,
    *,
    status: str,
    error_code: str | None = None,
) -> None:
    message.status = status
    message.last_error_code = error_code
    message.processed_at = _utcnow()
    db.commit()


def _received_before_baseline(
    metadata: dict[str, Any],
    consented_at: datetime,
) -> bool:
    raw_internal_date = metadata.get("internalDate")
    try:
        received_at = datetime.fromtimestamp(
            int(raw_internal_date) / 1000,
            tz=timezone.utc,
        ).replace(tzinfo=None)
    except (TypeError, ValueError, OSError, OverflowError):
        return True
    return received_at < consented_at


def _mark_reauth_required(db: Session, account_id: str) -> None:
    account = (
        db.query(ConnectedGmailAccount)
        .filter(ConnectedGmailAccount.id == account_id)
        .first()
    )
    if account is None:
        return
    if account.status == "connected":
        account.status = "reauth_required"
        account.updated_at = _utcnow()
    setting = (
        db.query(EmailMonitoringSetting)
        .filter(EmailMonitoringSetting.account_id == account_id)
        .first()
    )
    if setting is not None:
        setting.enabled = False
        setting.poll_lock_token = None
        setting.poll_lock_expires_at = None
        setting.last_error_code = "reauth_required"
    db.commit()


def _mark_sync_error(
    db: Session,
    user_id: str,
    account_id: str,
    code: str,
) -> None:
    setting = (
        db.query(EmailMonitoringSetting)
        .filter(
            EmailMonitoringSetting.user_id == user_id,
            EmailMonitoringSetting.account_id == account_id,
        )
        .first()
    )
    if setting is not None:
        setting.last_error_code = code[:64]
        setting.last_polled_at = _utcnow()
        db.commit()


def _process_message(
    db: Session,
    *,
    account: ConnectedGmailAccount,
    setting: EmailMonitoringSetting,
    lock_token: str,
    access_token: str,
    gmail_message_id: str,
    stop_event: threading.Event,
) -> bool:
    message = _claim_message(
        db,
        account_id=account.id,
        user_id=account.user_id,
        gmail_message_id=gmail_message_id,
    )
    if message is None:
        return False
    if not _lease_is_active(
        db, account.id, account.user_id, lock_token, stop_event
    ):
        _finish_message(
            db, message, status="skipped", error_code="monitoring_paused"
        )
        return True

    try:
        encoded_id = quote(gmail_message_id, safe="")
        metadata = _google_get(
            access_token,
            f"messages/{encoded_id}",
            params={
                "format": "metadata",
                "metadataHeaders": ["From", "Subject"],
            },
        )
        if _received_before_baseline(metadata, setting.consented_at):
            _finish_message(
                db, message, status="skipped", error_code="pre_consent_message"
            )
            return True
        try:
            message_size = int(metadata.get("sizeEstimate", 0))
        except (TypeError, ValueError):
            message_size = GMAIL_MAX_MESSAGE_BYTES + 1
        if message_size > GMAIL_MAX_MESSAGE_BYTES:
            _finish_message(
                db, message, status="skipped", error_code="message_too_large"
            )
            return True
        if not _lease_is_active(
            db, account.id, account.user_id, lock_token, stop_event
        ):
            _finish_message(
                db, message, status="skipped", error_code="monitoring_paused"
            )
            return True

        full = _google_get(
            access_token,
            f"messages/{encoded_id}",
            params={"format": "full"},
        )
        if not _lease_is_active(
            db, account.id, account.user_id, lock_token, stop_event
        ):
            _finish_message(
                db, message, status="skipped", error_code="monitoring_paused"
            )
            return True
        payload = full.get("payload")
        body = _plain_text_from_payload(payload) if isinstance(payload, dict) else ""
        if not body.strip():
            _finish_message(db, message, status="skipped", error_code="no_text_body")
            return True

        headers = _headers(metadata.get("payload"))
        subject = headers.get("subject", "").strip()[:500]
        sender = parseaddr(headers.get("from", ""))[1][:320]
        user = db.query(User).filter(User.id == account.user_id).first()
        if user is None:
            _finish_message(db, message, status="failed", error_code="user_missing")
            return True
        if not _lease_is_active(
            db, account.id, account.user_id, lock_token, stop_event
        ):
            _finish_message(
                db, message, status="skipped", error_code="monitoring_paused"
            )
            return True

        request = JobAnalysisRequest(
            job_title=subject or "Email message",
            analysis_mode="private_email",
            recruiter_email=sender,
            job_description=body,
        )
        result = analyze_job_pipeline(request, db, user, persist=False)
        if not _lease_is_active(
            db, account.id, account.user_id, lock_token, stop_event
        ):
            _finish_message(
                db, message, status="skipped", error_code="monitoring_paused"
            )
            return True

        risk_level = result.get("risk_level")
        if risk_level not in RISK_LEVELS:
            raise GmailMonitoringError("analysis_invalid_result")

        message.is_recruitment = None
        message.status = "analyzed"
        message.processed_at = _utcnow()
        message.last_error_code = None
        now = _utcnow()
        suspicious = risk_level in {"Needs Verification", "Likely Fraudulent"}
        setting_updates: dict[Any, Any] = {
            EmailMonitoringSetting.scanned_count:
                EmailMonitoringSetting.scanned_count + 1,
            EmailMonitoringSetting.last_error_code: None,
            EmailMonitoringSetting.last_polled_at: now,
        }
        if suspicious:
            setting_updates[EmailMonitoringSetting.suspicious_count] = (
                EmailMonitoringSetting.suspicious_count + 1
            )
        claim_still_active = (
            db.query(EmailMonitoringSetting)
            .filter(
                EmailMonitoringSetting.user_id == account.user_id,
                EmailMonitoringSetting.account_id == account.id,
                EmailMonitoringSetting.enabled.is_(True),
                EmailMonitoringSetting.poll_lock_token == lock_token,
            )
            .update(setting_updates, synchronize_session=False)
        )
        if claim_still_active != 1:
            message.status = "skipped"
            message.last_error_code = "monitoring_paused"
        elif suspicious:
            severity = "medium" if risk_level == "Needs Verification" else "high"
            db.add(
                SuspiciousEmailAlert(
                    id=str(uuid.uuid4()),
                    user_id=account.user_id,
                    processed_message_id=message.id,
                    severity=severity,
                    risk_level=risk_level,
                    trust_score=float(result["trust_score"]),
                    subject=subject or None,
                    sender_email=sender or None,
                    indicators=[],
                    explanation=(
                        "Private email analysis identified risk indicators. "
                        "Review the message carefully before responding."
                    ),
                    is_read=False,
                    created_at=now,
                )
            )
        db.commit()
        return True
    except GmailReauthRequired:
        _mark_reauth_required(db, account.id)
        _finish_message(db, message, status="failed", error_code="reauth_required")
        raise
    except GmailMonitoringError as exc:
        _finish_message(db, message, status="failed", error_code=exc.code)
        raise
    except GmailOAuthError:
        _finish_message(db, message, status="failed", error_code="credential_unavailable")
        raise GmailMonitoringError("credential_unavailable") from None
    except Exception:
        _finish_message(db, message, status="failed", error_code="analysis_failed")
        raise


def poll_account(
    user_id: str,
    account_id: str,
    stop_event: threading.Event,
) -> None:
    if stop_event.is_set():
        return
    with SessionLocal() as db:
        lock_token = _claim_poll_lease(db, account_id, user_id)
        if lock_token is None:
            return
        try:
            account = (
                db.query(ConnectedGmailAccount)
                .filter(
                    ConnectedGmailAccount.id == account_id,
                    ConnectedGmailAccount.user_id == user_id,
                    ConnectedGmailAccount.status == "connected",
                )
                .first()
            )
            setting = (
                db.query(EmailMonitoringSetting)
                .filter(
                    EmailMonitoringSetting.account_id == account_id,
                    EmailMonitoringSetting.user_id == user_id,
                    EmailMonitoringSetting.enabled.is_(True),
                )
                .first()
            )
            if account is None or setting is None:
                return
            if (
                not setting.last_history_id
                or not setting.baseline_history_id
                or setting.consented_at is None
            ):
                _mark_sync_error(db, user_id, account_id, "missing_monitoring_baseline")
                return

            try:
                access_token = refresh_access_token(db, account)
            except GmailReauthRequired:
                _mark_reauth_required(db, account_id)
                _mark_sync_error(db, user_id, account_id, "reauth_required")
                return
            except (GmailOAuthUnavailable, GmailTokenEncryptionError):
                _mark_sync_error(db, user_id, account_id, "credential_unavailable")
                return
            if not _renew_poll_lease(
                db, account_id, user_id, lock_token
            ) or not _lease_is_active(
                db, account_id, user_id, lock_token, stop_event
            ):
                return

            try:
                pages: list[dict[str, Any]] = []
                page_token: str | None = None
                while True:
                    if not _lease_is_active(
                        db, account_id, user_id, lock_token, stop_event
                    ):
                        return
                    params: dict[str, Any] = {
                        "startHistoryId": setting.last_history_id,
                        "historyTypes": "messageAdded",
                        "maxResults": GMAIL_HISTORY_PAGE_SIZE,
                    }
                    if page_token:
                        params["pageToken"] = page_token
                    page = _google_get(access_token, "history", params=params)
                    pages.append(page)
                    next_token = page.get("nextPageToken")
                    if not isinstance(next_token, str) or not next_token:
                        break
                    page_token = next_token
            except GmailHistoryExpired:
                if _lease_is_active(db, account_id, user_id, lock_token, stop_event):
                    fresh_history_id = _profile_history_id(access_token)
                    setting = (
                        db.query(EmailMonitoringSetting)
                        .filter(
                            EmailMonitoringSetting.user_id == user_id,
                            EmailMonitoringSetting.account_id == account_id,
                            EmailMonitoringSetting.poll_lock_token == lock_token,
                        )
                        .first()
                    )
                    if setting is not None:
                        setting.baseline_history_id = fresh_history_id
                        setting.last_history_id = fresh_history_id
                        setting.consented_at = _utcnow()
                        setting.last_error_code = "history_cursor_expired"
                        setting.last_polled_at = _utcnow()
                        db.commit()
                return
            except GmailReauthRequired:
                _mark_reauth_required(db, account_id)
                _mark_sync_error(db, user_id, account_id, "reauth_required")
                return
            except GmailMonitoringError as exc:
                _mark_sync_error(db, user_id, account_id, exc.code)
                return

            seen_ids: set[str] = set()
            completed_history = True
            claimed_count = 0
            final_history_id = setting.last_history_id
            for page_index, page in enumerate(pages):
                history_id = page.get("historyId")
                if isinstance(history_id, str) and history_id.isdigit():
                    final_history_id = history_id
                records = page.get("history", [])
                if not isinstance(records, list):
                    records = []
                for record in records:
                    if not isinstance(record, dict):
                        continue
                    additions = record.get("messagesAdded", [])
                    if not isinstance(additions, list):
                        continue
                    for addition in additions:
                        item = addition.get("message") if isinstance(addition, dict) else None
                        message_id = item.get("id") if isinstance(item, dict) else None
                        if not isinstance(message_id, str) or not message_id or message_id in seen_ids:
                            continue
                        seen_ids.add(message_id)
                        if not _lease_is_active(
                            db, account_id, user_id, lock_token, stop_event
                        ):
                            return
                        if claimed_count >= GMAIL_POLL_MAX_MESSAGES:
                            completed_history = False
                            break
                        try:
                            processed_new = _process_message(
                                db,
                                account=account,
                                setting=setting,
                                lock_token=lock_token,
                                access_token=access_token,
                                gmail_message_id=message_id,
                                stop_event=stop_event,
                            )
                            if processed_new:
                                claimed_count += 1
                        except GmailReauthRequired:
                            _mark_sync_error(db, user_id, account_id, "reauth_required")
                            return
                        except GmailMonitoringError as exc:
                            _mark_sync_error(db, user_id, account_id, exc.code)
                            return
                        except Exception:
                            logger.error("Gmail message analysis failed (analysis_failed).")
                            _mark_sync_error(db, user_id, account_id, "analysis_failed")
                            return
                    if not completed_history:
                        break
                if not completed_history:
                    break
                if page_index < len(pages) - 1:
                    continue

            if not completed_history:
                return
            if not _lease_is_active(db, account_id, user_id, lock_token, stop_event):
                return
            current_setting = (
                db.query(EmailMonitoringSetting)
                .filter(
                    EmailMonitoringSetting.user_id == user_id,
                    EmailMonitoringSetting.account_id == account_id,
                    EmailMonitoringSetting.enabled.is_(True),
                    EmailMonitoringSetting.poll_lock_token == lock_token,
                )
                .first()
            )
            if current_setting is not None:
                current_setting.last_history_id = final_history_id
                current_setting.last_successful_sync_at = _utcnow()
                current_setting.last_polled_at = _utcnow()
                current_setting.last_error_code = None
                db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.error("Gmail monitoring database operation failed.")
            _mark_sync_error(db, user_id, account_id, "database_unavailable")
        except GmailMonitoringError as exc:
            _mark_sync_error(db, user_id, account_id, exc.code)
        finally:
            try:
                db.query(EmailMonitoringSetting).filter(
                    EmailMonitoringSetting.user_id == user_id,
                    EmailMonitoringSetting.account_id == account_id,
                    EmailMonitoringSetting.poll_lock_token == lock_token,
                ).update(
                    {
                        EmailMonitoringSetting.poll_lock_token: None,
                        EmailMonitoringSetting.poll_lock_expires_at: None,
                    },
                    synchronize_session=False,
                )
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                logger.error("Gmail monitoring lease release failed.")


def poll_enabled_accounts(stop_event: threading.Event) -> None:
    if stop_event.is_set():
        return
    with SessionLocal() as db:
        accounts = (
            db.query(
                EmailMonitoringSetting.user_id,
                EmailMonitoringSetting.account_id,
            )
            .join(
                ConnectedGmailAccount,
                ConnectedGmailAccount.id == EmailMonitoringSetting.account_id,
            )
            .filter(
                EmailMonitoringSetting.enabled.is_(True),
                ConnectedGmailAccount.status == "connected",
            )
            .all()
        )
        account_pairs = [(row.user_id, row.account_id) for row in accounts]
    for user_id, account_id in account_pairs:
        if stop_event.is_set():
            break
        try:
            poll_account(user_id, account_id, stop_event)
        except Exception as exc:
            logger.error(
                "Gmail polling task failed (%s).",
                type(exc).__name__,
            )


async def run_monitoring_scheduler(stop_event: threading.Event) -> None:
    schema_warning_logged = False
    while not stop_event.is_set():
        try:
            if monitoring_schema_available():
                schema_warning_logged = False
                await asyncio.to_thread(poll_enabled_accounts, stop_event)
            elif not schema_warning_logged:
                logger.warning(
                    "Gmail monitoring is idle because its database migrations are pending."
                )
                schema_warning_logged = True
        except Exception as exc:
            logger.error(
                "Gmail monitoring scheduler cycle failed (%s).",
                type(exc).__name__,
            )
        if stop_event.is_set():
            break
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    stop_event.wait,
                    GMAIL_POLL_INTERVAL_SECONDS,
                ),
                timeout=GMAIL_POLL_INTERVAL_SECONDS + 1,
            )
        except asyncio.TimeoutError:
            pass
