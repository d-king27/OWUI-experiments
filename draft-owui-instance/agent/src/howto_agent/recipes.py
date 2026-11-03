"""Validate semantic UI maps and allow-listed browser demonstration recipes."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

import yaml


SUPPORTED_RECIPE_ACTIONS = frozenset(
    {
        "click",
        "wait_for_target",
        "choose_option",
        "type_fixed_text",
        "wait_for_text",
        "highlight",
    }
)
SUPPORTED_PRECONDITION_CHECKS = frozenset(
    {"target_available", "option_available", "selected_option"}
)
_MUTATING_ACTIONS = {"click", "choose_option", "type_fixed_text"}
_ACTION_CAPABILITIES = {
    "click": "click",
    "choose_option": "choose_option",
    "type_fixed_text": "type",
    "wait_for_text": "wait_for_text",
    "highlight": "highlight",
}


class ContentDefinitionError(ValueError):
    """Raised when a UI map or browser recipe is unsafe or malformed."""


class UiMap:
    """Canonical registry of semantic targets and allowed browser origins."""

    def __init__(self, definition: Mapping[str, Any]) -> None:
        if not isinstance(definition, Mapping):
            raise ContentDefinitionError("UI map must be a mapping")

        normalized = deepcopy(dict(definition))
        if normalized.get("schema_version") != 1:
            raise ContentDefinitionError("UI map requires schema_version 1")
        self._require_text(normalized, "id", "UI map")
        self._require_text(normalized, "status", "UI map")

        origins = normalized.get("allowed_origins")
        if not isinstance(origins, list) or not origins:
            raise ContentDefinitionError("UI map requires allowed_origins")
        for origin in origins:
            self._validate_origin(origin, "UI map")

        targets = normalized.get("targets")
        if not isinstance(targets, Mapping) or not targets:
            raise ContentDefinitionError("UI map requires targets")

        for target_id, raw_target in targets.items():
            if not isinstance(target_id, str) or not target_id.strip():
                raise ContentDefinitionError("UI target IDs must be non-empty text")
            if not isinstance(raw_target, Mapping):
                raise ContentDefinitionError(f"UI target {target_id} must be a mapping")
            self._require_text(raw_target, "description", f"UI target {target_id}")

            capabilities = raw_target.get("capabilities")
            if not isinstance(capabilities, list) or not capabilities:
                raise ContentDefinitionError(
                    f"UI target {target_id} requires capabilities"
                )
            if any(not isinstance(value, str) or not value for value in capabilities):
                raise ContentDefinitionError(
                    f"UI target {target_id} capabilities must be text"
                )

            locators = raw_target.get("locators")
            if not isinstance(locators, list) or not locators:
                raise ContentDefinitionError(
                    f"UI target {target_id} requires locator candidates"
                )
            for index, locator in enumerate(locators):
                if not isinstance(locator, Mapping):
                    raise ContentDefinitionError(
                        f"UI target {target_id} locator {index + 1} must be a mapping"
                    )
                self._require_text(
                    locator,
                    "kind",
                    f"UI target {target_id} locator {index + 1}",
                )

        self._definition = normalized
        self._target_ids = frozenset(targets)
        self._allowed_origins = frozenset(origins)

    @classmethod
    def from_yaml(cls, path: str | Path) -> UiMap:
        definition = _load_yaml_mapping(path, "UI map")
        return cls(definition)

    @property
    def target_ids(self) -> frozenset[str]:
        return self._target_ids

    @property
    def allowed_origins(self) -> frozenset[str]:
        return self._allowed_origins

    def get_target(self, target_id: str) -> dict[str, Any] | None:
        target = self._definition["targets"].get(target_id)
        return deepcopy(target) if target is not None else None

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self._definition)

    @staticmethod
    def _require_text(container: Mapping[str, Any], key: str, location: str) -> str:
        value = container.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ContentDefinitionError(f"{location} requires a non-empty '{key}'")
        return value

    @staticmethod
    def _validate_origin(origin: Any, location: str) -> None:
        if not isinstance(origin, str):
            raise ContentDefinitionError(f"{location} origins must be text")
        parsed = urlsplit(origin)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ContentDefinitionError(f"{location} has invalid origin: {origin}")
        if parsed.path or parsed.query or parsed.fragment:
            raise ContentDefinitionError(
                f"{location} origin must not contain a path, query, or fragment: {origin}"
            )


@dataclass(frozen=True, slots=True)
class RecipeStep:
    """One validated, allow-listed browser recipe step."""

    id: str
    action: str
    target: str
    definition: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "definition",
            MappingProxyType(deepcopy(dict(self.definition))),
        )

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(dict(self.definition))


class RecipeDefinition:
    """Validated recipe metadata and ordered steps."""

    def __init__(
        self,
        *,
        definition: Mapping[str, Any],
        steps: tuple[RecipeStep, ...],
    ) -> None:
        self._definition = deepcopy(dict(definition))
        self._steps = steps

    @property
    def id(self) -> str:
        return self._definition["id"]

    @property
    def title(self) -> str:
        return self._definition["title"]

    @property
    def requires_confirmation(self) -> bool:
        return self._definition["requires_confirmation"]

    @property
    def steps(self) -> tuple[RecipeStep, ...]:
        return self._steps

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self._definition)


class RecipeRegistry:
    """Load and address recipes validated against one semantic UI map."""

    def __init__(self, recipes: tuple[RecipeDefinition, ...]) -> None:
        indexes: dict[str, RecipeDefinition] = {}
        for recipe in recipes:
            if recipe.id in indexes:
                raise ContentDefinitionError(f"duplicate recipe id: {recipe.id}")
            indexes[recipe.id] = recipe
        if not indexes:
            raise ContentDefinitionError("recipe registry must not be empty")
        self._recipes = recipes
        self._indexes = indexes

    @classmethod
    def from_directory(
        cls,
        directory: str | Path,
        *,
        ui_map: UiMap,
    ) -> RecipeRegistry:
        recipe_directory = Path(directory)
        try:
            paths = sorted(recipe_directory.glob("*.yaml"))
        except OSError as error:
            raise ContentDefinitionError(
                f"could not inspect recipe directory {recipe_directory}"
            ) from error
        if not paths:
            raise ContentDefinitionError(
                f"recipe directory contains no YAML recipes: {recipe_directory}"
            )

        recipes = tuple(
            cls._validate_recipe(
                _load_yaml_mapping(path, f"recipe {path.name}"),
                ui_map=ui_map,
                location=f"recipe {path.name}",
            )
            for path in paths
        )
        return cls(recipes)

    @property
    def recipe_ids(self) -> frozenset[str]:
        return frozenset(self._indexes)

    @property
    def recipes(self) -> tuple[RecipeDefinition, ...]:
        return self._recipes

    def get(self, recipe_id: str) -> RecipeDefinition | None:
        return self._indexes.get(recipe_id)

    @staticmethod
    def _validate_recipe(
        definition: Mapping[str, Any],
        *,
        ui_map: UiMap,
        location: str,
    ) -> RecipeDefinition:
        normalized = deepcopy(dict(definition))
        if normalized.get("schema_version") != 1:
            raise ContentDefinitionError(f"{location} requires schema_version 1")
        UiMap._require_text(normalized, "id", location)
        UiMap._require_text(normalized, "title", location)
        UiMap._require_text(normalized, "description", location)

        requires_confirmation = normalized.get("requires_confirmation")
        if not isinstance(requires_confirmation, bool):
            raise ContentDefinitionError(
                f"{location} requires a boolean requires_confirmation"
            )
        confirmation = normalized.get("confirmation")
        if requires_confirmation:
            if not isinstance(confirmation, Mapping):
                raise ContentDefinitionError(
                    f"{location} requires confirmation copy"
                )
            for key in ("title", "body", "confirm_label", "cancel_label"):
                UiMap._require_text(confirmation, key, f"{location} confirmation")

        origins = normalized.get("allowed_origins")
        if not isinstance(origins, list) or not origins:
            raise ContentDefinitionError(f"{location} requires allowed_origins")
        for origin in origins:
            UiMap._validate_origin(origin, location)
            if origin not in ui_map.allowed_origins:
                raise ContentDefinitionError(
                    f"{location} uses origin absent from UI map: {origin}"
                )

        RecipeRegistry._validate_limits(normalized.get("limits"), location=location)

        trigger = normalized.get("trigger")
        if trigger is not None:
            if not isinstance(trigger, Mapping):
                raise ContentDefinitionError(f"{location} trigger must be a mapping")
            if trigger.get("intent") != "getting_started":
                raise ContentDefinitionError(
                    f"{location} trigger has unsupported intent"
                )
            if trigger.get("source") not in {
                "model",
                "cta",
                "prompt",
                "link",
                "api",
                "onboarding",
            }:
                raise ContentDefinitionError(
                    f"{location} trigger has unsupported source"
                )
            if trigger.get("version", 1) != 1:
                raise ContentDefinitionError(
                    f"{location} trigger has unsupported version"
                )

        RecipeRegistry._validate_preconditions(
            normalized.get("preconditions", []),
            ui_map=ui_map,
            location=location,
        )

        raw_steps = normalized.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise ContentDefinitionError(f"{location} requires steps")

        steps = []
        seen_step_ids: set[str] = set()
        contains_mutation = False
        for index, raw_step in enumerate(raw_steps):
            step_location = f"{location} step {index + 1}"
            if not isinstance(raw_step, Mapping):
                raise ContentDefinitionError(f"{step_location} must be a mapping")
            step = deepcopy(dict(raw_step))
            step_id = UiMap._require_text(step, "id", step_location)
            action = UiMap._require_text(step, "action", step_location)
            target = UiMap._require_text(step, "target", step_location)

            if step_id in seen_step_ids:
                raise ContentDefinitionError(
                    f"{location} has duplicate step id: {step_id}"
                )
            if action not in SUPPORTED_RECIPE_ACTIONS:
                raise ContentDefinitionError(
                    f"{step_location} uses unsupported action: {action}"
                )
            RecipeRegistry._validate_target_action(
                target,
                action,
                ui_map=ui_map,
                location=step_location,
            )
            RecipeRegistry._validate_step_values(step, location=step_location)

            if action in _MUTATING_ACTIONS:
                contains_mutation = True
            seen_step_ids.add(step_id)
            steps.append(
                RecipeStep(
                    id=step_id,
                    action=action,
                    target=target,
                    definition=step,
                )
            )

        if contains_mutation and not requires_confirmation:
            raise ContentDefinitionError(
                f"{location} mutates the UI and requires confirmation"
            )

        for handler_name in ("on_failure", "on_cancel"):
            handler = normalized.get(handler_name, {})
            if not isinstance(handler, Mapping):
                raise ContentDefinitionError(
                    f"{location} {handler_name} must be a mapping"
                )
            handler_action = handler.get("action")
            if handler_action is not None and handler_action != "stop":
                raise ContentDefinitionError(
                    f"{location} {handler_name} only supports action: stop"
                )
            restore = handler.get("restore_option")
            if restore is not None:
                if not isinstance(restore, Mapping):
                    raise ContentDefinitionError(
                        f"{location} {handler_name} restore_option must be a mapping"
                    )
                restore_target = UiMap._require_text(
                    restore,
                    "target",
                    f"{location} {handler_name} restore_option",
                )
                RecipeRegistry._validate_target_action(
                    restore_target,
                    "choose_option",
                    ui_map=ui_map,
                    location=f"{location} {handler_name} restore_option",
                )
                UiMap._require_text(
                    restore,
                    "value",
                    f"{location} {handler_name} restore_option",
                )

        return RecipeDefinition(definition=normalized, steps=tuple(steps))

    @staticmethod
    def _validate_limits(limits: Any, *, location: str) -> None:
        if not isinstance(limits, Mapping):
            raise ContentDefinitionError(f"{location} requires limits")
        for key in ("total_timeout_ms", "default_step_timeout_ms"):
            value = limits.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ContentDefinitionError(
                    f"{location} {key} must be a positive integer"
                )
        if limits["default_step_timeout_ms"] > limits["total_timeout_ms"]:
            raise ContentDefinitionError(
                f"{location} default step timeout exceeds total timeout"
            )
        if limits.get("cancel_key") != "Escape":
            raise ContentDefinitionError(
                f"{location} cancel_key must be Escape"
            )

    @staticmethod
    def _validate_preconditions(
        preconditions: Any,
        *,
        ui_map: UiMap,
        location: str,
    ) -> None:
        if not isinstance(preconditions, list):
            raise ContentDefinitionError(f"{location} preconditions must be a list")
        for index, raw_precondition in enumerate(preconditions):
            item_location = f"{location} precondition {index + 1}"
            if not isinstance(raw_precondition, Mapping):
                raise ContentDefinitionError(f"{item_location} must be a mapping")
            check = UiMap._require_text(raw_precondition, "check", item_location)
            target = UiMap._require_text(raw_precondition, "target", item_location)
            if check not in SUPPORTED_PRECONDITION_CHECKS:
                raise ContentDefinitionError(
                    f"{item_location} uses unsupported check: {check}"
                )
            if target not in ui_map.target_ids:
                raise ContentDefinitionError(
                    f"{item_location} references unknown target: {target}"
                )
            if check in {"option_available", "selected_option"}:
                UiMap._require_text(raw_precondition, "value", item_location)

    @staticmethod
    def _validate_target_action(
        target_id: str,
        action: str,
        *,
        ui_map: UiMap,
        location: str,
    ) -> None:
        target = ui_map.get_target(target_id)
        if target is None:
            raise ContentDefinitionError(
                f"{location} references unknown target: {target_id}"
            )
        capability = _ACTION_CAPABILITIES.get(action)
        if capability and capability not in target["capabilities"]:
            raise ContentDefinitionError(
                f"{location} target {target_id} does not allow {action}"
            )

    @staticmethod
    def _validate_step_values(step: Mapping[str, Any], *, location: str) -> None:
        action = step["action"]
        if action in {"choose_option", "type_fixed_text", "wait_for_text"}:
            UiMap._require_text(step, "value", location)

        timeout = step.get("timeout_ms")
        if timeout is not None and (
            not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0
        ):
            raise ContentDefinitionError(
                f"{location} timeout_ms must be a positive integer"
            )
        duration = step.get("duration_ms")
        if duration is not None and (
            not isinstance(duration, int) or isinstance(duration, bool) or duration <= 0
        ):
            raise ContentDefinitionError(
                f"{location} duration_ms must be a positive integer"
            )


def _load_yaml_mapping(path: str | Path, location: str) -> dict[str, Any]:
    content_path = Path(path)
    try:
        definition = yaml.safe_load(content_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ContentDefinitionError(f"could not load {location} from {content_path}") from error
    if not isinstance(definition, Mapping):
        raise ContentDefinitionError(f"{location} must be a mapping")
    return dict(definition)
