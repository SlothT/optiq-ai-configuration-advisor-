from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import db_session
from app.core.security import create_access_token, hash_password, verify_password
from app.models.domain import User
from app.schemas.domain import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")


def _validate_password(password: str) -> None:
    if not _PASSWORD_PATTERN.match(password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters and include letters and numbers",
        )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(db_session)) -> User:
    email = request.email.strip().lower()
    _validate_password(request.password)

    existing = db.query(User).filter(User.email == email).one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=email, password_hash=hash_password(request.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(db_session)) -> TokenResponse:
    user = db.query(User).filter(User.email == request.email.strip().lower()).one_or_none()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(user.id, {"email": user.email})
    return TokenResponse(access_token=token)
