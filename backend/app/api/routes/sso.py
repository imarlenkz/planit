"""Sign-in through iMARLEN ID (id.imarlen.kz), the shared login of the iMARLEN projects.

Settings (.env): IID_ISSUER=https://id.imarlen.kz, IID_CLIENT_ID=planit, IID_CLIENT_SECRET=...,
PUBLIC_URL=https://checker.imarlen.kz. The client is registered in iMARLEN ID with the redirect URI
{PUBLIC_URL}/api/auth/sso/callback. While any of them is empty the button is hidden and these routes are inert.

A user is found by idp_sub, else an existing Planit account with the same email is linked once, else the account
is created. A school is matched by schools.idp_code = the school's code in iMARLEN ID (or created from the claims
when IID_AUTO_CREATE_SCHOOL is on). Password sign-in keeps working next to SSO.
"""
import base64
import hashlib
import json
import logging
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes.auth import set_auth_cookies
from app.core.config import settings
from app.core.db import get_db
from app.core.security import hash_password
from app.models import School, SchoolClass, Student, Teacher, User
from app.services.audit import audit

router = APIRouter(prefix="/auth/sso", tags=["auth"])
log = logging.getLogger("planit.sso")
COOKIE = "planit_sso"

# iMARLEN ID role -> Planit role. Parents have no Planit account.
ROLE_MAP = {"student": "student", "teacher": "teacher", "school_admin": "school_admin", "platform_owner": "admin"}


class SsoError(Exception):
    pass


def _issuer() -> str:
    return settings.IID_ISSUER.rstrip("/")


def _public() -> str:
    return settings.PUBLIC_URL.rstrip("/")


def enabled() -> bool:
    return bool(settings.IID_ISSUER and settings.IID_CLIENT_ID and settings.IID_CLIENT_SECRET and settings.PUBLIC_URL)


def redirect_uri() -> str:
    return f"{_public()}{settings.API_PREFIX}/auth/sso/callback"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def norm_class(name: str | None) -> str:
    return re.sub(r"[\s\-–.]+", "", name or "").upper()


def norm_name(name: str | None) -> str:
    return " ".join((name or "").lower().replace("ё", "е").split())


def exchange_code(code: str, verifier: str) -> dict[str, Any]:
    """Code -> id_token claims. Kept as a module function so tests can replace it."""
    body = urllib.parse.urlencode({
        "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri(), "code_verifier": verifier,
    }).encode()
    basic = base64.b64encode(
        f"{urllib.parse.quote(settings.IID_CLIENT_ID)}:{urllib.parse.quote(settings.IID_CLIENT_SECRET)}".encode()
    ).decode()
    req = urllib.request.Request(
        f"{_issuer()}/token", data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Authorization": f"Basic {basic}"},
    )
    with urllib.request.urlopen(req, timeout=10) as res:  # noqa: S310 -- fixed https issuer from settings
        data = json.loads(res.read())
    # The id_token comes straight from the issuer's token endpoint over TLS (OIDC Core 3.1.3.7),
    # so its payload is trusted; iss / aud / nonce / exp are still checked by the caller.
    return json.loads(_unb64(data["id_token"].split(".")[1]))


def _school(db: Session, claim: dict) -> School | None:
    code = (claim.get("code") or "").strip()
    if not code:
        return None
    school = db.scalar(select(School).where(func.lower(School.idp_code) == code.lower()))
    if school is None and settings.IID_AUTO_CREATE_SCHOOL and claim.get("name"):
        school = School(name=claim["name"][:255], idp_code=code[:64])
        db.add(school)
        db.flush()
    return school


def _link_student(db: Session, user: User, school: School, class_name: str | None) -> None:
    if db.scalar(select(Student.id).where(Student.user_id == user.id)):
        return
    klass = None
    want = norm_class(class_name)
    if want:
        klass = next((c for c in db.scalars(select(SchoolClass).where(SchoolClass.school_id == school.id))
                      if norm_class(c.name) == want), None)
        m = re.match(r"^(\d{1,2})(.*)$", want)
        if klass is None and m and 0 < int(m.group(1)) <= 12:
            klass = SchoolClass(school_id=school.id, name=class_name.strip()[:20], grade=int(m.group(1)),
                                letter=(m.group(2) or None) and m.group(2)[:5])
            db.add(klass)
            db.flush()
    q = select(Student).where(Student.school_id == school.id, Student.user_id.is_(None))
    if klass is not None:
        q = q.where(Student.class_id == klass.id)
    me = norm_name(user.full_name)
    same = [s for s in db.scalars(q) if norm_name(s.full_name) == me]
    if len(same) == 1:
        same[0].user_id = user.id
    else:
        db.add(Student(school_id=school.id, class_id=klass.id if klass else None, user_id=user.id,
                       full_name=user.full_name, student_code=f"S{secrets.token_hex(4).upper()}"))


