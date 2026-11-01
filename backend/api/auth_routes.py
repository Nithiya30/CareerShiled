import hashlib
import re
import secrets
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User
from app.schemas import (
    AuthLoginRequest,
    AuthRegisterRequest,
    AuthUserResponse,
    ExtensionPairingExchangeRequest,
    ExtensionPairingResponse,
    ExtensionTokenResponse,
)
from services.auth_service import (
    create_session,
    hash_password,
    normalize_email,
    verify_password,
)
from api.auth_dependencies import AuthContext, get_auth_context, require_csrf
from services.rate_limit_service import get_client_ip, rate_limiter


router = APIRouter(prefix="/auth", tags=["authentication"])
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
RATE_LIMIT_DETAIL = "Too many requests. Please try again later."
EXTENSION_PAIRING_TTL_SECONDS = 300


@dataclass(frozen=True)
class PendingExtensionPairing:
    user_id: str
    expires_at: datetime


_extension_pairings: dict[str, PendingExtensionPairing] = {}
_extension_pairings_lock = threading.Lock()


def _enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    retry_after = rate_limiter.consume(key, limit, window_seconds)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail=RATE_LIMIT_DETAIL,
            headers={"Retry-After": str(retry_after)},
        )


def _login_account_key(client_ip: str, normalized_email: str) -> str:
    account_digest = hashlib.sha256(normalized_email.encode("utf-8")).hexdigest()
    return f"login:account:{client_ip}:{account_digest}"


def _set_auth_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    max_age = settings.AUTH_SESSION_TTL_HOURS * 60 * 60
    cookie_options = {
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "max_age": max_age,
        "path": "/",
    }
    response.set_cookie(
        settings.AUTH_SESSION_COOKIE,
        session_token,
        httponly=True,
        **cookie_options,
    )
    response.set_cookie(
        settings.AUTH_CSRF_COOKIE,
        csrf_token,
        httponly=False,
        **cookie_options,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        settings.AUTH_SESSION_COOKIE,
        path="/",
        secure=settings.AUTH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        settings.AUTH_CSRF_COOKIE,
        path="/",
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )


def _user_response(user: User) -> AuthUserResponse:
    return AuthUserResponse(id=user.id, name=user.name, email=user.email)


@router.post("/extension/pairing", response_model=ExtensionPairingResponse)
def create_extension_pairing(
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_csrf),
) -> ExtensionPairingResponse:
    client_ip = get_client_ip(request, settings.TRUSTED_PROXY_IPS)
    _enforce_rate_limit(f"extension-pairing:{context.user.id}:{client_ip}", 3, 300)
    code = secrets.token_urlsafe(24)
    pairing_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)
    with _extension_pairings_lock:
        expired = [
            key
            for key, pairing in _extension_pairings.items()
            if pairing.expires_at <= now
        ]
        for key in expired:
            _extension_pairings.pop(key, None)
        _extension_pairings[pairing_hash] = PendingExtensionPairing(
            user_id=context.user.id,
            expires_at=now + timedelta(seconds=EXTENSION_PAIRING_TTL_SECONDS),
        )
    return ExtensionPairingResponse(
        code=code,
        expires_in=EXTENSION_PAIRING_TTL_SECONDS,
    )


@router.post("/extension/exchange", response_model=ExtensionTokenResponse)
def exchange_extension_pairing(
    request: Request,
    payload: ExtensionPairingExchangeRequest,
    db: Session = Depends(get_db),
) -> ExtensionTokenResponse:
    client_ip = get_client_ip(request, settings.TRUSTED_PROXY_IPS)
    _enforce_rate_limit(f"extension-exchange:{client_ip}", 10, 300)
    pairing_hash = hashlib.sha256(payload.code.encode("utf-8")).hexdigest()
    with _extension_pairings_lock:
        pairing = _extension_pairings.pop(pairing_hash, None)
    if pairing is None or pairing.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=400,
            detail="Pairing code is invalid, expired, or already used.",
        )

    user = db.query(User).filter(User.id == pairing.user_id).first()
    if user is None:
        raise HTTPException(status_code=400, detail="Pairing code is invalid or expired.")

    access_token, csrf_token, auth_session = create_session(db, user)
    expires_in = max(
        0,
        int(
            (
                auth_session.expires_at
                - datetime.now(timezone.utc).replace(tzinfo=None)
            ).total_seconds()
        ),
    )
    return ExtensionTokenResponse(
        access_token=access_token,
        csrf_token=csrf_token,
        expires_in=expires_in,
        user=_user_response(user),
    )


@router.post("/register", response_model=AuthUserResponse, status_code=201)
def register(
    request: AuthRegisterRequest,
    response: Response,
    http_request: Request,
    db: Session = Depends(get_db),
) -> AuthUserResponse:
    client_ip = get_client_ip(http_request, settings.TRUSTED_PROXY_IPS)
    _enforce_rate_limit(
        f"register:ip:{client_ip}",
        settings.AUTH_REGISTRATION_IP_LIMIT,
        settings.AUTH_REGISTRATION_WINDOW_SECONDS,
    )
    email = normalize_email(request.email)
    name = request.name.strip()
    if not EMAIL_PATTERN.fullmatch(email) or not name:
        raise HTTPException(status_code=422, detail="Enter a valid name and email address.")

    user = User(
        id=str(uuid.uuid4()),
        email=email,
        name=name,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        ) from None

    session_token, csrf_token, _ = create_session(db, user)
    _set_auth_cookies(response, session_token, csrf_token)
    return _user_response(user)


@router.post("/login", response_model=AuthUserResponse)
def login(
    request: AuthLoginRequest,
    response: Response,
    http_request: Request,
    db: Session = Depends(get_db),
) -> AuthUserResponse:
    email = normalize_email(request.email)
    client_ip = get_client_ip(http_request, settings.TRUSTED_PROXY_IPS)
    _enforce_rate_limit(
        f"login:ip:{client_ip}",
        settings.AUTH_LOGIN_IP_LIMIT,
        settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )
    account_key = _login_account_key(client_ip, email)
    retry_after = rate_limiter.remaining_delay(
        account_key,
        settings.AUTH_LOGIN_ACCOUNT_IP_LIMIT,
        settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail=RATE_LIMIT_DETAIL,
            headers={"Retry-After": str(retry_after)},
        )

    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(request.password, user.password_hash):
        _enforce_rate_limit(
            account_key,
            settings.AUTH_LOGIN_ACCOUNT_IP_LIMIT,
            settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
        )
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    rate_limiter.reset(account_key)
    session_token, csrf_token, _ = create_session(db, user)
    _set_auth_cookies(response, session_token, csrf_token)
    return _user_response(user)


@router.get("/me", response_model=AuthUserResponse)
def current_user(context: AuthContext = Depends(get_auth_context)) -> AuthUserResponse:
    return _user_response(context.user)


@router.post("/logout")
def logout(
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_csrf),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    db.delete(context.auth_session)
    db.commit()
    _clear_auth_cookies(response)
    return {"message": "Signed out."}
