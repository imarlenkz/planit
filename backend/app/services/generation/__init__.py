"""AI generation of БЖБ/ТЖБ drafts. Output is always an editable draft; nothing is saved automatically."""
import logging
import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ANSWER_TYPES, QuestionBankItem
from app.services.ai.service import AIService

log = logging.getLogger(__name__)

GEN_SCHEMA = {
    "type": "object",
    "required": ["title", "questions"],
    "properties": {
        "title": {"type": "string"},
        "section": {"type": "string"},
        "questions": {"type": "array", "items": {
            "type": "object",
            "required": ["number", "text", "answer_type", "correct_answer", "max_score", "descriptors"],
            "properties": {
                "number": {"type": "integer"}, "text": {"type": "string"},
                "answer_type": {"type": "string", "enum": list(ANSWER_TYPES)},
                "options": {"type": ["object", "null"]},
                "correct_answer": {},
                "max_score": {"type": "number"},
                "objective_code": {"type": "string"}, "objective": {"type": "string"},
                "criteria": {"type": "string"},
                "descriptors": {"type": "array", "items": {"type": "object", "required": ["number", "text", "points"],
                                                            "properties": {"number": {"type": "integer"},
                                                                           "text": {"type": "string"},
                                                                           "points": {"type": "number"}}}},
            }}},
    },
}

SYSTEM = ("You design criteria-based summative assessments (БЖБ/ТЖБ) for Kazakhstan schools following the "
          "updated curriculum. Write in Kazakh. Each task links to a learning objective code (e.g. 7.2.1.4), has "
          "assessment criteria, descriptors whose points sum to max_score, and a correct answer.")


def generate_assessment(db: Session, prompt: str, count: int, subject_id: int | None) -> dict:
    if settings.AI_ENABLED and settings.AI_PROVIDER in ("openai", "anthropic"):
        try:
            data = AIService().complete_json(SYSTEM, f"{prompt}\nТапсырма саны: {count}.", GEN_SCHEMA)
            for q in data["questions"]:
                total = sum(d["points"] for d in q.get("descriptors", []))
                if total and abs(total - q["max_score"]) > 1e-6:
                    q["max_score"] = total
            data["source"] = settings.AI_PROVIDER
            data["max_score"] = sum(q["max_score"] for q in data["questions"])
            return data
        except Exception as e:  # fall back to offline generation
            log.warning("AI generation failed: %s", e)
    return _offline(db, prompt, count, subject_id)


def _offline(db: Session, prompt: str, count: int, subject_id: int | None) -> dict:
    """Without an LLM: pick matching items from the question bank and fill the rest with a structured skeleton."""
    words = [w for w in re.findall(r"\w{4,}", prompt.lower()) if not w.isdigit()]
    stmt = select(QuestionBankItem)
    if subject_id:
        stmt = stmt.where(QuestionBankItem.subject_id == subject_id)
    if words:
        stmt = stmt.where(or_(*[QuestionBankItem.text.ilike(f"%{w[:6]}%") for w in words],
                              *[QuestionBankItem.topic.ilike(f"%{w[:6]}%") for w in words]))
    found = list(db.scalars(stmt.limit(count)))
    grade = re.search(r"(\d{1,2})\s*-?\s*(сынып|класс|grade)", prompt.lower())
    topic = prompt.strip().rstrip(".")
    questions = []
    for i, it in enumerate(found, 1):
        questions.append({"number": i, "text": it.text, "answer_type": it.answer_type, "options": it.options,
                          "correct_answer": it.correct_answer, "max_score": it.max_score, "criteria": it.criteria,
                          "descriptors": it.descriptors or [], "objective_code": ""})
    skeleton = [
        ("single_choice", "Тақырып бойынша негізгі ұғымды анықтаңыз (дұрыс жауапты таңдаңыз).", 1,
         [{"number": 1, "text": "Дұрыс нұсқаны таңдайды", "points": 1}]),
        ("numeric", "Есепті шығарыңыз және жауабын жазыңыз.", 2,
         [{"number": 1, "text": "Шешу әдісін дұрыс таңдайды", "points": 1}, {"number": 2, "text": "Дұрыс жауап алады", "points": 1}]),
        ("math", "Есепті толық шешіңіз, әр қадамды көрсетіңіз.", 4,
         [{"number": 1, "text": "Есептің шартын математикалық түрде жазады", "points": 1},
          {"number": 2, "text": "Шешу алгоритмін дұрыс қолданады", "points": 2},
          {"number": 3, "text": "Жауабын тексереді", "points": 1}]),
        ("open", "Ұғымның мағынасын өз сөзіңізбен түсіндіріңіз.", 2,
         [{"number": 1, "text": "Анықтаманы дұрыс береді", "points": 1}, {"number": 2, "text": "Мысал келтіреді", "points": 1}]),
        ("short_text", "Терминді жазыңыз.", 1, [{"number": 1, "text": "Терминді дұрыс атайды", "points": 1}]),
        ("matching", "Сәйкестендіріңіз.", 3, [{"number": i, "text": f"{i}-жұпты дұрыс сәйкестендіреді", "points": 1} for i in (1, 2, 3)]),
    ]
    n = len(questions)
    while len(questions) < count:
        t, text, pts, descs = skeleton[(len(questions) - n) % len(skeleton)]
        questions.append({"number": len(questions) + 1, "text": f"{text} ({topic})", "answer_type": t,
                          "options": {"A": "", "B": "", "C": "", "D": ""} if t == "single_choice" else None,
                          "correct_answer": "A" if t == "single_choice" else "", "max_score": pts,
                          "criteria": "", "descriptors": descs, "objective_code": ""})
    return {"title": f"БЖБ — {topic[:80]}", "section": topic[:120], "grade": int(grade.group(1)) if grade else None,
            "questions": questions, "max_score": sum(q["max_score"] for q in questions),
            "source": "offline", "note": "AI провайдері қосылмаған: сұрақтар банкі мен құрылымдық үлгі қолданылды. "
                                        "Мәтіндер мен жауаптарды редакциялаңыз."}
