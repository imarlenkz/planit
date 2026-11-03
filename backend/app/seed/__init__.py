"""Demo data seeding. Run: `python -m app.seed` (idempotent: skipped when the demo school exists)."""
import logging
import random
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Answer,
    Assessment,
    AssessmentVersion,
    ClassTeacher,
    Descriptor,
    Evaluation,
    EvaluationItem,
    LearningObjective,
    Question,
    QuestionBankItem,
    Result,
    School,
    SchoolClass,
    Student,
    Subject,
    Submission,
    Teacher,
    User,
)
from app.seed import demo_data as D
from app.services.feedback import build_feedback
from app.services.scoring import level_for, percent

log = logging.getLogger(__name__)
DEMO_PASSWORD = "demo12345"


def _question(version_id: int, q: dict, objectives: dict[str, LearningObjective]) -> Question:
    obj = objectives.get(q.get("objective"))
    qq = Question(version_id=version_id, number=q["number"], text=q["text"], answer_type=q["answer_type"],
                  correct_answer=q["correct_answer"], max_score=q["max_score"], criteria=q.get("criteria"),
                  tolerance=q.get("tolerance"), options=q.get("options"), objective_id=obj.id if obj else None)
    for d in q.get("descriptors", []):
        qq.descriptors.append(Descriptor(number=d["number"], text=d["text"], points=d["points"], keywords=d.get("keywords")))
    return qq


def seed_demo(db: Session) -> dict:
    existing = db.scalar(select(School).where(School.name == D.SCHOOL["name"]))
    if existing:
        return {"skipped": True}
    rng = random.Random(7)
    school = School(**D.SCHOOL)
    db.add(school)
    db.flush()

    admin = User(email="admin@planit.kz", password_hash=hash_password(DEMO_PASSWORD), full_name="Жүйе әкімшісі",
                 role="admin", school_id=None)
    director = User(email="director@planit.kz", password_hash=hash_password(DEMO_PASSWORD),
                    full_name="Гүлмира Ахметова", role="school_admin", school_id=school.id)
    teacher_u = User(email="teacher@planit.kz", password_hash=hash_password(DEMO_PASSWORD),
                     full_name="Айгүл Серікқызы", role="teacher", school_id=school.id)
    teacher2_u = User(email="teacher2@planit.kz", password_hash=hash_password(DEMO_PASSWORD),
                      full_name="Ерлан Жақыпов", role="teacher", school_id=school.id)
    db.add_all([admin, director, teacher_u, teacher2_u])
    db.flush()
    teacher = Teacher(user_id=teacher_u.id, school_id=school.id, position="Математика пәні мұғалімі")
    teacher2 = Teacher(user_id=teacher2_u.id, school_id=school.id, position="Пән мұғалімі")
    db.add_all([teacher, teacher2])
    db.flush()

    subjects = {}
    for name, code in D.SUBJECTS:
        s = Subject(name=name, code=code, school_id=None)
        db.add(s)
        subjects[code] = s
    db.flush()
    objectives = {}
    for code, desc, subj, grade in D.OBJECTIVES:
        o = LearningObjective(code=code, description=desc, subject_id=subjects[subj].id, grade=grade)
        db.add(o)
        objectives[code] = o
    db.flush()

    classes = {}
    used = set()
    n = 0
    for name, grade, letter, count in D.CLASSES:
        c = SchoolClass(school_id=school.id, name=name, grade=grade, letter=letter,
                        homeroom_teacher_id=teacher.id if name == "5А" else teacher2.id)
        db.add(c)
        db.flush()
        classes[name] = c
        db.add(ClassTeacher(class_id=c.id, teacher_id=teacher.id))  # demo teacher teaches every class
        if name != "5А":
            db.add(ClassTeacher(class_id=c.id, teacher_id=teacher2.id))
        for i in range(count):
            gender = "m" if i % 2 == 0 else "f"
            for _ in range(50):
                first = rng.choice(D.BOYS if gender == "m" else D.GIRLS)
                last = rng.choice(D.SURNAMES_M if gender == "m" else D.SURNAMES_F)
                full = f"{first} {last}"
                if full not in used:
                    break
            used.add(full)
            n += 1
            db.add(Student(school_id=school.id, class_id=c.id, full_name=full, gender=gender,
                           student_code=f"DEMO{n:04d}"))
    db.flush()
    # a student account for the student portal
    first_student = db.scalar(select(Student).where(Student.class_id == classes["5А"].id).order_by(Student.full_name))
    stu_user = User(email="student@planit.kz", password_hash=hash_password(DEMO_PASSWORD),
                    full_name=first_student.full_name, role="student", school_id=school.id)
    db.add(stu_user)
    db.flush()
    first_student.user_id = stu_user.id

    def make_assessment(spec: dict, owner: Teacher, offset_days: int) -> Assessment:
        a = Assessment(type=spec["type"], title=spec["title"], subject_id=subjects[spec["subject"]].id,
                       class_id=classes[spec["class"]].id, teacher_id=owner.id, school_id=school.id,
                       quarter=spec.get("quarter"), section=spec.get("section"), topic=spec.get("topic"),
                       date=date.today() + timedelta(days=offset_days), max_score=spec["max_score"], status="active")
        v = AssessmentVersion(version_label="1-нұсқа", is_default=True)
        a.versions.append(v)
        db.add(a)
        db.flush()
        for q in spec["questions"]:
            db.add(_question(v.id, q, objectives))
        db.flush()
        return a

    main = make_assessment(D.MATH_BJB, teacher, 0)
    synthetic = []
    for spec in D.OTHER:
        a = make_assessment(spec, teacher, spec.get("date_offset", -7))
        _synthesise_results(db, a, rng)
        a.status = "completed"
        synthetic.append(a.id)

    # question bank from the main assessment
    for q in D.MATH_BJB["questions"][:6]:
        obj = objectives.get(q.get("objective"))
        db.add(QuestionBankItem(owner_id=teacher_u.id, subject_id=subjects["MATH"].id, grade=5, section="Жай бөлшектер",
                                topic="Жай бөлшектер", objective_id=obj.id if obj else None, text=q["text"],
                                answer_type=q["answer_type"], correct_answer=q["correct_answer"],
                                max_score=q["max_score"], options=q.get("options"), tolerance=q.get("tolerance"),
                                descriptors=q.get("descriptors", []), tags=["5-сынып", "бөлшек"]))
    db.commit()
    return {"school_id": school.id, "main_assessment_id": main.id, "synthetic": synthetic}


