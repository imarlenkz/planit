"""Cloud LLM providers (OpenAI, Anthropic) with forced structured JSON output."""
import json

import httpx

from app.core.config import settings
from app.services.ai.base import SYSTEM_PROMPT, EvalRequest, build_eval_prompt
from app.services.ai.schema import EVALUATION_SCHEMA


class OpenAIProvider:
    name = "openai"

    def __init__(self):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.model = settings.OPENAI_MODEL

    def _call(self, system: str, prompt: str, schema: dict, name: str) -> tuple[dict, str]:
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "response_format": {"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": False}},
        }
        r = httpx.post(f"{settings.OPENAI_BASE_URL}/chat/completions", json=body, timeout=settings.AI_TIMEOUT_SEC,
                       headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"})
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"]
        return json.loads(raw), raw

    def evaluate(self, req: EvalRequest) -> tuple[dict, str]:
        return self._call(SYSTEM_PROMPT, build_eval_prompt(req), EVALUATION_SCHEMA, "evaluation")

    def complete_json(self, system: str, prompt: str, schema: dict) -> dict:
        return self._call(system, prompt, schema, "output")[0]


class AnthropicProvider:
    """Claude via the Messages API; JSON is forced through a single tool with input_schema."""

    name = "anthropic"

    def __init__(self):
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.model = settings.ANTHROPIC_MODEL

    def _call(self, system: str, prompt: str, schema: dict, tool: str) -> tuple[dict, str]:
        body = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
            "tools": [{"name": tool, "description": "Return the structured result", "input_schema": schema}],
            "tool_choice": {"type": "tool", "name": tool},
        }
        r = httpx.post("https://api.anthropic.com/v1/messages", json=body, timeout=settings.AI_TIMEOUT_SEC,
                       headers={"x-api-key": settings.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"})
        r.raise_for_status()
        data = r.json()
        for block in data.get("content", []):
            if block.get("type") == "tool_use":
                return block["input"], json.dumps(block["input"], ensure_ascii=False)
        raise ValueError("no tool_use block in response")

    def evaluate(self, req: EvalRequest) -> tuple[dict, str]:
        return self._call(SYSTEM_PROMPT, build_eval_prompt(req), EVALUATION_SCHEMA, "submit_evaluation")

    def complete_json(self, system: str, prompt: str, schema: dict) -> dict:
        return self._call(system, prompt, schema, "submit")[0]
