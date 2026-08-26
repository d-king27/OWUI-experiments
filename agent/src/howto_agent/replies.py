"""Stable response contracts shared by the guide and UI adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DirectiveKind = Literal["highlight", "inspect", "run_recipe"]
_DIRECTIVE_KINDS = {"highlight", "inspect", "run_recipe"}


@dataclass(frozen=True, slots=True)
class UiDirective:
    """A declarative request that a client may independently validate."""

    kind: DirectiveKind
    target: str | None = None
    recipe: str | None = None
    requires_confirmation: bool = False

    def __post_init__(self) -> None:
        if self.kind not in _DIRECTIVE_KINDS:
            raise ValueError(f"unsupported UI directive kind: {self.kind}")

        if self.target is not None and (
            not isinstance(self.target, str) or not self.target.strip()
        ):
            raise ValueError("directive target must be non-empty when supplied")
        if self.recipe is not None and (
            not isinstance(self.recipe, str) or not self.recipe.strip()
        ):
            raise ValueError("directive recipe must be non-empty when supplied")

        if self.kind in {"highlight", "inspect"}:
            if self.target is None or self.recipe is not None:
                raise ValueError(
                    f"{self.kind} directives require a target and no recipe"
                )
        elif self.kind == "run_recipe":
            if self.recipe is None or self.target is not None:
                raise ValueError(
                    "run_recipe directives require a recipe and no target"
                )
            if not self.requires_confirmation:
                raise ValueError("run_recipe directives require confirmation")


@dataclass(frozen=True, slots=True)
class AgentReply:
    """Grounded response text plus optional client-side directives."""

    markdown: str
    directives: tuple[UiDirective, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.markdown, str) or not self.markdown.strip():
            raise ValueError("agent reply requires non-empty Markdown")
        object.__setattr__(self, "directives", tuple(self.directives))


def validate_directive(
    directive: UiDirective,
    *,
    allowed_targets: set[str] | frozenset[str],
    allowed_recipes: set[str] | frozenset[str],
) -> None:
    """Reject a well-formed directive that references an unknown registry ID."""

    if directive.target is not None and directive.target not in allowed_targets:
        raise ValueError(f"unknown UI target: {directive.target}")
    if directive.recipe is not None and directive.recipe not in allowed_recipes:
        raise ValueError(f"unknown UI recipe: {directive.recipe}")

