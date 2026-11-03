"""Text / number normalisation shared by evaluators, OCR parsing and question matching."""
import re
import unicodedata
from difflib import SequenceMatcher
from fractions import Fraction

# Cyrillic letters that OCR / students use instead of Latin option letters
_OPTION_MAP = {"А": "A", "В": "B", "С": "C", "Д": "D", "Е": "E", "а": "A", "в": "B", "с": "C",
               "д": "D", "е": "E", "Ә": "A", "Б": "B", "б": "B", "Ф": "F"}
_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹", "01234567890123456789")

# concept aliases: every group is treated as one concept for semantic matching
CONCEPT_ALIASES: list[set[str]] = [
    {"co2", "көмірқышқыл", "көмірқышқылгаз", "углекислый", "carbon dioxide", "көмір қышқыл газ"},
    {"o2", "оттек", "оттегі", "кислород", "oxygen"},
    {"h2o", "су", "вода", "water"},
    {"сіңір", "пайдалан", "жұт", "алад", "қабылда", "поглощ", "absorb", "use"},
    {"бөл", "шығар", "выдел", "release", "produce"},
    {"өсімдік", "растен", "plant"},
    {"күн", "жарық", "солнц", "light", "sun"},
    {"ортақ бөлім", "общий знаменатель", "common denominator", "ортақбөлім"},
]
STOPWORDS = {
    "және", "мен", "бен", "пен", "да", "де", "та", "те", "бұл", "ол", "кезінде", "үшін", "арқылы",
    "сондықтан", "себебі", "еді", "бар", "жоқ", "ма", "ме", "па", "пе", "немесе", "әр", "бір",
    "и", "в", "на", "с", "по", "это", "что", "как", "the", "a", "an", "of", "and", "is", "to", "in",
}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def clean_text(s: str) -> str:
    s = nfc(s).translate(_SUBSCRIPTS).lower().replace("ё", "е")
    s = re.sub(r"[«»\"'`“”„.,;:!?()\[\]{}…—–-]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_option(s: str | None) -> str:
    """'b)', ' В ', '(c)' → 'B','B','C'."""
    if not s:
        return ""
    s = nfc(s).strip()
    s = "".join(_OPTION_MAP.get(ch, ch) for ch in s).upper()
    m = re.findall(r"[A-H]", s)
    return m[0] if len(m) == 1 else "".join(dict.fromkeys(m))


def parse_options(s: str | list | None) -> list[str]:
    if s is None:
        return []
    if isinstance(s, list):
        return sorted({normalize_option(str(x)) for x in s if normalize_option(str(x))})
    s2 = "".join(_OPTION_MAP.get(ch, ch) for ch in nfc(s)).upper()
    return sorted(set(re.findall(r"\b([A-H])\b", re.sub(r"[^A-H]", " ", s2)))) or sorted(set(re.findall(r"[A-H]", s2)))


_NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?(?:\s*/\s*\d+)?")


def parse_number(s: str | float | int | None) -> float | None:
    """Return the last number in a string: 'x = 5' → 5, '3/4' → 0.75, '2,5 см' → 2.5."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    txt = nfc(str(s)).translate(_SUBSCRIPTS).replace("−", "-").replace(" ", " ")
    txt = re.sub(r"(?<=\d) (?=\d{3}\b)", "", txt)  # thousands separator
    nums = _NUM_RE.findall(txt)
    if not nums:
        return None
    token = nums[-1].replace(" ", "").replace(",", ".")
    try:
        if "/" in token:
            return float(Fraction(token))
        return float(token)
    except (ValueError, ZeroDivisionError):
        return None


def similarity(a: str, b: str) -> float:
    a, b = clean_text(a), clean_text(b)
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def stem(word: str) -> str:
    """Very light stemmer for Kazakh/Russian/English: keep first 5 chars of long words."""
    w = word.strip()
    if re.fullmatch(r"[a-z]{1,3}\d", w):  # chemical formulae co2, o2, h2o
        return w
    return w[:5] if len(w) > 5 else w


def concepts(text: str, exclude: set[str] | None = None) -> set[str]:
    """Map text to a set of concept ids (alias groups or stems)."""
    t = clean_text(text)
    found: set[str] = set()
    for i, group in enumerate(CONCEPT_ALIASES):
        for alias in group:
            if " " in alias and alias in t:
                found.add(f"@{i}")
                t = t.replace(alias, " ")
    for w in t.split():
        if w in STOPWORDS or (len(w) < 2 and not w.isdigit()):
            continue
        st = stem(w)
        cid = None
        for i, group in enumerate(CONCEPT_ALIASES):
            if any(st.startswith(stem(a)) or stem(a).startswith(st) and len(st) >= 4 for a in group if " " not in a):
                cid = f"@{i}"
                break
        found.add(cid or st)
    if exclude:
        found -= exclude
    return found


def normalize_formula(s: str) -> str:
    s = nfc(s or "").translate(_SUBSCRIPTS).lower()
    s = s.replace("×", "*").replace("·", "*").replace("÷", "/").replace("−", "-").replace("^", "**")
    s = re.sub(r"\s+", "", s)
    return s
