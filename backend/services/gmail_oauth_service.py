import hashlib
import binascii
import json
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ConnectedGmailAccount, EmailMonitoringSetting, GmailOAuthState


logger = logging.getLogger(__name__)
GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOCATION_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
OAUTH_SCOPES = ("openid", "email", GMAIL_READONLY_SCOPE)
OAUTH_STATE_TTL_SECONDS = 600
OAUTH_HTTP_TIMEOUT_SECONDS = 10.0
GMAIL_WRITE_SCOPE_PREFIX = "https://www.googleapis.com/auth/gmail."


class GmailOAuthError(Exception):
    """Base error with a safe message suitable for an API response."""


class GmailOAuthConfigurationError(GmailOAuthError):
    pass


class GmailOAuthUnavailable(GmailOAuthError):
    pass


class GmailOAuthStateError(GmailOAuthError):
    pass


class GmailAccountConflict(GmailOAuthError):
    pass


class GmailReauthRequired(GmailOAuthError):
    pass


class GmailTokenEncryptionError(GmailOAuthError):
    pass


def _is_loopback(hostname: str | None) -> bool:
    return hostname in {"localhost", "127.0.0.1", "::1"}


def _validate_https_uri(value: str, *, allow_query: bool = False) -> None:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or (parsed.query and not allow_query)
        or (parsed.scheme != "https" and not _is_loopback(parsed.hostname))
    ):
        raise GmailOAuthConfigurationError("Gmail OAuth is not configured correctly.")


def _oauth_config() -> tuple[str, str, str, str]:
    client_id = settings.GMAIL_OAUTH_CLIENT_ID
    client_secret = settings.GMAIL_OAUTH_CLIENT_SECRET
    redirect_uri = settings.GMAIL_OAUTH_REDIRECT_URI
    return_url = settings.GMAIL_OAUTH_RETURN_URL
    if not all((client_id, client_secret, redirect_uri, return_url)):
        raise GmailOAuthConfigurationError("Gmail OAuth is not configured.")
    _validate_https_uri(redirect_uri)
    _validate_https_uri(return_url, allow_query=True)
    return_origin = f"{urlsplit(return_url).scheme}://{urlsplit(return_url).netloc}"
    if return_origin not in settings.CORS_ORIGINS:
        raise GmailOAuthConfigurationError("Gmail OAuth is not configured correctly.")
    return client_id, client_secret, redirect_uri, return_url


def oauth_return_url(outcome: str) -> str:
    if outcome not in {"connected", "cancelled", "failed"}:
        raise ValueError("Unsupported Gmail OAuth result.")
    _, _, _, return_url = _oauth_config()
    parsed = urlsplit(return_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != "gmail_connection"
    ]
    query.append(("gmail_connection", outcome))
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), "")
    )


def _keyring() -> tuple[str, Fernet, dict[str, Fernet]]:
    raw_keys = settings.GMAIL_TOKEN_ENCRYPTION_KEYS
    active_version = settings.GMAIL_TOKEN_ACTIVE_KEY_VERSION
    if not raw_keys or not active_version:
        raise GmailOAuthConfigurationError(
            "Gmail token encryption is not configured."
        )
    try:
        configured_keys = json.loads(raw_keys)
        if not isinstance(configured_keys, dict) or not configured_keys:
            raise ValueError
        if any(
            not isinstance(version, str)
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", version)
            or not isinstance(key, str)
            for version, key in configured_keys.items()
        ):
            raise ValueError
        ciphers = {
            version: Fernet(key.encode("ascii"))
            for version, key in configured_keys.items()
        }
        active_cipher = ciphers[active_version]
    except (ValueError, KeyError, TypeError, UnicodeEncodeError, binascii.Error):
        raise GmailOAuthConfigurationError(
            "Gmail token encryption is not configured correctly."
        ) from None
    return active_version, active_cipher, ciphers


def encrypt_refresh_token(token: str) -> tuple[str, str]:
    if not token:
        raise GmailTokenEncryptionError("Google did not provide a refresh token.")
    version, cipher, _ = _keyring()
    ciphertext = cipher.encrypt(token.encode("utf-8")).decode("ascii")
    return ciphertext, version


