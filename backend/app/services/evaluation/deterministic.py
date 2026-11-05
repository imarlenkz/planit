"""Deterministic evaluators for objective answer types (no AI involved)."""
import json
import re

from app.services.evaluation.normalize import (
    clean_text,
    normalize_formula,
    normalize_option,
    parse_number,
    parse_options,
    similarity,
)
from app.services.evaluation.types import EvaluationProposal

DETERMINISTIC_TYPES = {"single_choice", "multiple_choice", "numeric", "short_text", "formula", "matching", "table"}


def _ca(question) -> object:
    ca = question.correct_answer
    if isinstance(ca, dict) and "value" in ca and len(ca) <= 2:
        return ca["value"]
    return ca


def _acceptable(ca) -> list[str]:
    if isinstance(ca, list):
        return [str(x) for x in ca]
    if isinstance(ca, dict) and "accept" in ca:
        return [str(x) for x in ca["accept"]]
    return [str(ca)] if ca is not None else []


def eval_single_choice(question, answer: str, flags: list[str]) -> EvaluationProposal:
    expected = normalize_option(str(_ca(question)))
    got = normalize_option(answer)
    if len(got) > 1 or "multiple_marks" in flags:
        return EvaluationProposal("deterministic", got, expected, None, 0.4,
                                  "Оқушы бірнеше нұсқаны белгілеген", flags=["multiple_marks"],
                                  error_category="task_misunderstanding")
    ok = got == expected and bool(got)
    return EvaluationProposal("deterministic", got, expected, ok, 0.99,
                              "Жауап эталонмен сәйкес" if ok else f"Дұрыс жауап: {expected}",
                              fraction=1.0 if ok else 0.0,
                              error_category=None if ok else "concept")


def eval_multiple_choice(question, answer: str, flags: list[str]) -> EvaluationProposal:
    expected = set(parse_options(_ca(question)))
    got = set(parse_options(answer))
    right = len(expected & got)
    wrong = len(got - expected)
    frac = max(0.0, (right - wrong) / len(expected)) if expected else 0.0
    ok = got == expected
    reason = "Барлық дұрыс нұсқа таңдалған" if ok else (
        f"Дұрыс: {right}/{len(expected)}, артық таңдалған: {wrong}")
    return EvaluationProposal("deterministic", ",".join(sorted(got)), ",".join(sorted(expected)), ok, 0.97,
                              reason, fraction=frac, error_category=None if ok else "incomplete")


def eval_numeric(question, answer: str, flags: list[str]) -> EvaluationProposal:
    ca = _ca(question)
    expected = parse_number(ca if not isinstance(ca, list) else ca[0])
    got = parse_number(answer)
    tol = question.tolerance or 0.0
    if got is None:
        return EvaluationProposal("deterministic", answer or "", str(expected), False if not answer else None,
                                  0.9 if not answer else 0.5,
                                  "Сан табылмады" if answer else "Жауап бос",
                                  fraction=0.0, error_category="incomplete")
    ok = expected is not None and abs(got - expected) <= max(tol, 1e-9)
    shown = f"{got:g}"
    reason = "Сандық жауап сәйкес" + (f" (±{tol:g})" if tol else "") if ok else f"Күтілген: {expected:g}, алынған: {shown}"
    return EvaluationProposal("deterministic", shown, f"{expected:g}" if expected is not None else "", ok, 0.98, reason,
                              fraction=1.0 if ok else 0.0, error_category=None if ok else "calculation")


def eval_short_text(question, answer: str, flags: list[str]) -> EvaluationProposal:
    accepts = _acceptable(_ca(question))
    best = max((similarity(answer, a) for a in accepts), default=0.0)
    expected = accepts[0] if accepts else ""
    if best >= 0.97:
        return EvaluationProposal("deterministic", answer, expected, True, 0.97, "Жауап эталонмен сәйкес", fraction=1.0)
    if best >= 0.82:
        return EvaluationProposal("deterministic", answer, expected, True, 0.85,
                                  f"Жауап сәйкес, бірақ жазылуында айырма бар (ұқсастық {best:.0%})",
                                  fraction=1.0, error_category="spelling")
    if best >= 0.6:
        return EvaluationProposal("deterministic", answer, expected, None, 0.55,
                                  f"Жартылай ұқсас (ұқсастық {best:.0%}), мұғалім тексеруі қажет", fraction=0.0,
                                  error_category="terminology")
    return EvaluationProposal("deterministic", answer, expected, False, 0.9 if answer else 0.95,
                              "Жауап эталонмен сәйкес емес" if answer else "Жауап бос", fraction=0.0,
                              error_category="concept" if answer else "incomplete")


