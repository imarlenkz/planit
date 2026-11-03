"""JSON schema every LLM evaluation must satisfy (hallucination protection)."""
import jsonschema

EVALUATION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "is_correct", "score", "max_score", "confidence", "reason", "descriptors", "error_category"],
    "properties": {
        "answer": {"type": "string"},
        "is_correct": {"type": "boolean"},
        "score": {"type": "number", "minimum": 0},
        "max_score": {"type": "number", "minimum": 0},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string", "maxLength": 2000},
        "descriptors": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["number", "met", "reason"],
                "properties": {
                    "number": {"type": "integer", "minimum": 1},
                    "met": {"type": "boolean"},
                    "reason": {"type": "string", "maxLength": 1000},
                },
            },
        },
        "error_category": {
            "type": ["string", "null"],
            "enum": [None, "calculation", "formula", "concept", "terminology", "spelling", "logic",
                     "task_misunderstanding", "incomplete"],
        },
    },
}

ERROR_CATEGORIES = EVALUATION_SCHEMA["properties"]["error_category"]["enum"][1:]


class SchemaError(ValueError):
    pass


def validate_evaluation(data: dict, max_score: float, descriptor_numbers: set[int]) -> dict:
    try:
        jsonschema.validate(data, EVALUATION_SCHEMA)
    except jsonschema.ValidationError as e:
        raise SchemaError(f"schema: {e.message}") from e
    if data["score"] > max_score + 1e-9:
        raise SchemaError(f"score {data['score']} > max_score {max_score}")
    if abs(data["max_score"] - max_score) > 1e-9:
        raise SchemaError("max_score mismatch")
    nums = {d["number"] for d in data["descriptors"]}
    if descriptor_numbers and not nums <= descriptor_numbers:
        raise SchemaError(f"unknown descriptors {nums - descriptor_numbers}")
    if descriptor_numbers and nums != descriptor_numbers:
        raise SchemaError("not all descriptors judged")
    return data
