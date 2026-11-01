import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AuthSession, User


password_hasher = PasswordHash.recommended()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except UnknownHashError:
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User) -> tuple[str, str, AuthSession]:
    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        hours=settings.AUTH_SESSION_TTL_HOURS
    )
    auth_session = AuthSession(
        token_hash=hash_token(session_token),
        csrf_token_hash=hash_token(csrf_token),
        user_id=user.id,
        expires_at=expires_at,
    )
    db.add(auth_session)
    db.commit()
    return session_token, csrf_token, auth_session
