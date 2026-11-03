"""Unit tests: AI schema validation, local semantic evaluator, OCR parsing, question & student matching."""
from types import SimpleNamespace as N

import pytest

from app.services.ai.schema import SchemaError, validate_evaluation
from app.services.ai.service import AIService
from app.services.detection.structure import detect_tasks
from app.services.detection.student import match_student
from app.services.evaluation.normalize import normalize_option, parse_number, parse_options
from app.services.ocr.base import OCROutput, OCRWord
from app.services.templates import parse_qr, qr_payload


def _q(**kw):
    base = dict(id=1, number=1, text="", answer_type="open", correct_answer="", max_score=2, criteria="",
                tolerance=None, options=None, descriptors=[])
    base.update(kw)
    return N(**base)


def test_schema_rejects_score_above_max():
    data = {"answer": "x", "is_correct": True, "score": 3, "max_score": 2, "confidence": 0.9, "reason": "",
            "descriptors": [], "error_category": None}
    with pytest.raises(SchemaError):
        validate_evaluation(data, 2, set())


def test_schema_rejects_unknown_descriptor_and_extra_fields():
    data = {"answer": "x", "is_correct": True, "score": 1, "max_score": 2, "confidence": 0.9, "reason": "",
            "descriptors": [{"number": 5, "met": True, "reason": ""}], "error_category": None}
    with pytest.raises(SchemaError):
        validate_evaluation(data, 2, {1, 2})
    data2 = {**data, "descriptors": [], "bonus": 10}
    with pytest.raises(SchemaError):
        validate_evaluation(data2, 2, set())


def test_photosynthesis_meaning_based_full_marks():
    q = _q(text="Фотосинтез кезінде не болады?",
           correct_answer="Фотосинтез кезінде өсімдік көмірқышқыл газын сіңіріп, оттек бөледі.",
           descriptors=[N(id=1, number=1, text="CO2 сіңіреді", points=1, keywords=["CO2 сіңіреді"]),
                        N(id=2, number=2, text="оттек бөледі", points=1, keywords=["оттек бөледі"])])
    p = AIService().evaluate(q, "Өсімдік CO₂ пайдаланып, O₂ бөледі.")
    assert p.suggested_score == 2 and all(j.met for j in p.descriptors)


def test_wrong_concept_gets_partial_not_full():
    q = _q(correct_answer="Бөлімдері бірдей екі бөлшектің алымы үлкені үлкен болады.",
           descriptors=[N(id=1, number=1, text="", points=1, keywords=["бөлімдері бірдей"]),
                        N(id=2, number=2, text="", points=1, keywords=["алымы үлкен"])])
    assert AIService().evaluate(q, "Бөлімі үлкен бөлшек үлкен").suggested_score == 0
    assert AIService().evaluate(q, "Алымы үлкен бөлшек үлкен").suggested_score == 1


class Boom:
    name, model = "boom", "x"

    def evaluate(self, req):
        return {"answer": "", "is_correct": True, "score": 99, "max_score": 2, "confidence": 1, "reason": "",
                "descriptors": [], "error_category": None}, "{}"


def test_invalid_ai_output_routes_to_manual_review():
    p = AIService(Boom()).evaluate(_q(), "anything")
    assert "manual_review_required" in p.flags and p.suggested_score is None


@pytest.mark.parametrize("s,v", [("x = 5", 5), ("2,5 см", 2.5), ("3/4", 0.75), ("−3", -3), ("ответ: 12", 12),
                                 ("10 000", 10000), ("", None)])
def test_parse_number(s, v):
    assert parse_number(s) == v


def test_option_parsing():
    assert normalize_option(" (b) ") == "B" and normalize_option("С") == "C"
    assert parse_options("A, C") == ["A", "C"]


def test_qr_roundtrip():
    assert parse_qr(qr_payload(5, 7, 12, 2)) == {"assessment_id": 5, "version_id": 7, "student_id": 12, "page": 2}
    assert parse_qr("https://example.com") is None


def test_student_matching_fuzzy():
    roster = [(1, "Айдос Ермек"), (2, "Айдана Сапарова"), (3, "Данияр Қасымов")]
    sid, conf, _ = match_student("Аты-жөні: Сапарова Айдана", roster)
    assert sid == 2 and conf > 0.8
    sid, conf, _ = match_student("Аты-жөні: Даниар Касымов", roster)
    assert sid == 3
    sid, _, _ = match_student("Аты-жөні: Белгісіз Адам", roster)
    assert sid is None


def _line(text, y, line):
    words, x = [], 50
    for w in text.split():
        words.append(OCRWord(w, 0.9, (x, y, 10 * len(w), 20), line=line, block=1))
        x += 10 * len(w) + 8
    return words


def test_structure_detection_without_template():
    words = (_line("1. 3/4 · 8 = ?", 100, 1) + _line("Жауабы: 6", 130, 2) + _line("2-тапсырма", 200, 3) +
             _line("Фотосинтезді түсіндір", 230, 4) + _line("Өсімдік оттек бөледі", 260, 5))
    out = OCROutput(text="", words=words, mean_confidence=0.9)
    qs = [_q(id=10, number=1, text="3/4 · 8 = ?", answer_type="numeric"),
          _q(id=11, number=2, text="Фотосинтезді түсіндір")]
    res = {r.number: r for r in detect_tasks(out, 1000, 1400, qs)}
    assert res[1].text == "6" and res[1].question_id == 10
    assert "оттек" in res[2].text and "Фотосинтез" not in res[2].text