def decrypt_refresh_token(account: ConnectedGmailAccount) -> str:
    _, _, ciphers = _keyring()
    cipher = ciphers.get(account.token_key_version)
    if cipher is None:
        raise GmailTokenEncryptionError(
            "The Gmail encryption key version is unavailable."
        )
    try:
        return cipher.decrypt(account.refresh_token_ciphertext.encode("ascii")).decode(
            "utf-8"
        )
    except (InvalidToken, UnicodeDecodeError, UnicodeEncodeError):
        raise GmailTokenEncryptionError(
            "The stored Gmail credential could not be decrypted."
        ) from None


def _post_google_form(url: str, data: dict[str, str]) -> tuple[int, dict[str, Any]]:
    try:
        with httpx.Client(timeout=OAUTH_HTTP_TIMEOUT_SECONDS) as client:
            response = client.post(url, data=data)
    except httpx.RequestError:
        raise GmailOAuthUnavailable(
            "Google authorization is temporarily unavailable."
        ) from None
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return response.status_code, payload


def verify_google_identity(token: str, client_id: str) -> dict[str, Any]:
    try:
        from google.auth.transport.requests import Request as GoogleAuthRequest
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(
            token,
            GoogleAuthRequest(),
            audience=client_id,
        )
    except Exception:
        raise GmailOAuthError("Google account identity could not be verified.") from None
    if (
        not isinstance(claims, dict)
        or not isinstance(claims.get("sub"), str)
        or not claims["sub"]
        or not isinstance(claims.get("email"), str)
        or not claims["email"]
        or claims.get("email_verified") is not True
    ):
        raise GmailOAuthError("Google account identity could not be verified.")
    return claims


def _granted_scopes(payload: dict[str, Any]) -> set[str]:
    raw_scopes = payload.get("scope")
    if isinstance(raw_scopes, str):
        return set(raw_scopes.split())
    if isinstance(raw_scopes, list) and all(
        isinstance(scope, str) for scope in raw_scopes
    ):
        return set(raw_scopes)
    return set()


def _validate_granted_scopes(scopes: set[str]) -> None:
    if GMAIL_READONLY_SCOPE not in scopes:
        raise GmailOAuthError("Required Gmail read-only access was not granted.")
    if "https://mail.google.com/" in scopes or any(
        scope.startswith(GMAIL_WRITE_SCOPE_PREFIX)
        and scope != GMAIL_READONLY_SCOPE
        for scope in scopes
    ):
        raise GmailOAuthError("Google granted an unsupported Gmail permission.")


