"""Normalize selectable-model, CTA, and future guide entry points."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Literal, cast


TriggerSource = Literal["model", "cta", "prompt", "link", "api", "onboarding"]
_TRIGGER_SOURCES = {"model", "cta", "prompt", "link", "api", "onboarding"}
_SUPPORTED_INTENTS = {"getting_started"}
_SUPPORTED_VERSIONS = {1}
_GETTING_STARTED_PHRASES = {
    "start the getting started tour",
    "start getting started",
    "getting started",
}


class GuideTriggerError(ValueError):
    """Raised when a guide trigger does not match the supported contract."""


@dataclass(frozen=True, slots=True)
class GuideTrigger:
    """A versioned request to enter a known guide intent."""

    intent: str
    source: TriggerSource
    version: int = 1
    parameters: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.intent not in _SUPPORTED_INTENTS:
            raise GuideTriggerError(f"unsupported guide intent: {self.intent}")
        if self.source not in _TRIGGER_SOURCES:
            raise GuideTriggerError(f"unsupported trigger source: {self.source}")
        if self.version not in _SUPPORTED_VERSIONS:
            raise GuideTriggerError(f"unsupported trigger version: {self.version}")
        if not isinstance(self.parameters, Mapping):
            raise GuideTriggerError("trigger parameters must be a mapping")

        parameters = MappingProxyType(deepcopy(dict(self.parameters)))
        object.__setattr__(self, "parameters", parameters)


def normalize_trigger(
    value: str | Mapping[str, Any] | GuideTrigger,
    *,
    default_source: TriggerSource = "model",
) -> GuideTrigger | None:
    """Return a validated trigger, or ``None`` for unrelated user text."""

    if isinstance(value, GuideTrigger):
        return value

    if isinstance(value, str):
        normalized_text = " ".join(value.strip().casefold().split()).rstrip(".!?")
        if normalized_text not in _GETTING_STARTED_PHRASES:
            return None
        return GuideTrigger(intent="getting_started", source=default_source)

    if not isinstance(value, Mapping):
        raise GuideTriggerError("trigger must be text, a mapping, or GuideTrigger")

    try:
        intent = value["intent"]
        source = value["source"]
    except KeyError as error:
        raise GuideTriggerError(f"trigger is missing '{error.args[0]}'") from error

    version = value.get("version", 1)
    parameters = value.get("parameters", {})

    if not isinstance(intent, str):
        raise GuideTriggerError("trigger intent must be text")
    if not isinstance(source, str):
        raise GuideTriggerError("trigger source must be text")
    if not isinstance(version, int) or isinstance(version, bool):
        raise GuideTriggerError("trigger version must be an integer")

    return GuideTrigger(
        intent=intent,
        source=cast(TriggerSource, source),
        version=version,
        parameters=parameters,
    )