def _synthesise_results(db: Session, a: Assessment, rng: random.Random) -> None:
    """Demo-only: realistic finalised results for dashboards (no scans)."""
    students = list(db.scalars(select(Student).where(Student.class_id == a.class_id)))
    qs = list(db.scalars(select(Question).where(Question.version_id == a.versions[0].id).order_by(Question.number)))
    difficulty = {q.id: rng.uniform(0.45, 0.95) for q in qs}
    cats = ["calculation", "concept", "incomplete", "spelling", "formula", "logic"]
    for st in students:
        ability = rng.uniform(0.55, 1.15)
        sub = Submission(assessment_id=a.id, version_id=a.versions[0].id, student_id=st.id, status="approved",
                         detection_method="qr", detection_confidence=1.0)
        db.add(sub)
        db.flush()
        total = 0.0
        items = []
        for q in qs:
            p = max(0.0, min(1.0, difficulty[q.id] * ability + rng.uniform(-0.15, 0.15)))
            score = round(q.max_score * p * 2) / 2
            ans = Answer(submission_id=sub.id, question_id=q.id, detected_answer="(demo)", ocr_confidence=0.95)
            db.add(ans)
            db.flush()
            status = "correct" if score >= q.max_score else ("incorrect" if score == 0 else "partial")
            ev = Evaluation(answer_id=ans.id, question_id=q.id, submission_id=sub.id, method="deterministic",
                            score=score, max_score=q.max_score, confidence=rng.uniform(86, 99.5), status=status,
                            review_status="approved", reasoning="Demo нәтиже",
                            error_category=None if status == "correct" else rng.choice(cats))
            db.add(ev)
            db.flush()
            remaining = score
            for d in q.descriptors:
                met = remaining >= d.points
                remaining -= d.points if met else 0
                db.add(EvaluationItem(evaluation_id=ev.id, descriptor_id=d.id, met=met,
                                      points_awarded=d.points if met else 0, confidence=0.9))
            total += score
            items.append({"label": f"{q.number}-тапсырма", "percent": percent(score, q.max_score),
                          "error_category": ev.error_category})
        pct = percent(total, a.max_score)
        text, strengths, weaknesses = build_feedback(items, pct)
        db.add(Result(submission_id=sub.id, student_id=st.id, assessment_id=a.id, total_score=total,
                      max_score=a.max_score, percent=pct, level=level_for(pct)[0], feedback=text, strengths=strengths,
                      weaknesses=weaknesses, is_final=True, approved_at=datetime.now(UTC)))
