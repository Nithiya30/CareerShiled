from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from api.auth_dependencies import AuthContext, get_auth_context, require_csrf
from app.db import get_db
from app.models import ConnectedGmailAccount, EmailMonitoringSetting
from app.schemas import (
    GmailAccountStatusResponse,
    GmailDisconnectResponse,
    GmailMonitoringConsentRequest,
    GmailMonitoringStatusResponse,
    GmailOAuthStartResponse,
)
from services.gmail_oauth_service import (
    GmailOAuthError,
    GmailReauthRequired,
    GmailOAuthStateError,
    create_authorization_request,
    consume_oauth_state,
    exchange_code_and_connect,
    revoke_and_delete_account,
)
from services.gmail_oauth_service import oauth_return_url
from services.gmail_monitoring_service import (
    GmailMonitoringError,
    establish_monitoring_baseline,
)


router = APIRouter(prefix="/gmail", tags=["Gmail account"])


def get_gmail_db(db: Session = Depends(get_db)) -> Session:
    required_tables = {
        "gmail_oauth_states",
        "connected_gmail_accounts",
        "email_monitoring_settings",
        "processed_gmail_messages",
        "suspicious_email_alerts",
    }
    inspector = inspect(db.get_bind())
    if not required_tables.issubset(set(inspector.get_table_names())):
        raise HTTPException(
            status_code=503,
            detail=(
                "Gmail schema is unavailable. Apply the approved database "
                "migrations before using Gmail connection."
            ),
        )
    monitoring_columns = {
        column["name"]
        for column in inspector.get_columns("email_monitoring_settings")
    }
    if not {"poll_lock_token", "poll_lock_expires_at"} <= monitoring_columns:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gmail monitoring schema is unavailable. Apply the approved database "
                "migrations before using Gmail monitoring."
            ),
        )
    return db


def _monitoring_status(
    db: Session,
    user_id: str,
) -> GmailMonitoringStatusResponse:
    setting = (
        db.query(EmailMonitoringSetting)
        .filter(EmailMonitoringSetting.user_id == user_id)
        .first()
    )
    if setting is None:
        return GmailMonitoringStatusResponse()
    return GmailMonitoringStatusResponse(
        enabled=setting.enabled,
        consented_at=setting.consented_at,
        last_successful_sync_at=setting.last_successful_sync_at,
        scanned_count=setting.scanned_count,
        recruitment_count=setting.recruitment_count,
        suspicious_count=setting.suspicious_count,
        last_error_code=setting.last_error_code,
    )


def _enable_monitoring(
    db: Session,
    user_id: str,
    request: GmailMonitoringConsentRequest,
) -> GmailMonitoringStatusResponse:
    if not request.consent:
        raise HTTPException(
            status_code=400,
            detail="Explicit monitoring consent is required.",
        )
    try:
        setting = establish_monitoring_baseline(db, user_id)
    except GmailReauthRequired:
        raise HTTPException(
            status_code=409,
            detail="Reconnect the Google account before enabling monitoring.",
        ) from None
    except GmailMonitoringError as exc:
        status_code = (
            409
            if exc.code in {"gmail_account_not_connected", "monitoring_state_changed"}
            else 503
        )
        raise HTTPException(
            status_code=status_code,
            detail=(
                "A connected Gmail account is required."
                if exc.code == "gmail_account_not_connected"
                else (
                    "The monitoring state changed. Please reload and try again."
                    if status_code == 409
                    else "Gmail monitoring could not be enabled. Please try again."
                )
            ),
        ) from None
    except GmailOAuthError:
        raise HTTPException(
            status_code=503,
            detail="Google authorization is temporarily unavailable.",
        ) from None
    return _monitoring_status(db, setting.user_id)


