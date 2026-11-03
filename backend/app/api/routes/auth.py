from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import rate_limit
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    new_csrf_token,
    verify_password,
)
from app.models import Student, User
from app.schemas import LoginIn, MeUpdate, PasswordChange, UserOut
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_cookies(resp: Response, user: User) -> dict:
    access = create_access_token(user.id, user.role)
    refresh = create_refresh_token(user.id)
    csrf = new_csrf_token()
    common = {"secure": settings.COOKIE_SECURE, "samesite": "lax", "domain": settings.COOKIE_DOMAIN}
    resp.set_cookie("access_token", access, httponly=True, max_age=settings.ACCESS_TOKEN_MINUTES * 60, path="/", **common)
    resp.set_cookie("refresh_token", refresh, httponly=True, max_age=settings.REFRESH_TOKEN_DAYS * 86400,
                    path="/api/auth", **common)
    resp.set_cookie("csrf_token", csrf, httponly=False, max_age=settings.REFRESH_TOKEN_DAYS * 86400, path="/", **common)
    return {"access_token": access, "token_type": "bearer", "csrf_token": csrf}


def user_payload(db: Session, user: User) -> dict:
    data = UserOut.model_validate(user).model_dump()
    data["school_name"] = user.school.name if user.school else None
    if user.role == "student":
        s = db.scalar(select(Student).where(Student.user_id == user.id))
        data["student_id"] = s.id if s else None
    return data


@router.post("/login", dependencies=[Depends(rate_limit("login", settings.RATE_LIMIT_LOGIN_PER_MIN))])
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower().strip()))
    if not user or not verify_password(body.password, user.password_hash):
        audit(db, None, "auth.login_failed", "user", None, after={"email": body.email[:255]}, request=request, commit=True)
        raise HTTPException(401, "Email немесе құпиясөз қате")
    if not user.is_active:
        raise HTTPException(403, "Аккаунт бұғатталған")
    user.last_login_at = datetime.now(UTC)
    tokens = _set_cookies(response, user)
    audit(db, user, "auth.login", "user", user.id, request=request)
    db.commit()
    return {"user": user_payload(db, user), **tokens}


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    payload = decode_token(token, "refresh") if token else None
    if not payload:
        raise HTTPException(401, "Қайта кіру қажет")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "Қайта кіру қажет")
    return {"user": user_payload(db, user), **_set_cookies(response, user)}


@router.post("/logout")
def logout(response: Response):
    for name, path in (("access_token", "/"), ("refresh_token", "/api/auth"), ("csrf_token", "/")):
        response.delete_cookie(name, path=path, domain=settings.COOKIE_DOMAIN)
    return {"ok": True}


@router.get("/me")
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return user_payload(db, user)


@router.patch("/me")
def update_me(body: MeUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(user, k, v)
    db.commit()
    return user_payload(db, user)


@router.post("/change-password")
def change_password(body: PasswordChange, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "Ескі құпиясөз қате")
    user.password_hash = hash_password(body.new_password)
    audit(db, user, "auth.password_changed", "user", user.id, request=request)
    db.commit()
    return {"ok": True}