def eval_formula(question, answer: str, flags: list[str]) -> EvaluationProposal:
    accepts = _acceptable(_ca(question))
    got = normalize_formula(answer)
    for a in accepts:
        na = normalize_formula(a)
        if got == na:
            return EvaluationProposal("deterministic", answer, a, True, 0.96, "Формула сәйкес", fraction=1.0)
        # commutative sides: a=b vs b=a, and sorted factors for simple products
        if "=" in got and "=" in na and set(got.split("=")) == set(na.split("=")):
            return EvaluationProposal("deterministic", answer, a, True, 0.92, "Формула сәйкес (теңдік жақтары ауысқан)", fraction=1.0)
        if sorted(re.split(r"[*=]", got)) == sorted(re.split(r"[*=]", na)):
            return EvaluationProposal("deterministic", answer, a, True, 0.85, "Формула эквивалентті (көбейткіштер реті)", fraction=1.0)
    best = max((similarity(got, normalize_formula(a)) for a in accepts), default=0)
    return EvaluationProposal("deterministic", answer, accepts[0] if accepts else "", False if best < 0.7 else None,
                              0.85 if best < 0.7 else 0.5, "Формула сәйкес емес", fraction=0.0,
                              error_category="formula")


def _parse_pairs(s: str | dict) -> dict[str, str]:
    if isinstance(s, dict):
        return {str(k).strip(): normalize_option(str(v)) or clean_text(str(v)) for k, v in s.items()}
    try:
        data = json.loads(s)
        if isinstance(data, dict):
            return _parse_pairs(data)
    except (ValueError, TypeError):
        pass
    pairs = {}
    for k, v in re.findall(r"(\w+)\s*[-–—:=→>]+\s*(\w+)", s or ""):
        pairs[k.strip()] = normalize_option(v) or clean_text(v)
    return pairs


def eval_matching(question, answer: str, flags: list[str]) -> EvaluationProposal:
    expected = _parse_pairs(_ca(question) or {})
    got = _parse_pairs(answer or "")
    right = sum(1 for k, v in expected.items() if got.get(k) == v)
    frac = right / len(expected) if expected else 0.0
    ok = right == len(expected) and bool(expected)
    exp_s = ", ".join(f"{k}-{v}" for k, v in expected.items())
    return EvaluationProposal("deterministic", ", ".join(f"{k}-{v}" for k, v in got.items()), exp_s, ok,
                              0.93 if got else 0.6, f"Сәйкестендіру: {right}/{len(expected)} дұрыс", fraction=frac,
                              error_category=None if ok else "concept")


def eval_table(question, answer: str, flags: list[str]) -> EvaluationProposal:
    expected = _ca(question) or {}
    cells = expected.get("cells", expected) if isinstance(expected, dict) else {}
    got = _parse_pairs(answer or "")
    right = 0
    for k, v in cells.items():
        g = got.get(str(k))
        if g is None:
            continue
        nv, ng = parse_number(str(v)), parse_number(g)
        if (nv is not None and ng is not None and abs(nv - ng) <= (question.tolerance or 1e-9)) or similarity(str(v), g) > 0.85:
            right += 1
    frac = right / len(cells) if cells else 0.0
    return EvaluationProposal("deterministic", answer or "", json.dumps(cells, ensure_ascii=False), frac == 1.0,
                              0.85 if got else 0.5, f"Кесте ұяшықтары: {right}/{len(cells)} дұрыс", fraction=frac,
                              error_category=None if frac == 1 else "incomplete")


EVALUATORS = {
    "single_choice": eval_single_choice,
    "multiple_choice": eval_multiple_choice,
    "numeric": eval_numeric,
    "short_text": eval_short_text,
    "formula": eval_formula,
    "matching": eval_matching,
    "table": eval_table,
}


def evaluate_math_final_answer(question, answer: str) -> EvaluationProposal | None:
    """Math with no descriptors: compare the final numeric answer (x = 5 ≡ 5)."""
    ca = _ca(question)
    expected = parse_number(ca if not isinstance(ca, list) else ca[0])
    if expected is None:
        return None
    # last line / last "=" side is the final answer
    tail = (answer or "").strip().splitlines()[-1] if answer and answer.strip() else ""
    got = parse_number(tail.split("=")[-1]) if tail else None
    if got is None:
        return EvaluationProposal("deterministic", answer or "", str(ca), False, 0.6 if answer else 0.95,
                                  "Соңғы жауап табылмады" if answer else "Жауап бос", fraction=0.0,
                                  error_category="incomplete")
    ok = abs(got - expected) <= max(question.tolerance or 0, 1e-9)
    return EvaluationProposal("deterministic", f"{got:g}", str(ca), ok, 0.95,
                              "Соңғы жауап дұрыс" if ok else f"Соңғы жауап қате: күтілген {expected:g}",
                              fraction=1.0 if ok else 0.0, error_category=None if ok else "calculation")
