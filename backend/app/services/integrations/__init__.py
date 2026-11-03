"""Adapters for external systems (school e-journals). Implement GradebookAdapter and register it in ADAPTERS."""
from typing import Protocol


class GradebookAdapter(Protocol):
    name: str

    def push_results(self, assessment: dict, results: list[dict]) -> dict: ...

    def sync_students(self, class_external_id: str) -> list[dict]: ...


class NoopGradebook:
    name = "noop"

    def push_results(self, assessment: dict, results: list[dict]) -> dict:
        return {"pushed": 0, "adapter": self.name}

    def sync_students(self, class_external_id: str) -> list[dict]:
        return []


ADAPTERS: dict[str, GradebookAdapter] = {"noop": NoopGradebook()}
