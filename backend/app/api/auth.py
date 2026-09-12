from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import db_session, get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.domain import User
from app.schemas.domain import (
    GoogleAuthRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    TokenResponse,
    UserRead,
    VerifyEmailRequest,
)
from app.services.email import send_verification_email

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_PASSWORD_PATTERN = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,}$")
_VERIFY_TTL = timedelta(hours=24)


def _validate_password(password: str) -> None:
    if not _PASSWORD_PATTERN.match(password):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters and include letters and numbers",
        )


def _token_for_user(user: User) -> TokenResponse:
    return TokenResponse(access_token=create_access_token(user.id, {"email": user.email}))


def _hash_verify_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_verification(user: User) -> str:
    raw_token = secrets.token_urlsafe(32)
    user.email_verified = False
    user.email_verify_token_hash = _hash_verify_token(raw_token)
    user.email_verify_expires_at = datetime.now(UTC) + _VERIFY_TTL
    return f"{settings.frontend_url.rstrip('/')}/auth/verify?token={raw_token}"


def _deliver_verification(email: str, verify_url: str) -> bool:
    return send_verification_email(email, verify_url)


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(db_session)) -> RegisterResponse:
    email = str(request.email).strip().lower()
    _validate_password(request.password)

    existing = db.query(User).filter(User.email == email).one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Sign in instead.",
        )

    user = User(email=email, password_hash=hash_password(request.password), auth_provider="password")
    verify_url = _issue_verification(user)
    db.add(user)
    db.flush()

    if not _deliver_verification(email, verify_url):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "We could not send a verification email. Use a real inbox you can open, "
                "and make sure mail is configured (SMTP or RESEND_API_KEY)."
            ),
        )

    db.commit()
    db.refresh(user)
    return RegisterResponse(
        id=user.id,
        email=user.email,
        email_verified=False,
        message="Check your inbox and click the confirmation link. If this address is not real, you will not get the email and cannot sign in.",
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(db_session)) -> TokenResponse:
    email = str(request.email).strip().lower()
    user = db.query(User).filter(User.email == email).one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found for this email. Sign up to get started.",
        )
    if user.auth_provider == "google":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This account uses Google sign-in. Use Continue with Google.",
        )
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password.")
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Confirm this sign-in from your email first. Click the verification link we sent.",
        )

    return _token_for_user(user)


@router.post("/verify", response_model=TokenResponse)
def verify_email(request: VerifyEmailRequest, db: Session = Depends(db_session)) -> TokenResponse:
    token_hash = _hash_verify_token(request.token.strip())
    user = db.query(User).filter(User.email_verify_token_hash == token_hash).one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This verification link is invalid.")
    expires = user.email_verify_expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if not expires or expires < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This verification link has expired. Request a new one.")

    user.email_verified = True
    user.email_verify_token_hash = None
    user.email_verify_expires_at = None
    db.commit()
    db.refresh(user)
    return _token_for_user(user)


@router.post("/resend-verification")
def resend_verification(request: ResendVerificationRequest, db: Session = Depends(db_session)) -> dict:
    email = str(request.email).strip().lower()
    user = db.query(User).filter(User.email == email).one_or_none()
    if not user or user.email_verified or user.auth_provider != "password":
        return {"message": "If that email can be verified, we sent a new link."}

    verify_url = _issue_verification(user)
    db.commit()
    _deliver_verification(email, verify_url)
    return {"message": "If that email can be verified, we sent a new link."}


@router.post("/google", response_model=TokenResponse)
def login_with_google(request: GoogleAuthRequest, db: Session = Depends(db_session)) -> TokenResponse:
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured. Set GOOGLE_CLIENT_ID.",
        )

    try:
        response = httpx.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": request.id_token},
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token") from exc

    if payload.get("aud") != settings.google_client_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google token audience mismatch")
    if payload.get("email_verified") not in (True, "true"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google email is not verified")

    email = str(payload.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google token did not include an email")

    user = db.query(User).filter(User.email == email).one_or_none()
    if not user:
        user = User(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            auth_provider="google",
            email_verified=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.email_verified:
        user.email_verified = True
        db.commit()

    return _token_for_user(user)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
