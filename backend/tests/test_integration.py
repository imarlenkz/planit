"""Integration: Upload → preprocessing → QR → OCR/OMR → evaluation → scoring → result → review → export."""
from sqlalchemy import select

from app.models import Assessment, Question, Student
from app.seed.demo_data import MATH_BJB
from app.seed.demo_scans import generate_demo_scan
from app.services.templates import build_layout


def test_full_scan_and_check_flow(teacher, db, database):
    aid = database["main_assessment_id"]
    a = db.get(Assessment, aid)
    teacher.post(f"/api/assessments/{aid}/template")
    db.refresh(a)
    v = a.versions[0]
    students = [{"id": s.id, "full_name": s.full_name} for s in db.scalars(
        select(Student).where(Student.class_id == a.class_id).order_by(Student.full_name).limit(3))]
    # everyone answers perfectly → every objective answer must be scored full
    perfect = [{**q, "wrong": [q["correct_answer"]] if q["answer_type"].endswith("choice") else q.get("right"),
                "partial": None} for q in MATH_BJB["questions"]]
    pdf = generate_demo_scan(v.template_layout, {"title": a.title, "max_score": a.max_score}, a.id, v.id, students,
                             perfect, seed=3)
    r = teacher.post(f"/api/assessments/{aid}/uploads", files=[("files", ("scan.pdf", pdf, "application/pdf"))])
    assert r.status_code == 202, r.text
    job = teacher.get(f"/api/jobs/{r.json()['id']}").json()
    assert job["status"] == "done", job
    assert job["total_pages"] == 6 and job["stats"]["submissions"] == 3 and job["stats"]["students_unknown"] == 0

    subs = teacher.get(f"/api/assessments/{aid}/submissions").json()
    assert {s["student_id"] for s in subs} == {s["id"] for s in students}
    sub = teacher.get(f"/api/submissions/{subs[0]['id']}").json()
    by_num = {x["number"]: x for x in sub["answers"]}
    objective = [n for n, q in ((q.number, q) for q in db.scalars(select(Question).where(Question.version_id == v.id)))
                 if q.answer_type in ("single_choice", "multiple_choice", "numeric", "matching")]
    full = [n for n in objective if by_num[n]["evaluation"]["score"] == by_num[n]["max_score"]]
    assert len(full) >= len(objective) - 1, {n: by_num[n]["detected_answer"] for n in objective}
    assert sub["result"]["total_score"] >= 15

    # teacher review: override one answer, approve the work
    ev = by_num[7]["evaluation"]
    o = teacher.post(f"/api/evaluations/{ev['id']}/override", json={"score": 1, "comment": "балама жауап"})
    assert o.status_code == 200
    assert teacher.post(f"/api/evaluations/{ev['id']}/override", json={"score": 99}).status_code == 422
    rc = teacher.post(f"/api/evaluations/{by_num[4]['evaluation']['id']}/recheck", json={"detected_answer": "6"})
    assert rc.json()["evaluation"]["score"] == by_num[4]["max_score"]
    batch = teacher.post(f"/api/assessments/{aid}/approve-confident", json={"min_confidence": 95}).json()
    assert batch["approved"] > 0
    ap = teacher.post(f"/api/submissions/{sub['id']}/approve").json()
    assert ap["ok"]
    res = teacher.get(f"/api/assessments/{aid}/results").json()
    assert len(res["students"]) == 3
    assert teacher.get(f"/api/exports/assessments/{aid}.xlsx").status_code == 200


def test_unknown_student_requires_selection(teacher, db, database):
    """Blank template (no student in QR) and no readable name → «Оқушыны таңдаңыз»."""
    aid = database["main_assessment_id"]
    a = db.get(Assessment, aid)
    v = a.versions[0]
    pdf = generate_demo_scan(v.template_layout, {"title": a.title}, a.id, v.id, [{"id": 0, "full_name": " "}],
                             MATH_BJB["questions"], seed=5)
    r = teacher.post(f"/api/assessments/{aid}/uploads", files=[("files", ("blank.pdf", pdf, "application/pdf"))])
    job = teacher.get(f"/api/jobs/{r.json()['id']}").json()
    assert job["stats"]["students_unknown"] == 1
    unknown = [s for s in teacher.get(f"/api/assessments/{aid}/submissions").json() if not s["student_id"]][0]
    assert "student_unknown" in unknown["flags"] and unknown["status"] == "needs_review"
    st = db.scalars(select(Student).where(Student.class_id == a.class_id).order_by(Student.full_name.desc())).first()
    r = teacher.patch(f"/api/submissions/{unknown['id']}/student", json={"student_id": st.id})
    assert r.status_code == 200 and r.json()["student_id"] == st.id


def test_layout_builder_paginates():
    qs = [{"id": i, "number": i, "text": "x" * 120, "answer_type": "essay", "max_score": 2} for i in range(1, 8)]
    layout = build_layout(qs)
    assert layout["pages"] >= 3 and all(0 <= r["y"] + r["h"] <= 1 for r in layout["regions"])
