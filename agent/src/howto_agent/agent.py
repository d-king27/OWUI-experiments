"""Small process-navigation API for the experimental How-To Agent."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


class ProcessDefinitionError(ValueError):
    """Raised when a process definition does not match the minimal schema."""


class HowToAgent:
    """Read and navigate a small, ordered process definition."""

    def __init__(self, process_definition: Mapping[str, Any]) -> None:
        if not isinstance(process_definition, Mapping):
            raise ProcessDefinitionError("process definition must be a mapping")

        definition = deepcopy(dict(process_definition))
        self._require_text(definition, "id", "process")
        self._require_text(definition, "name", "process")
        self._require_text(definition, "description", "process")

        steps = definition.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ProcessDefinitionError("process steps must be a non-empty list")

        step_indexes: dict[str, int] = {}
        normalized_steps: list[dict[str, Any]] = []

        for index, raw_step in enumerate(steps):
            if not isinstance(raw_step, Mapping):
                raise ProcessDefinitionError(f"step {index + 1} must be a mapping")

            step = deepcopy(dict(raw_step))
            step_id = self._require_text(step, "id", f"step {index + 1}")
            self._require_text(step, "title", f"step {index + 1}")
            self._require_text(step, "description", f"step {index + 1}")

            if step_id in step_indexes:
                raise ProcessDefinitionError(f"duplicate step id: {step_id}")

            step_indexes[step_id] = index
            normalized_steps.append(step)

        definition["steps"] = normalized_steps
        self._process_definition = definition
        self._step_indexes = step_indexes

    @classmethod
    def from_yaml(cls, path: str | Path) -> HowToAgent:
        """Load a process definition from a UTF-8 YAML file."""

        process_path = Path(path)
        try:
            data = yaml.safe_load(process_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise ProcessDefinitionError(
                f"could not load process definition from {process_path}"
            ) from error

        if not isinstance(data, Mapping):
            raise ProcessDefinitionError("process definition must be a mapping")

        return cls(data)

    def get_process_overview(self) -> dict[str, Any]:
        """Return process metadata and the ordered list of step summaries."""

        steps = self._process_definition["steps"]
        return {
            "id": self._process_definition["id"],
            "name": self._process_definition["name"],
            "description": self._process_definition["description"],
            "step_count": len(steps),
            "steps": [
                {"id": step["id"], "title": step["title"]} for step in steps
            ],
        }

    def get_step(self, step_id: str) -> dict[str, Any] | None:
        """Return a step by ID, or ``None`` when it is unknown."""

        index = self._step_indexes.get(step_id)
        if index is None:
            return None
        return deepcopy(self._process_definition["steps"][index])

    def get_next_step(self, current_step_id: str) -> dict[str, Any] | None:
        """Return the following step, or ``None`` for unknown/final steps."""

        index = self._step_indexes.get(current_step_id)
        if index is None or index + 1 >= len(self._process_definition["steps"]):
            return None
        return deepcopy(self._process_definition["steps"][index + 1])

    @staticmethod
    def _require_text(container: Mapping[str, Any], key: str, location: str) -> str:
        value = container.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ProcessDefinitionError(f"{location} requires a non-empty '{key}'")
        return value