def create_authorization_request(db: Session, user_id: str) -> tuple[str, int]:
    client_id, _, redirect_uri, _ = _oauth_config()
    _keyring()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.query(GmailOAuthState).filter(GmailOAuthState.expires_at <= now).delete(
        synchronize_session=False
    )
    state = secrets.token_urlsafe(32)
    db.add(
        GmailOAuthState(
            state_hash=hashlib.sha256(state.encode("utf-8")).hexdigest(),
            user_id=user_id,
            created_at=now,
            expires_at=now + timedelta(seconds=OAUTH_STATE_TTL_SECONDS),
        )
    )
    db.commit()
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(OAUTH_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    return f"{GOOGLE_AUTHORIZATION_URL}?{query}", OAUTH_STATE_TTL_SECONDS


def consume_oauth_state(db: Session, state: str) -> str:
    if not state or len(state) > 256:
        raise GmailOAuthStateError("Gmail authorization state is invalid or expired.")
    state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    record = (
        db.query(GmailOAuthState)
        .filter(GmailOAuthState.state_hash == state_hash)
        .first()
    )
    if record is None:
        raise GmailOAuthStateError("Gmail authorization state is invalid or expired.")
    user_id = record.user_id
    updated = (
        db.query(GmailOAuthState)
        .filter(
            GmailOAuthState.state_hash == state_hash,
            GmailOAuthState.consumed_at.is_(None),
            GmailOAuthState.expires_at > now,
        )
        .update(
            {GmailOAuthState.consumed_at: now},
            synchronize_session=False,
        )
    )
    if updated != 1:
        db.rollback()
        raise GmailOAuthStateError("Gmail authorization state is invalid or expired.")
    db.commit()
    return user_id


def exchange_code_and_connect(
    db: Session,
    user_id: str,
    authorization_code: str,
) -> ConnectedGmailAccount:
    client_id, client_secret, redirect_uri, _ = _oauth_config()
    status, payload = _post_google_form(
        GOOGLE_TOKEN_URL,
        {
            "code": authorization_code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if status != 200:
        raise GmailOAuthError("Google authorization could not be completed.")
    granted_scopes = _granted_scopes(payload)
    _validate_granted_scopes(granted_scopes)
    identity_token = payload.get("id_token")
    if not isinstance(identity_token, str) or not identity_token:
        raise GmailOAuthError("Google account identity could not be verified.")
    identity = verify_google_identity(identity_token, client_id)
    if identity.get("email_verified") is not True:
        raise GmailOAuthError("Google account identity could not be verified.")
    google_subject = identity["sub"]
    gmail_address = identity["email"].strip()
    if not gmail_address:
        raise GmailOAuthError("Google account identity could not be verified.")

    account_for_identity = (
        db.query(ConnectedGmailAccount)
        .filter(ConnectedGmailAccount.google_subject == google_subject)
        .first()
    )
    if account_for_identity is not None and account_for_identity.user_id != user_id:
        raise GmailAccountConflict(
            "This Google account is already connected to another CareerShield account."
        )

    existing = (
        db.query(ConnectedGmailAccount)
        .filter(ConnectedGmailAccount.user_id == user_id)
        .first()
    )
    if existing is not None and existing.google_subject != google_subject:
        raise GmailAccountConflict(
            "Disconnect the currently connected Google account before connecting another."
        )

    refresh_token = payload.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        if existing is None:
            raise GmailOAuthError(
                "Google did not provide a refresh token. Revoke CareerShield access in "
                "Google Account settings and try connecting again."
            )
        refresh_token = decrypt_refresh_token(existing)
    ciphertext, key_version = encrypt_refresh_token(refresh_token)

    account = existing or ConnectedGmailAccount(
        id=str(uuid.uuid4()),
        user_id=user_id,
        google_subject=google_subject,
        gmail_address=gmail_address,
    )
    account.google_subject = google_subject
    account.gmail_address = gmail_address
    account.refresh_token_ciphertext = ciphertext
    account.token_key_version = key_version
    account.granted_scopes = sorted(granted_scopes)
    account.status = "connected"
    account.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if existing is None:
        account.connected_at = account.updated_at
        db.add(account)
    try:
        db.commit()
        db.refresh(account)
    except IntegrityError:
        db.rollback()
        raise GmailAccountConflict(
            "This Google account could not be connected to the CareerShield account."
        ) from None
    return account


def refresh_access_token(
    db: Session,
    account: ConnectedGmailAccount,
) -> str:
    if account.status != "connected":
        raise GmailReauthRequired("Reconnect the Google account to continue.")
    client_id, client_secret, _, _ = _oauth_config()
    refresh_token = decrypt_refresh_token(account)
    status, payload = _post_google_form(
        GOOGLE_TOKEN_URL,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    if payload.get("error") == "invalid_grant":
        account.status = "reauth_required"
        account.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        raise GmailReauthRequired("Reconnect the Google account to continue.")
    access_token = payload.get("access_token")
    if status != 200 or not isinstance(access_token, str) or not access_token:
        raise GmailOAuthUnavailable("Google authorization is temporarily unavailable.")
    rotated_refresh_token = payload.get("refresh_token")
    if isinstance(rotated_refresh_token, str) and rotated_refresh_token:
        ciphertext, key_version = encrypt_refresh_token(rotated_refresh_token)
        account.refresh_token_ciphertext = ciphertext
        account.token_key_version = key_version
        account.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    return access_token


def revoke_and_delete_account(
    db: Session,
    account: ConnectedGmailAccount,
) -> str:
    setting = (
        db.query(EmailMonitoringSetting)
        .filter(EmailMonitoringSetting.account_id == account.id)
        .first()
    )
    account.status = "revoked"
    account.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if setting is not None:
        setting.enabled = False
        setting.poll_lock_token = None
        setting.poll_lock_expires_at = None
    db.commit()

    revocation_confirmed = False
    try:
        refresh_token = decrypt_refresh_token(account)
        status, _ = _post_google_form(
            GOOGLE_REVOCATION_URL,
            {"token": refresh_token},
        )
        revocation_confirmed = status == 200
    except (GmailOAuthError, GmailTokenEncryptionError):
        pass

    db.delete(account)
    db.commit()
    if not revocation_confirmed:
        logger.warning("Gmail credential revocation could not be confirmed.")
        return "unconfirmed"
    return "confirmed"