@router.post("/oauth/start", response_model=GmailOAuthStartResponse)
def start_gmail_oauth(
    context: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_csrf),
    db: Session = Depends(get_gmail_db),
) -> GmailOAuthStartResponse:
    try:
        authorization_url, expires_in = create_authorization_request(
            db, context.user.id
        )
    except GmailOAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    return GmailOAuthStartResponse(
        authorization_url=authorization_url,
        expires_in=expires_in,
    )


@router.get("/oauth/callback")
def gmail_oauth_callback(
    state: str | None = Query(default=None),
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_gmail_db),
):
    try:
        user_id = consume_oauth_state(db, state or "")
    except GmailOAuthStateError:
        raise HTTPException(
            status_code=400,
            detail="Gmail authorization state is invalid or expired.",
        ) from None

    outcome = "cancelled" if error else "failed"
    if not error and code:
        try:
            exchange_code_and_connect(db, user_id, code)
            outcome = "connected"
        except GmailOAuthError:
            outcome = "failed"
    elif not error:
        outcome = "failed"

    redirect_url = oauth_return_url(outcome)
    response = RedirectResponse(redirect_url, status_code=303)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/account", response_model=GmailAccountStatusResponse)
def get_gmail_account(
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_gmail_db),
) -> GmailAccountStatusResponse:
    account = (
        db.query(ConnectedGmailAccount)
        .filter(ConnectedGmailAccount.user_id == context.user.id)
        .first()
    )
    if account is None:
        return GmailAccountStatusResponse(connected=False, monitoring_enabled=False)
    monitoring_setting = account.monitoring_setting
    return GmailAccountStatusResponse(
        connected=True,
        gmail_address=account.gmail_address,
        status=account.status,
        connected_at=account.connected_at,
        monitoring_enabled=bool(monitoring_setting and monitoring_setting.enabled),
    )


@router.get(
    "/monitoring",
    response_model=GmailMonitoringStatusResponse,
)
def get_gmail_monitoring_status(
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_gmail_db),
) -> GmailMonitoringStatusResponse:
    return _monitoring_status(db, context.user.id)


@router.post(
    "/monitoring/enable",
    response_model=GmailMonitoringStatusResponse,
)
def enable_gmail_monitoring(
    request: GmailMonitoringConsentRequest,
    context: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_csrf),
    db: Session = Depends(get_gmail_db),
) -> GmailMonitoringStatusResponse:
    return _enable_monitoring(db, context.user.id, request)


@router.post(
    "/monitoring/pause",
    response_model=GmailMonitoringStatusResponse,
)
def pause_gmail_monitoring(
    context: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_csrf),
    db: Session = Depends(get_gmail_db),
) -> GmailMonitoringStatusResponse:
    setting = (
        db.query(EmailMonitoringSetting)
        .filter(EmailMonitoringSetting.user_id == context.user.id)
        .first()
    )
    if setting is not None:
        setting.enabled = False
        setting.poll_lock_token = None
        setting.poll_lock_expires_at = None
        setting.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    return _monitoring_status(db, context.user.id)


@router.post(
    "/monitoring/resume",
    response_model=GmailMonitoringStatusResponse,
)
def resume_gmail_monitoring(
    request: GmailMonitoringConsentRequest,
    context: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_csrf),
    db: Session = Depends(get_gmail_db),
) -> GmailMonitoringStatusResponse:
    return _enable_monitoring(db, context.user.id, request)


@router.delete("/account", response_model=GmailDisconnectResponse)
def disconnect_gmail_account(
    context: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_csrf),
    db: Session = Depends(get_gmail_db),
) -> GmailDisconnectResponse:
    account = (
        db.query(ConnectedGmailAccount)
        .filter(ConnectedGmailAccount.user_id == context.user.id)
        .first()
    )
    if account is None:
        return GmailDisconnectResponse(
            disconnected=True,
            remote_revocation="not_applicable",
        )
    revocation_status = revoke_and_delete_account(db, account)
    return GmailDisconnectResponse(
        disconnected=True,
        remote_revocation=revocation_status,
    )