def provision(db: Session, c: dict[str, Any]) -> User:
    role = ROLE_MAP.get(c.get("role") or "")
    if role is None:
        raise SsoError("role")
    if not c.get("sub"):
        raise SsoError("error")

    user = db.scalar(select(User).where(User.idp_sub == c["sub"]))
    if user is None:
        school = _school(db, c.get("school") or {})
        if school is None and role != "admin":
            raise SsoError("school")
        email = (c.get("email") or f"{c.get('preferred_username') or c['sub']}@id.imarlen.kz").lower().strip()
        same = db.scalar(select(User).where(func.lower(User.email) == email))
        if same is not None:
            # Link an existing Planit account once, only inside the same school.
            if same.idp_sub is not None or (same.role != "admin" and school is not None and same.school_id != school.id):
                raise SsoError("conflict")
            user = same
            user.idp_sub = c["sub"]
        else:
            user = User(email=email, full_name=(c.get("name") or email)[:255], role=role,
                        school_id=school.id if school and role != "admin" else None,
                        password_hash=hash_password(secrets.token_urlsafe(24)),  # unusable: signs in through SSO
                        locale="kk", is_active=True, idp_sub=c["sub"])
            db.add(user)
            db.flush()
            if role == "teacher":
                db.add(Teacher(user_id=user.id, school_id=user.school_id))
        if user.role == "student" and school is not None:
            _link_student(db, user, school, c.get("class_name"))

    if not user.is_active:
        raise SsoError("disabled")
    # The name follows iMARLEN ID; the role stays as managed in Planit.
    if c.get("name"):
        user.full_name = c["name"][:255]
    user.last_login_at = datetime.now(UTC)
    return user


@router.get("/status")
def status() -> dict:
    return {"enabled": enabled(), "demo": settings.SEED_DEMO}


@router.get("/login")
def login() -> RedirectResponse:
    if not enabled():
        return RedirectResponse(f"{_public()}/login?sso=off", status_code=303)
    st = {"state": _b64(secrets.token_bytes(16)), "nonce": _b64(secrets.token_bytes(16)),
          "verifier": _b64(secrets.token_bytes(32))}
    q = urllib.parse.urlencode({
        "client_id": settings.IID_CLIENT_ID, "redirect_uri": redirect_uri(), "response_type": "code",
        "scope": "openid profile email", "state": st["state"], "nonce": st["nonce"],
        "code_challenge": _b64(hashlib.sha256(st["verifier"].encode()).digest()), "code_challenge_method": "S256",
    })
    res = RedirectResponse(f"{_issuer()}/authorize?{q}", status_code=303)
    res.set_cookie(COOKIE, _b64(json.dumps(st).encode()), max_age=600, httponly=True, samesite="lax",
                   secure=_public().startswith("https"), path=f"{settings.API_PREFIX}/auth/sso")
    return res


@router.get("/callback")
def callback(request: Request, db: Session = Depends(get_db)) -> RedirectResponse:
    def fail(why: str) -> RedirectResponse:
        r = RedirectResponse(f"{_public()}/login?sso={why}", status_code=303)
        r.delete_cookie(COOKIE, path=f"{settings.API_PREFIX}/auth/sso")
        return r

    if not enabled():
        return fail("off")
    try:
        st = json.loads(_unb64(request.cookies.get(COOKIE, "")))
    except Exception:  # noqa: BLE001
        return fail("state")
    q = request.query_params
    if not q.get("state") or not isinstance(st, dict) or q.get("state") != st.get("state"):
        return fail("state")
    if q.get("error") or not q.get("code"):
        return fail("denied")
    try:
        claims = exchange_code(q["code"], st["verifier"])
        aud = claims.get("aud")
        if (claims.get("iss") != _issuer()
                or (aud != settings.IID_CLIENT_ID and not (isinstance(aud, list) and settings.IID_CLIENT_ID in aud))
                or claims.get("nonce") != st.get("nonce")
                or claims.get("exp", 0) < datetime.now(UTC).timestamp()):
            raise ValueError("bad id_token")
        user = provision(db, claims)
        audit(db, user, "auth.sso_login", "user", user.id, after={"sub": claims.get("sub")}, request=request)
        db.commit()
    except SsoError as e:
        db.rollback()
        return fail(str(e))
    except (urllib.error.URLError, ValueError, KeyError, TypeError) as e:
        db.rollback()
        log.warning("iMARLEN ID sign-in failed: %r", e)
        return fail("error")

    r = RedirectResponse(f"{_public()}{'/me' if user.role == 'student' else '/dashboard'}", status_code=303)
    set_auth_cookies(r, user)
    r.delete_cookie(COOKIE, path=f"{settings.API_PREFIX}/auth/sso")
    return r


@router.get("/logout")
def logout() -> RedirectResponse:
    """Ends the iMARLEN ID session too, so a shared school computer is really signed out.
    Planit's own cookies are cleared first by POST /auth/logout."""
    if not enabled():
        return RedirectResponse(f"{_public()}/login", status_code=303)
    q = urllib.parse.urlencode({"client_id": settings.IID_CLIENT_ID, "post_logout_redirect_uri": f"{_public()}/login"})
    return RedirectResponse(f"{_issuer()}/logout?{q}", status_code=303)
