"""Deterministic intent routing for the Open WebUI starter guide."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
import re
from typing import Any

from .triggers import GuideTrigger, normalize_trigger


class GuideIntent(str, Enum):
    """Guide intents supported by the proof-of-concept content."""

    GETTING_STARTED = "getting_started"
    WHAT_IS_OPEN_WEBUI = "what_is_open_webui"
    HOW_TO_USE = "how_to_use"
    WHAT_IS_A_MODEL = "what_is_a_model"
    LIST_CHAT_CHOICES = "list_chat_choices"
    WORKABLE_EXAMPLE = "workable_example"
    HIGHLIGHT_TARGET = "highlight_target"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class IntentMatch:
    """The deterministic route selected for one guide input."""

    intent: GuideIntent
    target: str | None = None


_CATALOG_PATTERNS = (
    re.compile(
        r"\b(?:what|which|show|list)\b.*"
        r"\b(?:models?|agents?|chat choices?)\b.*"
        r"\b(?:access|available|use|choose)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:available|accessible)\b.*\b(?:models?|agents?|chat choices?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bwhat (?:can|do) i (?:access|have access to)\b", re.IGNORECASE),
)

_OPEN_WEBUI_PATTERN = re.compile(
    r"\bwhat(?:'s| is)\s+(?:open\s+webui|open\s+web\s+ui|owui)\b",
    re.IGNORECASE,
)
_HOW_TO_USE_PATTERN = re.compile(
    r"\bhow\s+(?:do|can|should)\s+i\s+use\s+"
    r"(?:open\s+webui|open\s+web\s+ui|owui|it)\b",
    re.IGNORECASE,
)
_MODEL_PATTERN = re.compile(
    r"\bwhat(?:'s| is)\s+(?:an?\s+)?(?:ai\s+)?model\b",
    re.IGNORECASE,
)
_EXAMPLE_PATTERN = re.compile(
    r"\b(?:workable|working|practical)\s+example\b|"
    r"\b(?:show|give|run|try)\b.*\b(?:example|demo|demonstration)\b|"
    r"\bhello[- ]world\b.*\b(?:example|demo|test)\b",
    re.IGNORECASE,
)
_HIGHLIGHT_REQUEST_PATTERN = re.compile(
    r"\b(?:show me|highlight|point (?:out|to)|where (?:is|are|do i|will|does))\b",
    re.IGNORECASE,
)

_TARGET_PATTERNS = (
    (
        "getting-started-cta",
        re.compile(r"\b(?:getting started|guide)\s+(?:button|cta)\b", re.IGNORECASE),
    ),
    (
        "model-picker",
        re.compile(
            r"\b(?:model|agent|chat choice)\b.*\b(?:picker|selector|select|choose)\b|"
            r"\b(?:picker|selector|select|choose)\b.*\b(?:model|agent)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "message-composer",
        re.compile(
            r"\b(?:message|prompt|request|chat)\b.*\b(?:box|input|composer|type|write)\b|"
            r"\b(?:box|input|composer|type|write)\b.*\b(?:message|prompt|request)\b|"
            r"\bwhere\s+do\s+i\s+(?:type|write)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "send-button",
        re.compile(r"\b(?:send|submit)\b.*\b(?:button|message|prompt)\b", re.IGNORECASE),
    ),
    (
        "assistant-message",
        re.compile(
            r"\b(?:answer|response|result|assistant message)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "new-chat",
        re.compile(r"\bnew\s+chat\b", re.IGNORECASE),
    ),
)


def route_guide_input(
    value: str | Mapping[str, Any] | GuideTrigger,
) -> IntentMatch:
    """Route supported guide input without invoking a language model."""

    trigger = normalize_trigger(value)
    if trigger is not None:
        return IntentMatch(GuideIntent.GETTING_STARTED)

    if not isinstance(value, str):
        return IntentMatch(GuideIntent.UNKNOWN)

    message = " ".join(value.strip().split())
    if not message:
        return IntentMatch(GuideIntent.UNKNOWN)

    if any(pattern.search(message) for pattern in _CATALOG_PATTERNS):
        return IntentMatch(GuideIntent.LIST_CHAT_CHOICES)
    if _OPEN_WEBUI_PATTERN.search(message):
        return IntentMatch(GuideIntent.WHAT_IS_OPEN_WEBUI)
    if _HOW_TO_USE_PATTERN.search(message):
        return IntentMatch(GuideIntent.HOW_TO_USE)
    if _MODEL_PATTERN.search(message):
        return IntentMatch(GuideIntent.WHAT_IS_A_MODEL)
    if _EXAMPLE_PATTERN.search(message):
        return IntentMatch(GuideIntent.WORKABLE_EXAMPLE)
    if _HIGHLIGHT_REQUEST_PATTERN.search(message):
        for target_id, pattern in _TARGET_PATTERNS:
            if pattern.search(message):
                return IntentMatch(GuideIntent.HIGHLIGHT_TARGET, target=target_id)

    return IntentMatch(GuideIntent.UNKNOWN)
