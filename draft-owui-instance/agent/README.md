# Agent package

This directory contains the framework-independent How-To Agent domain logic.

The package loads process definitions, the Open WebUI instruction manual, semantic UI targets, and allow-listed demonstration recipes. It also defines the stable context, reply, directive, and trigger contracts used by future Open WebUI adapters. It does not depend on Open WebUI internals, allowing the integration to remain thin.

## Contents

- `src/howto_agent/` - Python package for process-domain logic
- `system_prompt.md` - initial conversational behavior instructions
- `process_definition.example.yaml` - example process structure
- `../knowledge/open-webui-instruction-manual.md` - addressable guide content
- `../knowledge/ui-map.yaml` - canonical semantic UI target registry
- `../knowledge/recipes/` - validated, consent-gated browser recipes

The example process explains the existing Hello World UI baseline. It is intentionally linear and uses only `id`, `name`, `description`, and an ordered list of steps.

## Python API

```python
from howto_agent import HowToAgent

agent = HowToAgent.from_yaml("agent/process_definition.example.yaml")

overview = agent.get_process_overview()
first_step = agent.get_step("understand_the_goal")
next_step = agent.get_next_step("understand_the_goal")
```

Unknown step IDs and final steps return `None`. Invalid process definitions raise `ProcessDefinitionError`.

## Guide contracts and content

```python
from howto_agent import (
    AgentReply,
    ChatChoice,
    GuideContext,
    InstructionManual,
    RecipeRegistry,
    UiDirective,
    UiMap,
    normalize_trigger,
)

manual = InstructionManual.from_markdown(
    "knowledge/open-webui-instruction-manual.md"
)
ui_map = UiMap.from_yaml("knowledge/ui-map.yaml")
recipes = RecipeRegistry.from_directory(
    "knowledge/recipes",
    ui_map=ui_map,
)
manual.validate_references(
    allowed_targets=ui_map.target_ids,
    allowed_recipes=recipes.recipe_ids,
)

trigger = normalize_trigger("Start the getting started tour")
context = GuideContext(
    visible_chat_choices=(
        ChatChoice(id="hello-world", name="Hello World", kind="model"),
    )
)
reply = AgentReply(
    markdown="The model selector contains your available chat choices.",
    directives=(UiDirective(kind="highlight", target="model-picker"),),
)
```

Content loading fails closed when a manual reference, recipe action, recipe target, origin, timeout, or confirmation boundary is invalid. The generated browser asset is derived from the validated canonical UI map.

The content-aware agent constructor adds deterministic, grounded responses:

```python
guide = HowToAgent.from_content_files(
    process_path="agent/process_definition.example.yaml",
    manual_path="knowledge/open-webui-instruction-manual.md",
    ui_map_path="knowledge/ui-map.yaml",
    recipe_directory="knowledge/recipes",
)

reply = guide.respond(
    "What agents do I have access to?",
    context=context,
)
```

The guide currently routes the required starter questions, semantic highlight requests, and the versioned `getting_started` trigger without an LLM. It returns validated directives but does not execute browser actions. It also does not yet persist multi-turn tour progress; those behaviours belong to the Pipe and Guide Bridge tickets.
