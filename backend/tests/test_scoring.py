"""Unit tests: ScoringEngine, partial credit, percentages, deterministic evaluators."""
from types import SimpleNamespace as N

import pytest

from app.services.evaluation.deterministic import EVALUATORS, evaluate_math_final_answer
from app.services.evaluation.dispatcher import evaluate_answer
from app.services.evaluation.types import DescriptorJudgment, EvaluationProposal
from app.services.scoring import ScoringEngine, Thresholds, confidence_band, level_for, percent, round_half


def Q(answer_type="numeric", correct=None, max_score=1, tolerance=None, descriptors=(), text=""):
    return N(answer_type=answer_type, correct_answer=correct, max_score=max_score, tolerance=tolerance,
             descriptors=list(descriptors), text=text, criteria="", options=None)


def D(i, pts, text="d", kw=None):
    return N(id=i, number=i, points=pts, text=text, keywords=kw)


engine = ScoringEngine(Thresholds(high=95, medium=80, auto_approve=True))


def test_multiple_choice_correct():
    q = Q("single_choice", "B", 1)
    r = engine.score(q, evaluate_answer(q, "B", []), 0.99)
    assert (r.score, r.status, r.review_status) == (1, "correct", "auto_approved")


def test_cyrillic_option_letter_is_normalised():
    q = Q("single_choice", "B", 1)
    assert engine.score(q, evaluate_answer(q, "В", []), 0.99).score == 1  # Cyrillic В


def test_multiple_marks_on_single_choice_goes_to_review():
    q = Q("single_choice", "B", 1)
    r = engine.score(q, evaluate_answer(q, "A,B", ["multiple_marks"]), 0.99)
    assert r.review_status == "needs_review" and r.status == "doubtful"


def test_multiple_choice_partial():
    q = Q("multiple_choice", ["A", "C"], 2)
    assert engine.score(q, evaluate_answer(q, "A", []), 0.99).score == 1
    assert engine.score(q, evaluate_answer(q, "A,C", []), 0.99).score == 2
    assert engine.score(q, evaluate_answer(q, "A,C,D", []), 0.99).score == 1  # wrong pick cancels one right


@pytest.mark.parametrize("answer,expected", [("25", 1), ("25,00", 1), ("24.995", 1), ("24.9", 0), ("x = 25", 1)])
def test_numeric_with_tolerance(answer, expected):
    q = Q("numeric", {"value": 25}, 1, tolerance=0.01)
    assert engine.score(q, evaluate_answer(q, answer, []), 0.99).score == expected


def test_numeric_fraction():
    q = Q("numeric", {"value": 0.75}, 1)
    assert engine.score(q, evaluate_answer(q, "3/4", []), 0.99).score == 1


def test_math_x_equals_5_matches_5():
    q = Q("math", "x = 5", 2)
    p = evaluate_math_final_answer(q, "5")
    assert p.is_correct and engine.score(q, p, 0.99).score == 2
    assert evaluate_math_final_answer(q, "2x = 10\nx = 5").is_correct


def test_partial_credit_by_descriptors_3_of_4():
    q = Q("math", "x=5", 4, descriptors=[D(1, 1), D(2, 1), D(3, 1), D(4, 1)])
    p = EvaluationProposal("ai", "...", "x=5", False, 0.9, "Әдіс дұрыс, соңғы есептеу қате", suggested_score=3,
                           descriptors=[DescriptorJudgment(1, 1, True, 0.9), DescriptorJudgment(2, 2, True, 0.9),
                                        DescriptorJudgment(3, 3, False, 0.9), DescriptorJudgment(4, 4, True, 0.9)])
    r = engine.score(q, p, 0.95)
    assert r.score == 3 and r.status == "partial"
    assert "3-дескриптор: орындалмады" in r.reasoning


def test_ai_score_cannot_exceed_descriptors():
    """Hallucination guard: the AI says 4/4 but only judged 2 descriptors met → engine gives 2 and lowers trust."""
    q = Q("open", "...", 4, descriptors=[D(1, 2), D(2, 2)])
    p = EvaluationProposal("ai", "...", "...", True, 0.99, "ok", suggested_score=4,
                           descriptors=[DescriptorJudgment(1, 1, True, 0.99), DescriptorJudgment(2, 2, False, 0.99)])
    r = engine.score(q, p, 0.99)
    assert r.score == 2 and r.confidence < 95


def test_score_is_clamped():
    q = Q("open", "...", 2)
    p = EvaluationProposal("ai", "...", "...", False, 0.9, "x", suggested_score=7)
    assert engine.score(q, p, 0.9).score == 2


def test_low_ocr_confidence_requires_review():
    q = Q("numeric", {"value": 24}, 1)
    r = engine.score(q, evaluate_answer(q, "24", []), 0.6)
    assert r.score == 1 and r.review_status == "needs_review"


def test_confidence_bands():
    assert confidence_band(97) == "high" and confidence_band(85) == "medium" and confidence_band(50) == "low"


def test_percent_and_levels():
    assert percent(17, 20) == 85.0 and percent(0, 0) == 0
    assert level_for(85.0) == ("high", 5) and level_for(70) == ("medium", 4) and level_for(39.9) == ("very_low", 2)
    assert round_half(1.74) == 1.5


def test_matching_partial():
    q = Q("matching", {"1": "B", "2": "C", "3": "A"}, 3)
    assert engine.score(q, EVALUATORS["matching"](q, "1-B, 2-A, 3-C", []), 0.99).score == 1
    assert engine.score(q, EVALUATORS["matching"](q, "1-B 2-C 3-A", []), 0.99).score == 3


def test_short_text_spelling_tolerance():
    q = Q("short_text", {"accept": ["дұрыс бөлшек"]}, 1)
    p = EVALUATORS["short_text"](q, "дурыс бөлшек", [])
    assert p.is_correct and p.error_category == "spelling"


def test_formula_equivalence():
    q = Q("formula", "S = a·b", 1)
    assert EVALUATORS["formula"](q, "S=a*b", []).is_correct
    assert EVALUATORS["formula"](q, "a*b=S", []).is_correct


def test_unreadable_answer_goes_to_manual_review():
    q = Q("numeric", {"value": 1}, 1)
    r = engine.score(q, evaluate_answer(q, "", ["unreadable"]), 0.1)
    assert r.review_status == "needs_review" and r.status == "doubtful"
