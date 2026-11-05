"""Pick students in Ustaz and import them into Planit."""
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import ClassTeacher, School, SchoolClass, Student, Teacher, User
from app.services.integrations import ustaz
from tests.conftest import login


@pytest.fixture
def roster(monkeypatch, db):
    t = db.scalar(select(User).where(User.email == "teacher@planit.kz"))
    school = db.get(School, t.school_id)
    old_code = school.idp_code
    school.idp_code = "s51-test"
    db.commit()
    monkeypatch.setattr(settings, "USTAZ_INTEGRATION_KEY", "k" * 32)
    data = {
        "school": {"name": "Test", "code": "s51-test"},
        "year": "2026-2027",
        "classes": [
            {"id": 901, "grade": 11, "letter": "Ж", "name": "11-Ж", "students": [
                {"id": 1, "code": "A1", "full_name": "Әлиев Нұрлан", "gender": "M"},
                {"id": 2, "code": "A2", "full_name": "Серікова Аружан", "gender": "F"},
                {"id": 3, "code": "A3", "full_name": "Бақыт Ерлан", "gender": "M"},
            ]},
        ],
    }
    seen = []

    def fake(code):
        seen.append(code)
        return data

    monkeypatch.setattr(ustaz, "fetch_roster", fake)
    yield data, seen
    school = db.get(School, t.school_id)
    school.idp_code = old_code
    db.commit()


def test_off_without_key(teacher):
    assert teacher.get("/api/integrations/ustaz/status").json() == {"configured": False}
    r = teacher.get("/api/integrations/ustaz/roster")
    assert r.status_code in (400, 503)


def test_student_cannot_use(student_client):
    assert student_client.get("/api/integrations/ustaz/roster").status_code == 403


def test_pick_and_import(roster, db):
    data, seen = roster
    c = login("teacher@planit.kz")
    r = c.get("/api/integrations/ustaz/roster")
    assert r.status_code == 200, r.text
    assert seen == ["s51-test"]
    cls = r.json()["classes"][0]
    assert cls["planit_class_id"] is None and not any(s["imported"] for s in cls["students"])

    r = c.post("/api/integrations/ustaz/import", json={"student_ids": [1, 2]})
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 2 and r.json()["classes_created"] == 1

    db.expire_all()
    pc = db.scalar(select(SchoolClass).where(SchoolClass.external_ref == "ustaz:901"))
    assert pc and pc.name == "11-Ж" and pc.grade == 11 and pc.academic_year == "2026-2027"
    names = sorted(s.full_name for s in db.scalars(select(Student).where(Student.class_id == pc.id)))
    assert names == ["Серікова Аружан", "Әлиев Нұрлан"]
    t = db.scalar(select(Teacher).join(User, User.id == Teacher.user_id).where(User.email == "teacher@planit.kz"))
    assert db.scalar(select(ClassTeacher).where(ClassTeacher.class_id == pc.id, ClassTeacher.teacher_id == t.id))

    # the teacher now sees the class; the roster marks who is in
    assert any(x["id"] == pc.id for x in c.get("/api/classes").json())
    cls = c.get("/api/integrations/ustaz/roster").json()["classes"][0]
    assert cls["planit_class_id"] == pc.id
    assert [s["imported"] for s in cls["students"]] == [True, True, False]

    # a hand-typed student with the same name is linked, not duplicated; a renamed one is updated
    db.add(Student(school_id=pc.school_id, class_id=pc.id, full_name="Бақыт  Ерлан", student_code="SHANDMADE1"))
    db.commit()
    data["classes"][0]["students"][0]["full_name"] = "Әлиев Нұрлан Серікұлы"
    r = c.post("/api/integrations/ustaz/import", json={"student_ids": [1, 2, 3]})
    out = r.json()
    assert (out["created"], out["linked"], out["updated"], out["unchanged"], out["classes_created"]) == (0, 1, 1, 1, 0)
    db.expire_all()
    assert db.scalar(select(Student).where(Student.student_code == "SHANDMADE1")).external_ref == "ustaz:3"
    assert db.scalar(select(Student).where(Student.external_ref == "ustaz:1")).full_name == "Әлиев Нұрлан Серікұлы"
    assert len(list(db.scalars(select(Student).where(Student.class_id == pc.id)))) == 3


def test_roster_errors_are_reported(monkeypatch, roster):
    def boom(code):
        raise ustaz.UstazError(502, "Ұстаз жауап бермеді")

    monkeypatch.setattr(ustaz, "fetch_roster", boom)
    c = login("teacher@planit.kz")
    r = c.get("/api/integrations/ustaz/roster")
    assert r.status_code == 502 and "Ұстаз" in r.json()["detail"]


def test_fetch_roster_sends_key(monkeypatch):
    import httpx
    monkeypatch.setattr(settings, "USTAZ_INTEGRATION_KEY", "secret-key")
    monkeypatch.setattr(settings, "USTAZ_API_URL", "https://ustaz.example.kz/api/")
    got = {}

    def fake_get(url, params, headers, timeout):
        got.update(url=url, params=params, key=headers["X-Integration-Key"])
        return httpx.Response(200, json={"classes": []}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    assert ustaz.fetch_roster("s51") == {"classes": []}
    assert got == {"url": "https://ustaz.example.kz/api/integration/planit/roster", "params": {"school_code": "s51"},
                   "key": "secret-key"}

    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(404, request=httpx.Request("GET", "x")))
    with pytest.raises(ustaz.UstazError) as e:
        ustaz.fetch_roster("s51")
    assert e.value.status == 404


def test_platform_admin_picks_school_by_code(roster, db):
    data, seen = roster
    c = login("admin@planit.kz")
    admin = db.scalar(select(User).where(User.email == "admin@planit.kz"))
    assert admin.role == "admin"
    # schools with a code are offered; with one such school it is the default, otherwise the admin picks
    codes = [s["idp_code"] for s in c.get("/api/integrations/ustaz/status").json()["schools"]]
    assert "s51-test" in codes
    r = c.get("/api/integrations/ustaz/roster")
    assert r.status_code == (200 if len(codes) == 1 else 400), r.text
    r = c.get("/api/integrations/ustaz/roster", params={"school_code": "S51-TEST"})
    assert r.status_code == 200, r.text
    assert r.json()["school_code"] == "s51-test" and r.json()["planit_school_id"] is not None

    # a school Planit does not have yet: listed from Ustaz, created on import
    r = c.get("/api/integrations/ustaz/roster", params={"school_code": "new-77"})
    assert r.status_code == 200 and r.json()["planit_school_id"] is None and seen[-1] == "new-77"
    data["school"]["name"] = "№77 мектеп"
    r = c.post("/api/integrations/ustaz/import", json={"student_ids": [1], "school_code": "new-77"})
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1 and r.json()["classes_created"] == 1
    db.expire_all()
    school = db.scalar(select(School).where(School.idp_code == "new-77"))
    assert school and school.name == "№77 мектеп"
    st = db.scalar(select(Student).where(Student.school_id == school.id))
    assert st.full_name == "Әлиев Нұрлан" and st.school_class.school_id == school.id


def test_teacher_cannot_pick_other_school(roster):
    data, seen = roster
    c = login("teacher@planit.kz")
    assert c.get("/api/integrations/ustaz/roster", params={"school_code": "other"}).status_code == 200
    assert seen[-1] == "s51-test"
