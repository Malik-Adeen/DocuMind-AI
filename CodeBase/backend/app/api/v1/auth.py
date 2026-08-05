from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.core.security import create_access_token, verify_password
from app.db.models import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(
    payload: dict[str, Any],
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    email = payload.get("email")
    password = payload.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        raise ApiError("UNAUTHORIZED", "Invalid credentials.")

    user = db.scalars(select(User).where(User.email == email)).first()
    if user is None or not verify_password(password, user.password_hash):
        raise ApiError("UNAUTHORIZED", "Invalid credentials.")

    token = create_access_token(
        user_id=user.id,
        role=user.role,
        secret=settings.jwt_secret,
        expires_in=settings.jwt_expires_in,
    )
    return JSONResponse(
        status_code=200,
        content={
            "access_token": token,
            "expires_in": settings.jwt_expires_in,
            "user": {"id": str(user.id), "name": user.name, "role": user.role},
        },
    )
