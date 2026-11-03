"""Runtime context supplied to the framework-independent guide domain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ChatChoiceKind = Literal["model", "agent", "custom_model", "unknown"]
_CHAT_CHOICE_KINDS = {"model", "agent", "custom_model", "unknown"}


@dataclass(frozen=True, slots=True)
class ChatChoice:
    """One chat choice visible to the current Open WebUI user."""

    id: str
    name: str
    kind: ChatChoiceKind = "unknown"

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("chat choice requires a non-empty id")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("chat choice requires a non-empty name")
        if self.kind not in _CHAT_CHOICE_KINDS:
            raise ValueError(f"unsupported chat choice kind: {self.kind}")


@dataclass(frozen=True, slots=True)
class GuideContext:
    """User-specific facts the Open WebUI adapter supplies to the guide."""

    visible_chat_choices: tuple[ChatChoice, ...] = ()
    catalog_available: bool = True
    catalog_error: str | None = None

    def __post_init__(self) -> None:
        choices = tuple(self.visible_chat_choices)
        if any(not isinstance(choice, ChatChoice) for choice in choices):
            raise ValueError("visible_chat_choices must contain ChatChoice values")
        object.__setattr__(self, "visible_chat_choices", choices)

        if not isinstance(self.catalog_available, bool):
            raise ValueError("catalog_available must be a boolean")
        if self.catalog_available and self.catalog_error is not None:
            raise ValueError(
                "catalog_error must be None when the catalog is available"
            )
        if self.catalog_error is not None and (
            not isinstance(self.catalog_error, str) or not self.catalog_error.strip()
        ):
            raise ValueError("catalog_error must be non-empty when supplied")
