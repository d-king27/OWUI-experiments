"""
title: Open WebUI Guide
author: Open WebUI How-To Agent project
version: 0.1.0
required_open_webui_version: 0.11.0
description: Grounded onboarding guide backed by source-controlled content.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
import json
import os
from pathlib import Path
import re
from typing import Any

from howto_agent import (
    AgentConfigurationError,
    AgentReply,
    GuideContext,
    GuideIntent,
    HowToAgent,
    UiDirective,
    route_guide_input,
)

from openwebui.functions.catalog import visible_chat_choices


CatalogLoader = Callable[..., Awaitable[tuple[Any, ...]]]
_TRANSPORT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_GENERIC_PIPE_ERROR = (
    "The Open WebUI Guide is not configured correctly. Ask an administrator "
    "to verify its mounted process and knowledge files."
)
_MISSING_MESSAGE_ERROR = (
    "I couldn't find a user message to answer. Ask me what Open WebUI is, how "
    "to use it, what a model is, which chat choices you can access, or for a "
    "workable example."
)


class Pipe:
    """Selectable Open WebUI Pipe backed by the deterministic How-To Agent."""

    def __init__(
        self,
        *,
        agent: HowToAgent | None = None,
        catalog_loader: CatalogLoader = visible_chat_choices,
        content_root: str | Path | None = None,
    ) -> None:
        self.name = "Open WebUI Guide"
        self._catalog_loader = catalog_loader
        self._agent = agent
        if self._agent is None:
            try:
                self._agent = self._build_agent(content_root)
            except Exception:
                self._agent = None

    async def pipe(
        self,
        body: dict[str, Any],
        __user__: dict[str, Any] | None = None,
        __request__: Any = None,
        __metadata__: dict[str, Any] | None = None,
    ) -> str:
        """Translate one Open WebUI request into a grounded guide response."""

        prompt = extract_user_prompt(body, metadata=__metadata__)
        if prompt is None:
            return _MISSING_MESSAGE_ERROR
        if self._agent is None:
            return _GENERIC_PIPE_ERROR

        context = GuideContext()
        if route_guide_input(prompt).intent == GuideIntent.LIST_CHAT_CHOICES:
            context = await self._load_catalog_context(__request__, __user__)

        try:
            reply = self._agent.respond(prompt, context=context)
            return render_reply_with_directives(reply)
        except (AgentConfigurationError, ValueError):
            return _GENERIC_PIPE_ERROR

    async def _load_catalog_context(
        self,
        request: Any,
        user_payload: Mapping[str, Any] | None,
    ) -> GuideContext:
        if user_payload is None:
            return GuideContext(
                catalog_available=False,
                catalog_error="catalog context unavailable",
            )
        try:
            choices = await self._catalog_loader(request, user_payload)
            return GuideContext(visible_chat_choices=tuple(choices))
        except Exception:
            return GuideContext(
                catalog_available=False,
                catalog_error="catalog unavailable",
            )

    @staticmethod
    def _build_agent(content_root: str | Path | None) -> HowToAgent:
        root = Path(
            content_root
            or os.environ.get("HOWTO_CONTENT_ROOT", "/opt/howto")
        )
        return HowToAgent.from_content_files(
            process_path=root / "agent" / "process_definition.example.yaml",
            manual_path=root / "knowledge" / "open-webui-instruction-manual.md",
            ui_map_path=root / "knowledge" / "ui-map.yaml",
            recipe_directory=root / "knowledge" / "recipes",
        )


def extract_user_prompt(
    body: Any,
    *,
    metadata: Mapping[str, Any] | None = None,
) -> str | None:
    """Prefer Open WebUI's unwrapped prompt, then scan messages defensively."""

    if isinstance(metadata, Mapping):
        user_prompt = metadata.get("user_prompt")
        if isinstance(user_prompt, str) and user_prompt.strip():
            return user_prompt.strip()

    if not isinstance(body, Mapping):
        return None
    messages = body.get("messages")
    if not isinstance(messages, list):
        return None

    for message in reversed(messages):
        if not isinstance(message, Mapping) or message.get("role") != "user":
            continue
        text = _extract_text_content(message.get("content"))
        if text:
            return text
    return None


def render_reply_with_directives(reply: AgentReply) -> str:
    """Serialize validated directives in the Guide Bridge transport format."""

    blocks = [reply.markdown.strip()]
    for directive in reply.directives:
        payload = _directive_payload(directive)
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        blocks.append(f"```owui-action\n{serialized}\n```")
    return "\n\n".join(blocks)


def _directive_payload(directive: UiDirective) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "version": 1,
        "kind": directive.kind,
        "requires_confirmation": directive.requires_confirmation,
    }
    if directive.target is not None:
        _require_transport_id(directive.target)
        payload["target"] = directive.target
    if directive.recipe is not None:
        _require_transport_id(directive.recipe)
        payload["recipe"] = directive.recipe
    return payload


def _require_transport_id(value: str) -> None:
    if not _TRANSPORT_ID_PATTERN.fullmatch(value):
        raise ValueError(f"unsafe directive transport ID: {value}")


def _extract_text_content(content: Any) -> str | None:
    if isinstance(content, str):
        stripped = content.strip()
        return stripped or None
    if not isinstance(content, list):
        return None

    parts = []
    for block in content:
        if not isinstance(block, Mapping) or block.get("type") != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    combined = "\n".join(parts)
    return combined or None
