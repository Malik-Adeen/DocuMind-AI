from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator

import jwt
from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.security import decode_access_token, outranks
from app.db.models import User
from app.db.session import get_sessionmaker


def get_db() -> Iterator[Session]:
    with get_sessionmaker()() as session:
        yield session


def current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise ApiError("UNAUTHORIZED", "Missing or invalid bearer token.")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        claims = decode_access_token(token, secret=settings.jwt_secret)
    except jwt.PyJWTError:
        raise ApiError("UNAUTHORIZED", "Missing or invalid bearer token.") from None

    try:
        user_id = uuid.UUID(str(claims.get("sub")))
    except ValueError:
        raise ApiError("UNAUTHORIZED", "Missing or invalid bearer token.") from None

    user = db.get(User, user_id)
    if user is None:
        raise ApiError("UNAUTHORIZED", "Missing or invalid bearer token.")
    return user


def require_role(minimum: str) -> Callable[[User], User]:
    def guard(user: User = Depends(current_user)) -> User:
        if not outranks(user.role, minimum):
            raise ApiError("FORBIDDEN", f"Role {user.role} cannot perform this action.")
        return user

    return guard


require_reviewer = Depends(require_role("reviewer"))
