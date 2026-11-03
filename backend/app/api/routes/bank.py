"""Question bank and AI assessment generation."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_assessment_or_404, staff
from app.core.pagination import PageParams
from app.models import Descriptor, Question, QuestionBankItem, User
from app.schemas import BankItemIn, GenerateIn, QuestionIn
from app.services.audit import audit
from app.services.generation import generate_assessment

router = APIRouter(tags=["question-bank"])


def _out(i: QuestionBankItem) -> dict:
    return {k: getattr(i, k) for k in ("id", "subject_id", "grade", "section", "topic", "objective_id", "text",
                                       "answer_type", "correct_answer", "max_score", "criteria", "tolerance", "options",
                                       "descriptors", "tags")}


@router.get("/question-bank")
def list_bank(q: str | None = None, subject_id: int | None = None, grade: int | None = None, p: PageParams = Depends(),
              db: Session = Depends(get_db), user: User = Depends(staff)):
    stmt = select(QuestionBankItem)
    if user.role != "admin":
        stmt = stmt.where(QuestionBankItem.owner_id == user.id)
    if q:
        stmt = stmt.where(or_(QuestionBankItem.text.ilike(f"%{q}%"), QuestionBankItem.topic.ilike(f"%{q}%")))
    if subject_id:
        stmt = stmt.where(QuestionBankItem.subject_id == subject_id)
    if grade:
        stmt = stmt.where(QuestionBankItem.grade == grade)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(QuestionBankItem.id.desc()).offset(p.offset).limit(p.size))
    return {"items": [_out(i) for i in items], "total": total, "page": p.page, "size": p.size}


@router.post("/question-bank", status_code=201)
def create_bank_item(body: BankItemIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    QuestionIn(number=1, **body.model_dump(exclude={"subject_id", "grade", "section", "topic", "tags"}))  # validate
    item = QuestionBankItem(owner_id=user.id, **body.model_dump(exclude={"descriptors"}),
                            descriptors=[d.model_dump() for d in body.descriptors])
    db.add(item)
    db.commit()
    return _out(item)


@router.put("/question-bank/{item_id}")
def update_bank_item(item_id: int, body: BankItemIn, db: Session = Depends(get_db), user: User = Depends(staff)):
    item = db.get(QuestionBankItem, item_id)
    if not item or (item.owner_id != user.id and user.role != "admin"):
        raise HTTPException(404)
    for k, v in body.model_dump(exclude={"descriptors"}).items():
        setattr(item, k, v)
    item.descriptors = [d.model_dump() for d in body.descriptors]
    db.commit()
    return _out(item)


@router.delete("/question-bank/{item_id}", status_code=204)
def delete_bank_item(item_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    item = db.get(QuestionBankItem, item_id)
    if item and (item.owner_id == user.id or user.role == "admin"):
        db.delete(item)
        db.commit()


@router.post("/question-bank/from-question/{question_id}", status_code=201)
def save_question_to_bank(question_id: int, db: Session = Depends(get_db), user: User = Depends(staff)):
    q = db.get(Question, question_id)
    if not q:
        raise HTTPException(404)
    a = get_assessment_or_404(db, user, q.version.assessment_id)
    item = QuestionBankItem(owner_id=user.id, subject_id=a.subject_id, grade=a.school_class.grade, section=a.section,
                            topic=a.topic, objective_id=q.objective_id, text=q.text, answer_type=q.answer_type,
                            correct_answer=q.correct_answer, max_score=q.max_score, criteria=q.criteria,
                            tolerance=q.tolerance, options=q.options,
                            descriptors=[{"number": d.number, "text": d.text, "points": d.points,
                                          "keywords": d.keywords} for d in q.descriptors])
    db.add(item)
    db.commit()
    return _out(item)


@router.post("/question-bank/{item_id}/add-to/{assessment_id}", status_code=201)
def add_bank_item_to_assessment(item_id: int, assessment_id: int, request: Request, db: Session = Depends(get_db),
                                user: User = Depends(staff)):
    item = db.get(QuestionBankItem, item_id)
    if not item or (item.owner_id != user.id and user.role != "admin"):
        raise HTTPException(404)
    a = get_assessment_or_404(db, user, assessment_id, write=True)
    v = next((x for x in a.versions if x.is_default), a.versions[0])
    number = (db.scalar(select(func.max(Question.number)).where(Question.version_id == v.id)) or 0) + 1
    q = Question(version_id=v.id, number=number, text=item.text, answer_type=item.answer_type,
                 correct_answer=item.correct_answer, max_score=item.max_score, criteria=item.criteria,
                 tolerance=item.tolerance, options=item.options, objective_id=item.objective_id)
    for d in item.descriptors or []:
        q.descriptors.append(Descriptor(number=d["number"], text=d["text"], points=d["points"], keywords=d.get("keywords")))
    db.add(q)
    a.max_score = (a.max_score or 0) + item.max_score
    v.template_layout = {}
    audit(db, user, "assessment.add_from_bank", "assessment", a.id, after={"bank_item": item.id}, request=request)
    db.commit()
    return {"question_id": q.id, "number": number}


@router.post("/ai/generate-assessment")
def ai_generate(body: GenerateIn, request: Request, db: Session = Depends(get_db), user: User = Depends(staff)):
    """«7-сынып математика, квадрат теңдеулер бойынша БЖБ жаса» → editable draft (questions, objectives, descriptors)."""
    draft = generate_assessment(db, body.prompt, body.question_count, body.subject_id)
    audit(db, user, "ai.generate", "assessment", None, after={"prompt": body.prompt[:200], "source": draft["source"]},
          request=request, commit=True)
    return draft
