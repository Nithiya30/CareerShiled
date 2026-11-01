import hmac
from datetime import datetime, timezone
from typing import NamedTuple

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import AuthSession, User
from services.auth_service import hash_token


class AuthContext(NamedTuple):
    user: User
    auth_session: AuthSession


def _bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization", "")
    if not authorization:
        return None
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise HTTPException(status_code=401, detail="Authentication required.")
    return token.strip()


def get_auth_context(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthContext:
    raw_token = _bearer_token(request) or request.cookies.get(settings.AUTH_SESSION_COOKIE)
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    auth_session = (
        db.query(AuthSession)
        .filter(AuthSession.token_hash == hash_token(raw_token))
        .first()
    )
    if auth_session is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    if auth_session.expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=401, detail="Authentication required.")

    user = db.query(User).filter(User.id == auth_session.user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return AuthContext(user=user, auth_session=auth_session)


def get_current_user(context: AuthContext = Depends(get_auth_context)) -> User:
    return context.user


def require_csrf(
    request: Request,
    csrf_header: str | None = Header(None, alias="X-CSRF-Token"),
    context: AuthContext = Depends(get_auth_context),
) -> None:
    is_bearer_auth = _bearer_token(request) is not None
    csrf_cookie = request.cookies.get(settings.AUTH_CSRF_COOKIE)
    if (
        (not is_bearer_auth and not csrf_cookie)
        or not csrf_header
        or (
            not is_bearer_auth
            and not hmac.compare_digest(csrf_cookie or "", csrf_header)
        )
        or not hmac.compare_digest(
            hash_token(csrf_header), context.auth_session.csrf_token_hash
        )
    ):
        raise HTTPException(status_code=403, detail="CSRF validation failed.")
