"""API tests: auth, CSRF, RBAC / tenant isolation, answer key, templates, privacy."""
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    assert TestClient(app).get("/api/health").json()["status"] == "ok"


def test_login_failure_and_me(teacher):
    c = TestClient(app)
    assert c.post("/api/auth/login", json={"email": "teacher@planit.kz", "password": "wrong"}).status_code == 401
    me = teacher.get("/api/auth/me").json()
    assert me["role"] == "teacher" and me["email"] == "teacher@planit.kz"


def test_requires_auth():
    assert TestClient(app).get("/api/assessments").status_code == 401


def test_csrf_required_for_cookie_mutations(teacher):
    token = teacher.headers.pop("X-CSRF-Token")
    r = teacher.post("/api/subjects", json={"name": "Тарих"})
    assert r.status_code == 403
    teacher.headers["X-CSRF-Token"] = token
    assert teacher.post("/api/subjects", json={"name": "Тарих"}).status_code == 201


def test_bearer_token_works_without_csrf():
    c = TestClient(app)
    tok = c.post("/api/auth/login", json={"email": "teacher@planit.kz", "password": "demo12345"}).json()["access_token"]
    c.cookies.clear()
    r = c.post("/api/subjects", json={"name": "География"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 201


def test_teacher_isolation(teacher, teacher2, database):
    aid = database["main_assessment_id"]
    assert teacher.get(f"/api/assessments/{aid}").status_code == 200
    # teacher2 does not teach 5А → cannot see the assessment, its results or students
    assert teacher2.get(f"/api/assessments/{aid}").status_code == 404
    assert teacher2.get(f"/api/analytics/assessments/{aid}").status_code == 404
    ids = {a["id"] for a in teacher2.get("/api/assessments?size=100").json()["items"]}
    assert aid not in ids
    s5a = teacher.get("/api/students?size=1").json()["items"][0]
    assert teacher2.get(f"/api/students/{s5a['id']}").status_code in (200, 404)


def test_student_role_restrictions(student_client, database):
    assert student_client.get("/api/students").status_code == 403
    assert student_client.post("/api/assessments", json={}).status_code in (403, 422)
    r = student_client.get("/api/me/results")
    assert r.status_code == 200 and "results" in r.json()
    a = student_client.get(f"/api/assessments/{database['main_assessment_id']}").json()
    assert all(q["correct_answer"] is None for q in a["questions"])  # answer key hidden from students


def test_create_assessment_with_answer_key_and_template(teacher):
    classes = teacher.get("/api/classes").json()
    subjects = teacher.get("/api/subjects").json()
    a = teacher.post("/api/assessments", json={"type": "TZhB", "title": "Тест ТЖБ", "subject_id": subjects[0]["id"],
                                               "class_id": classes[0]["id"], "quarter": 2}).json()
    key = [
        {"number": 1, "text": "2+2", "answer_type": "numeric", "correct_answer": {"value": 4}, "max_score": 1},
        {"number": 2, "text": "Таңда", "answer_type": "single_choice", "correct_answer": "C", "max_score": 1,
         "options": {"A": "1", "B": "2", "C": "3", "D": "4"}},
        {"number": 3, "text": "Түсіндір", "answer_type": "open", "correct_answer": "...", "max_score": 3,
         "descriptors": [{"number": 1, "text": "a", "points": 1}, {"number": 2, "text": "b", "points": 2}]},
    ]
    r = teacher.put(f"/api/assessments/{a['id']}/questions", json=key)
    assert r.status_code == 200 and r.json()["max_score"] == 5
    bad = [{**key[2], "descriptors": [{"number": 1, "text": "a", "points": 5}]}]
    assert teacher.put(f"/api/assessments/{a['id']}/questions", json=bad).status_code == 422
    pdf = teacher.get(f"/api/assessments/{a['id']}/template.pdf?mode=blank")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_upload_rejects_non_images(teacher, database):
    aid = database["main_assessment_id"]
    r = teacher.post(f"/api/assessments/{aid}/uploads", files=[("files", ("x.exe", b"MZ\x90\x00binary", "image/png"))])
    assert r.status_code == 415


def test_corrupted_pdf_does_not_crash(teacher, database):
    aid = database["main_assessment_id"]
    r = teacher.post(f"/api/assessments/{aid}/uploads", files=[("files", ("bad.pdf", b"%PDF-1.4 garbage", "application/pdf"))])
    assert r.status_code == 202
    job = teacher.get(f"/api/jobs/{r.json()['id']}").json()
    assert job["status"] == "failed" and "bad.pdf" in (job["error"] or "")


def test_dashboard_and_exports(teacher, database):
    d = teacher.get("/api/analytics/dashboard").json()
    assert {"checked_today", "in_progress", "needs_review", "completed"} <= d["cards"].keys()
    aid = database["synthetic"][0]
    an = teacher.get(f"/api/analytics/assessments/{aid}").json()
    assert an["summary"]["submitted"] > 0 and an["insights"]
    x = teacher.get(f"/api/exports/assessments/{aid}.xlsx")
    assert x.status_code == 200 and x.content[:2] == b"PK"
    p = teacher.get(f"/api/exports/assessments/{aid}.pdf")
    assert p.status_code == 200 and p.content.startswith(b"%PDF")
    w = teacher.get(f"/api/exports/assessments/{aid}.docx")
    assert w.status_code == 200 and w.content[:2] == b"PK"


def test_audit_log_records_actions(admin):
    items = admin.get("/api/audit?size=200").json()["items"]
    actions = {i["action"] for i in items}
    assert "auth.login" in actions and "export.excel" in actions


def test_student_data_export_and_purge(teacher, db):
    s = teacher.post("/api/students", json={"full_name": "Тест Оқушы", "class_id": teacher.get("/api/classes").json()[0]["id"]}).json()
    exp = teacher.get(f"/api/students/{s['id']}/export")
    assert exp.status_code == 200 and exp.json()["student"]["full_name"] == "Тест Оқушы"
    assert teacher.delete(f"/api/students/{s['id']}?purge=true").status_code == 204
    assert teacher.get(f"/api/students/{s['id']}").status_code == 404


def test_question_bank_and_generation(teacher, database):
    items = teacher.get("/api/question-bank").json()["items"]
    assert items
    r = teacher.post(f"/api/question-bank/{items[0]['id']}/add-to/{database['synthetic'][0]}")
    assert r.status_code == 201
    g = teacher.post("/api/ai/generate-assessment", json={"prompt": "7-сынып математика, квадрат теңдеулер бойынша БЖБ жаса",
                                                          "question_count": 5}).json()
    assert len(g["questions"]) == 5 and g["grade"] == 7
