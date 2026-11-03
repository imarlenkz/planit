import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="planit-test-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
    "QUEUE_MODE": "eager",
    "STORAGE_LOCAL_PATH": f"{_tmp}/storage",
    "ENVIRONMENT": "test",
    "AI_PROVIDER": "local",
    "RATE_LIMIT_LOGIN_PER_MIN": "1000",
    "PIPELINE_WORKERS": "2",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_demo  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.create_all(engine)
    db = SessionLocal()
    info = seed_demo(db)
    db.close()
    yield info
    Base.metadata.drop_all(engine)


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


def login(email: str, password: str = "demo12345") -> TestClient:
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    return c


@pytest.fixture
def teacher():
    return login("teacher@planit.kz")


@pytest.fixture
def teacher2():
    return login("teacher2@planit.kz")


@pytest.fixture
def student_client():
    return login("student@planit.kz")


@pytest.fixture
def admin():
    return login("admin@planit.kz")
