"""Domain logic for the experimental How-To Agent."""

from .agent import AgentConfigurationError, HowToAgent, ProcessDefinitionError
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
from .router import GuideIntent, IntentMatch, route_guide_input
from .triggers import (
    GuideTrigger,
    GuideTriggerError,
    TriggerSource,
    normalize_trigger,
)

__all__ = [
    "AgentReply",
    "AgentConfigurationError",
    "ChatChoice",
    "ChatChoiceKind",
    "ContentDefinitionError",
    "DirectiveKind",
    "GuideContext",
    "GuideIntent",
    "GuideTrigger",
    "GuideTriggerError",
    "HowToAgent",
    "InstructionManual",
    "IntentMatch",
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
    "route_guide_input",
    "validate_directive",
]
