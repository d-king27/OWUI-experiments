"""Small process-navigation API for the experimental How-To Agent."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import html
from pathlib import Path
import re
from typing import Any

import yaml

from .context import ChatChoice, GuideContext
from .manual import InstructionManual
from .recipes import RecipeRegistry, UiMap
from .replies import AgentReply, UiDirective, validate_directive
from .router import GuideIntent, IntentMatch, route_guide_input
from .triggers import GuideTrigger


class ProcessDefinitionError(ValueError):
    """Raised when a process definition does not match the minimal schema."""


class AgentConfigurationError(RuntimeError):
    """Raised when guide behaviour is requested without guide content."""


class HowToAgent:
    """Read and navigate a small, ordered process definition."""

    def __init__(
        self,
        process_definition: Mapping[str, Any],
        *,
        manual: InstructionManual | None = None,
        ui_map: UiMap | None = None,
        recipes: RecipeRegistry | None = None,
    ) -> None:
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
        self._manual = manual
        self._ui_map = ui_map
        self._recipes = recipes

        configured_values = (manual, ui_map, recipes)
        if any(value is not None for value in configured_values) and not all(
            value is not None for value in configured_values
        ):
            raise AgentConfigurationError(
                "manual, UI map, and recipe registry must be configured together"
            )
        if manual is not None and ui_map is not None and recipes is not None:
            manual.validate_references(
                allowed_targets=ui_map.target_ids,
                allowed_recipes=recipes.recipe_ids,
            )

    @classmethod
    def from_yaml(cls, path: str | Path) -> HowToAgent:
        """Load a process definition from a UTF-8 YAML file."""

        return cls(cls._load_process_definition(path))

    @classmethod
    def from_content_files(
        cls,
        *,
        process_path: str | Path,
        manual_path: str | Path,
        ui_map_path: str | Path,
        recipe_directory: str | Path,
    ) -> HowToAgent:
        """Load the process and all grounded guide content from source files."""

        process = cls._load_process_definition(process_path)
        manual = InstructionManual.from_markdown(manual_path)
        ui_map = UiMap.from_yaml(ui_map_path)
        recipes = RecipeRegistry.from_directory(recipe_directory, ui_map=ui_map)
        return cls(process, manual=manual, ui_map=ui_map, recipes=recipes)

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

    def respond(
        self,
        message: str | Mapping[str, Any] | GuideTrigger,
        *,
        context: GuideContext | None = None,
    ) -> AgentReply:
        """Return a deterministic response grounded in configured guide content."""

        manual, ui_map, recipes = self._require_guide_content()
        match = route_guide_input(message)
        guide_context = context or GuideContext()

        if match.intent == GuideIntent.GETTING_STARTED:
            reply = self._getting_started_reply(manual)
        elif match.intent == GuideIntent.WHAT_IS_OPEN_WEBUI:
            reply = self._section_reply(manual, "what-is-open-webui")
        elif match.intent == GuideIntent.HOW_TO_USE:
            reply = self._section_reply(
                manual,
                "how-do-i-use-open-webui",
                directive=UiDirective(kind="highlight", target="model-picker"),
            )
        elif match.intent == GuideIntent.WHAT_IS_A_MODEL:
            reply = self._section_reply(manual, "what-is-a-model")
        elif match.intent == GuideIntent.LIST_CHAT_CHOICES:
            reply = self._chat_choices_reply(guide_context)
        elif match.intent == GuideIntent.WORKABLE_EXAMPLE:
            reply = self._section_reply(
                manual,
                "workable-example-hello-world-connectivity",
                directive=UiDirective(
                    kind="run_recipe",
                    recipe="hello-world-demo",
                    requires_confirmation=True,
                ),
            )
        elif match.intent == GuideIntent.HIGHLIGHT_TARGET:
            reply = self._highlight_reply(match, ui_map)
        else:
            reply = self._unknown_reply()

        for directive in reply.directives:
            validate_directive(
                directive,
                allowed_targets=ui_map.target_ids,
                allowed_recipes=recipes.recipe_ids,
            )
        return reply

    @staticmethod
    def _require_text(container: Mapping[str, Any], key: str, location: str) -> str:
        value = container.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ProcessDefinitionError(f"{location} requires a non-empty '{key}'")
        return value

    @staticmethod
    def _load_process_definition(path: str | Path) -> Mapping[str, Any]:
        process_path = Path(path)
        try:
            data = yaml.safe_load(process_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise ProcessDefinitionError(
                f"could not load process definition from {process_path}"
            ) from error
        if not isinstance(data, Mapping):
            raise ProcessDefinitionError("process definition must be a mapping")
        return data

    def _require_guide_content(
        self,
    ) -> tuple[InstructionManual, UiMap, RecipeRegistry]:
        if self._manual is None or self._ui_map is None or self._recipes is None:
            raise AgentConfigurationError(
                "guide responses require manual, UI map, and recipe content"
            )
        return self._manual, self._ui_map, self._recipes

    @staticmethod
    def _section_reply(
        manual: InstructionManual,
        section_id: str,
        *,
        directive: UiDirective | None = None,
    ) -> AgentReply:
        section = manual.get_section(section_id)
        if section is None:
            raise AgentConfigurationError(
                f"required manual section is missing: {section_id}"
            )
        directives = (directive,) if directive is not None else ()
        return AgentReply(markdown=section.markdown, directives=directives)

    @staticmethod
    def _getting_started_reply(manual: InstructionManual) -> AgentReply:
        open_webui = manual.get_section("what-is-open-webui")
        model = manual.get_section("what-is-a-model")
        if open_webui is None or model is None:
            raise AgentConfigurationError(
                "getting started requires Open WebUI and model manual sections"
            )

        markdown = (
            "## Step 1: Open WebUI and models\n\n"
            f"{HowToAgent._first_paragraph(open_webui.markdown)}\n\n"
            f"{HowToAgent._first_paragraph(model.markdown)}\n\n"
            "Next, use **Show me** to locate the model selector, or ask me "
            "to explain the available chat choices."
        )
        return AgentReply(
            markdown=markdown,
            directives=(UiDirective(kind="highlight", target="model-picker"),),
        )

    @staticmethod
    def _chat_choices_reply(context: GuideContext) -> AgentReply:
        directive = UiDirective(kind="highlight", target="model-picker")
        if not context.catalog_available:
            return AgentReply(
                markdown=(
                    "I can't verify your current chat choices from the runtime "
                    "catalog. Open the model selector to inspect the choices "
                    "available to your account."
                ),
                directives=(directive,),
            )

        if not context.visible_chat_choices:
            return AgentReply(
                markdown=(
                    "The runtime catalog did not return any chat choices for "
                    "your account. Open the model selector to confirm the current "
                    "configuration."
                ),
                directives=(directive,),
            )

        choice_lines = "\n".join(
            HowToAgent._format_chat_choice(choice)
            for choice in context.visible_chat_choices
        )
        return AgentReply(
            markdown=(
                "These chat choices are currently visible to your account:\n\n"
                f"{choice_lines}\n\n"
                "I only classify an entry when the runtime supplies enough "
                "information; otherwise I label it as a chat choice."
            ),
            directives=(directive,),
        )

    @staticmethod
    def _format_chat_choice(choice: ChatChoice) -> str:
        labels = {
            "model": "model",
            "agent": "agent",
            "custom_model": "custom model",
            "unknown": "chat choice",
        }
        name = HowToAgent._escape_markdown(choice.name)
        identifier = ""
        if choice.id != choice.name:
            safe_id = html.escape(choice.id).replace("`", "&#96;")
            identifier = f" (`{safe_id}`)"
        return f"- **{name}**{identifier} — {labels[choice.kind]}"

    @staticmethod
    def _highlight_reply(match: IntentMatch, ui_map: UiMap) -> AgentReply:
        if match.target is None:
            return HowToAgent._unknown_reply()
        target = ui_map.get_target(match.target)
        if target is None:
            raise AgentConfigurationError(
                f"routed UI target is missing from the UI map: {match.target}"
            )
        return AgentReply(
            markdown=f"**{target['description']}** Choose **Show me** to highlight it.",
            directives=(UiDirective(kind="highlight", target=match.target),),
        )

    @staticmethod
    def _unknown_reply() -> AgentReply:
        return AgentReply(
            markdown=(
                "The current instruction manual does not contain enough "
                "information to answer that reliably. I can explain:\n\n"
                "- what Open WebUI is;\n"
                "- how to use the chat interface;\n"
                "- what a model is;\n"
                "- which chat choices are available to you; or\n"
                "- the Hello World example."
            )
        )

    @staticmethod
    def _first_paragraph(markdown: str) -> str:
        paragraphs = [value.strip() for value in markdown.split("\n\n")]
        return next((value for value in paragraphs if value), "")

    @staticmethod
    def _escape_markdown(value: str) -> str:
        escaped = html.escape(value)
        return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", escaped)
