from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import (
    ExpiredSignatureError,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.models.app_user import AppUser
from app.schemas.auth import (
    AccountUpdateIn,
    EmailCheckResponse,
    LoginIn,
    LoginResponse,
    SignupIn,
    UsernameCheckResponse,
    UserOut,
    UserSessionOut,
)

router = APIRouter()
SESSION_COOKIE = "dn_session"


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return request.cookies.get(SESSION_COOKIE)


def _get_current_user(request: Request, db: Session) -> AppUser:
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="missing_token")
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token_expired")
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid_token")

    raw_user_id = payload.get("user_id")
    if not raw_user_id:
        raise HTTPException(status_code=401, detail="invalid_token")
    try:
        user_id = uuid.UUID(str(raw_user_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid_token")

    user = db.get(AppUser, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="user_not_found")
    return user


def _secure_cookie() -> bool:
    return settings.app_env.lower() == "prod"


def _set_session_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=_secure_cookie(),
        max_age=settings.jwt_exp_minutes * 60,
        path="/",
    )


def _clear_session_cookie(response: JSONResponse) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value="",
        httponly=True,
        samesite="lax",
        secure=_secure_cookie(),
        max_age=0,
        path="/",
    )


@router.post("/signup", response_model=LoginResponse)
def signup(payload: SignupIn, db: Session = Depends(get_db)):
    password_errors = validate_password_strength(payload.password)
    if password_errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "Password does not meet requirements", "rules": password_errors},
        )

    username = payload.username.strip()
    email = payload.email.lower().strip()

    existing_username = db.execute(
        select(AppUser).where(func.lower(AppUser.username) == username.lower())
    ).scalars().first()
    if existing_username:
        raise HTTPException(status_code=409, detail="username_taken")

    existing_email = db.execute(select(AppUser).where(func.lower(AppUser.email) == email)).scalars().first()
    if existing_email:
        raise HTTPException(status_code=409, detail="email_taken")

    phone = payload.phone.strip() if payload.phone else None
    user = AppUser(
        username=username,
        email=email,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        phone=phone or None,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(sub=user.email, user_id=str(user.id), is_admin=user.is_admin)
    user_out = UserOut.model_validate(user)
    payload = LoginResponse(access_token=token, user=user_out)
    response = JSONResponse(jsonable_encoder(payload))
    _set_session_cookie(response, token)
    return response


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    email = payload.email.lower().strip()
    user = db.execute(select(AppUser).where(func.lower(AppUser.email) == email)).scalars().first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid_credentials")

    token = create_access_token(sub=user.email, user_id=str(user.id), is_admin=user.is_admin)
    user_out = UserOut.model_validate(user)
    payload = LoginResponse(access_token=token, user=user_out)
    response = JSONResponse(jsonable_encoder(payload))
    _set_session_cookie(response, token)
    return response


@router.get("/session")
def session(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return {"user": UserSessionOut.model_validate(user)}


@router.get("/account", response_model=UserOut)
def get_account(request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)
    return UserOut.model_validate(user)


@router.post("/logout")
def logout():
    response = JSONResponse({"status": "ok"})
    _clear_session_cookie(response)
    return response


@router.get("/check-username", response_model=UsernameCheckResponse)
def check_username(username: str = Query("", min_length=1), db: Session = Depends(get_db)):
    normalized = username.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="username_required")

    exists = db.execute(
        select(AppUser.id).where(func.lower(AppUser.username) == normalized.lower())
    ).scalars().first()
    return UsernameCheckResponse(username=normalized, available=not bool(exists))


@router.get("/check-email", response_model=EmailCheckResponse)
def check_email(email: str = Query(""), db: Session = Depends(get_db)):
    normalized = email.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="email_required")

    exists = db.execute(select(AppUser.id).where(func.lower(AppUser.email) == normalized)).scalars().first()
    return EmailCheckResponse(email=normalized, available=not bool(exists))


@router.put("/account", response_model=UserOut)
def update_account(payload: AccountUpdateIn, request: Request, db: Session = Depends(get_db)):
    user = _get_current_user(request, db)

    if payload.email:
        normalized_email = payload.email.strip().lower()
        exists = db.execute(
            select(AppUser.id).where(func.lower(AppUser.email) == normalized_email, AppUser.id != user.id)
        ).scalars().first()
        if exists:
            raise HTTPException(status_code=409, detail="email_taken")
        user.email = normalized_email

    if payload.first_name is not None:
        user.first_name = payload.first_name.strip()
    if payload.last_name is not None:
        user.last_name = payload.last_name.strip()
    if payload.phone is not None:
        user.phone = payload.phone.strip() or None

    if payload.password:
        password_errors = validate_password_strength(payload.password)
        if password_errors:
            raise HTTPException(
                status_code=400,
                detail={"message": "Password does not meet requirements", "rules": password_errors},
            )
        user.password_hash = hash_password(payload.password)

    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/deactivate")
def deactivate_account(request: Request, db: Session = Depends(get_db)):
    _get_current_user(request, db)
    raise HTTPException(status_code=403, detail="self_deactivate_not_allowed")
