"""iMARLEN ID single sign-on: redirect, state checks, provisioning and account linking."""
import time
import urllib.parse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes import sso
from app.core.config import settings
from app.main import app
from app.models import School, SchoolClass, Student, Teacher, User

ISS = "https://id.example.kz"


@pytest.fixture
def iid(monkeypatch):
    for k, v in {"IID_ISSUER": ISS, "IID_CLIENT_ID": "planit", "IID_CLIENT_SECRET": "s3cret",
                 "PUBLIC_URL": "https://checker.example.kz"}.items():
        monkeypatch.setattr(settings, k, v)
    claims: dict = {}

    def fake_exchange(code, verifier):
        assert code == "the-code" and verifier
        return claims

    monkeypatch.setattr(sso, "exchange_code", fake_exchange)
    return claims


def start(c: TestClient) -> dict:
    r = c.get("/api/auth/sso/login", follow_redirects=False)
    assert r.status_code == 303
    url = urllib.parse.urlparse(r.headers["location"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{ISS}/authorize"
    q = dict(urllib.parse.parse_qsl(url.query))
    assert q["client_id"] == "planit" and q["code_challenge_method"] == "S256"
    assert q["redirect_uri"] == "https://checker.example.kz/api/auth/sso/callback"
    return q


def finish(c: TestClient, iid: dict, q: dict, claims: dict | None = None, **extra):
    if claims is not None:
        iid.clear()
        iid.update(claims)
    claims = iid
    claims.setdefault("iss", ISS)
    claims.setdefault("aud", "planit")
    claims.setdefault("exp", time.time() + 300)
    claims.setdefault("nonce", q["nonce"])
    claims.update(extra)
    return c.get("/api/auth/sso/callback", params={"code": "the-code", "state": q["state"]}, follow_redirects=False)


def test_disabled_by_default():
    c = TestClient(app)
    assert c.get("/api/auth/sso/status").json()["enabled"] is False
    r = c.get("/api/auth/sso/callback", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("/login?sso=off")


def test_state_mismatch_is_rejected(iid):
    c = TestClient(app, base_url="https://testserver")
    assert c.get("/api/auth/sso/status").json()["enabled"] is True
    start(c)
    r = c.get("/api/auth/sso/callback", params={"code": "the-code", "state": "forged"}, follow_redirects=False)
    assert r.headers["location"].endswith("/login?sso=state")


def test_bad_nonce_is_rejected(iid):
    c = TestClient(app, base_url="https://testserver")
    q = start(c)
    iid.update({"sub": "u-x", "role": "teacher", "name": "X", "school": {"code": "Z", "name": "Z"}})
    r = finish(c, iid, q, nonce="other")
    assert r.headers["location"].endswith("/login?sso=error")


def test_parent_is_rejected(iid):
    c = TestClient(app, base_url="https://testserver")
    q = start(c)
    iid.update({"sub": "p-1", "role": "parent", "name": "Ата-ана"})
    assert finish(c, iid, q).headers["location"].endswith("/login?sso=role")


def test_new_teacher_is_created_and_signed_in(iid, db):
    c = TestClient(app, base_url="https://testserver")
    q = start(c)
    iid.update({"sub": "t-100", "role": "teacher", "name": "Жаңа Мұғалім", "preferred_username": "new.teacher",
                "school": {"id": "s1", "code": "SCH-NEW", "name": "Жаңа мектеп"}})
    r = finish(c, iid, q)
    assert r.status_code == 303 and r.headers["location"] == "https://checker.example.kz/dashboard"
    assert "access_token" in r.cookies and "csrf_token" in r.cookies
    me = c.get("/api/auth/me").json()
    assert me["email"] == "new.teacher@id.imarlen.kz" and me["role"] == "teacher" and me["sso"] is True
    u = db.scalar(select(User).where(User.idp_sub == "t-100"))
    assert u.school.idp_code == "SCH-NEW" and db.scalar(select(Teacher).where(Teacher.user_id == u.id))

    # second sign-in finds the same account by sub and follows the name
    c2 = TestClient(app, base_url="https://testserver")
    q2 = start(c2)
    claims = {"sub": "t-100", "role": "teacher", "name": "Жаңа Мұғалім Атыжөні", "school": {"code": "SCH-NEW"}}
    finish(c2, iid, q2, claims)
    assert c2.get("/api/auth/me").json()["full_name"] == "Жаңа Мұғалім Атыжөні"


def test_existing_account_is_linked_by_email(iid, db):
    school = db.scalar(select(School).order_by(School.id))
    school.idp_code = "DEMO7"
    db.commit()
    c = TestClient(app, base_url="https://testserver")
    q = start(c)
    iid.update({"sub": "t-demo", "role": "teacher", "name": "Demo Teacher", "email": "Teacher2@planit.kz",
                "school": {"code": "demo7", "name": "№7"}})
    finish(c, iid, q)
    me = c.get("/api/auth/me").json()
    assert me["email"] == "teacher2@planit.kz" and me["sso"] is True

    # the same email from another iMARLEN ID subject is a conflict, not a takeover
    c2 = TestClient(app, base_url="https://testserver")
    q2 = start(c2)
    claims = {"sub": "t-other", "role": "teacher", "name": "X", "email": "teacher2@planit.kz",
              "school": {"code": "demo7"}}
    assert finish(c2, iid, q2, claims).headers["location"].endswith("/login?sso=conflict")


def test_student_is_linked_to_roster(iid, db):
    school = db.scalar(select(School).where(School.idp_code == "DEMO7")) or db.scalar(select(School).order_by(School.id))
    school.idp_code = "DEMO7"
    klass = db.scalar(select(SchoolClass).where(SchoolClass.school_id == school.id, SchoolClass.name == "6А"))
    st = db.scalar(select(Student).where(Student.class_id == klass.id, Student.user_id.is_(None)))
    db.commit()
    c = TestClient(app, base_url="https://testserver")
    q = start(c)
    iid.update({"sub": "s-1", "role": "student", "name": st.full_name.upper(), "preferred_username": "stud1",
                "class_name": "6 А", "school": {"code": "DEMO7"}})
    r = finish(c, iid, q)
    assert r.headers["location"].endswith("/me")
    me = c.get("/api/auth/me").json()
    assert me["student_id"] == st.id
