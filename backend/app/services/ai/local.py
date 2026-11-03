"""Offline rule-based provider: semantic concept matching with aliases. Default for demo/no-API setups.

It is intentionally conservative: confidence stays below the auto-approve threshold for open answers
so that a teacher sees them, unless the match is unambiguous.
"""
import re

from app.services.ai.base import EvalRequest
from app.services.evaluation.normalize import clean_text, concepts, parse_number

_NUM = re.compile(r"(?<![^\W\d_])\d+(?:[.,/]\d+)?")  # numbers not glued to letters (CO2 is a word)


def _coverage(target: set[str], got: set[str]) -> float:
    return len(target & got) / len(target) if target else 0.0


class LocalProvider:
    name = "local"
    model = "rule-based-v1"

    def evaluate(self, req: EvalRequest) -> tuple[dict, str]:
        student = req.student_answer or ""
        context = concepts(req.question_text)
        got = concepts(student)
        ref = concepts(req.reference_answer, exclude=context) or concepts(req.reference_answer)
        cov = _coverage(ref, got)
        descriptors = []
        score = 0.0
        if req.descriptors:
            clarity: list[float] = []
            student_nums = {round(n, 6) for n in (parse_number(x) for x in _NUM.findall(student)) if n is not None}
            for d in req.descriptors:
                kws = d.get("keywords") or []
                if kws:
                    hit = 0
                    for k in kws:
                        nums = [parse_number(x) for x in _NUM.findall(k)]
                        if nums:  # numeric keyword: all numbers must appear in the answer
                            hit += all(round(n, 6) in student_nums for n in nums if n is not None)
                        else:  # a keyword phrase must be covered (almost) completely
                            t = concepts(k)
                            need = 1.0 if len(t) <= 2 else 0.67
                            hit += bool(t) and _coverage(t, got) >= need - 1e-9
                    c = hit / len(kws)
                else:
                    t = concepts(d["text"], exclude=context | {"дұрыс", "жаза", "табад", "көрсе", "қолда", "есепт"})
                    c = _coverage(t, got) if t else cov
                met = c >= 0.5
                clarity.append(abs(c - 0.5) * 2)
                if met:
                    score += float(d["points"])
                descriptors.append({"number": d["number"], "met": met,
                                    "reason": ("Орындалды" if met else "Орындалмады") + f" (сәйкестік {c:.0%})"})
            score = min(score, req.max_score)
        else:
            score = req.max_score if cov >= 0.6 else (round(req.max_score * cov * 2) / 2 if cov >= 0.3 else 0.0)
        is_correct = score >= req.max_score - 1e-9
        if not clean_text(student):
            conf, reason, cat = 0.9, "Жауап бос", "incomplete"
            score, is_correct = 0.0, False
            descriptors = [{"number": d["number"], "met": False, "reason": "Жауап бос"} for d in req.descriptors]
        else:
            # confidence: high when coverage is clearly high or clearly low
            margin = (sum(clarity) / len(clarity)) if req.descriptors and clarity else abs(cov - 0.5) * 2
            conf = round(0.6 + 0.3 * margin, 2)
            if is_correct and req.descriptors:
                reason = "Барлық дескриптор орындалған, жауаптың мағынасы эталонмен сәйкес."
                cat = None
            elif is_correct:
                reason = f"Жауаптың мағынасы эталонмен сәйкес (негізгі ұғымдар {cov:.0%} қамтылған)."
                cat = None
            elif score > 0:
                missed = [str(d["number"]) for d in descriptors if not d["met"]]
                reason = (f"Жауап жартылай дұрыс. Орындалмаған дескриптор(лар): {', '.join(missed)}." if missed
                          else "Жауап жартылай дұрыс.")
                cat = "incomplete"
            else:
                reason = "Жауап эталонның негізгі ұғымдарын қамтымайды."
                cat = "concept"
        out = {"answer": student, "is_correct": is_correct, "score": float(score), "max_score": float(req.max_score),
               "confidence": float(min(conf, 0.92)), "reason": reason, "descriptors": descriptors, "error_category": cat}
        return out, "local"

    def complete_json(self, system: str, prompt: str, schema: dict) -> dict:
        raise NotImplementedError("Local provider cannot generate free-form content")
