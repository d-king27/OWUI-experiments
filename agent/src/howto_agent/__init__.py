"""Domain logic for the experimental How-To Agent."""

from .agent import HowToAgent, ProcessDefinitionError
from .context import ChatChoice, ChatChoiceKind, GuideContext
from .manual import InstructionManual, ManualDefinitionError, ManualSection
from .recipes import (
    ContentDefinitionError,
    RecipeDefinition,
    RecipeRegistry,
    RecipeStep,
    UiMap,
)
from .replies import AgentReply, DirectiveKind, UiDirective, validate_directive
from .triggers import (
    GuideTrigger,
    GuideTriggerError,
    TriggerSource,
    normalize_trigger,
)

__all__ = [
    "AgentReply",
    "ChatChoice",
    "ChatChoiceKind",
    "ContentDefinitionError",
    "DirectiveKind",
    "GuideContext",
    "GuideTrigger",
    "GuideTriggerError",
    "HowToAgent",
    "InstructionManual",
    "ManualDefinitionError",
    "ManualSection",
    "ProcessDefinitionError",
    "RecipeDefinition",
    "RecipeRegistry",
    "RecipeStep",
    "TriggerSource",
    "UiDirective",
    "UiMap",
    "normalize_trigger",
    "validate_directive",
]
