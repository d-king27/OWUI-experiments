# Open WebUI How-To Agent proof-of-concept proposal

## Status

- **Status:** Implementation in progress (Tickets 1-8 complete)
- **Scope:** Proof of concept
- **Target Open WebUI version:** The version pinned by `WEBUI_DOCKER_TAG` in this repository
- **Primary user outcome:** A new user can discover the guide, understand the core Open WebUI concepts, and complete a safe guided example from inside Open WebUI.

## Summary

Add an **Open WebUI Guide** that users can select from the normal model selector and can also launch from a persistent **Getting started** call to action (CTA). The guide answers questions conversationally from a source-controlled instruction manual, identifies the chat choices available to the current user, highlights documented Open WebUI controls, and can run a small consent-gated demonstration.

The proof of concept keeps the official Open WebUI image rather than maintaining a frontend fork. It therefore has two integration pieces:

1. A server-side Open WebUI Pipe Function exposes the guide as a selectable chat choice and adapts Open WebUI requests to the framework-independent `HowToAgent` package.
2. A small browser extension, referred to below as the **Guide Bridge**, owns browser-only behaviour: the persistent CTA, highlighting, and tightly constrained UI demonstration recipes.

The extension is needed because an Open WebUI Function executes on the server and cannot directly manipulate the user's browser DOM. Open WebUI Action Functions can add controls to individual chat messages, but do not provide the persistent, pre-chat CTA required by this experience.

## Goals

The proof of concept must let a user:

- Discover and select **Open WebUI Guide** from the normal model selector.
- Launch the same guide from a visible **Getting started** CTA without first knowing which model to select.
- Ask "What is Open WebUI?"
- Ask "How do I use it?"
- Ask "What is a model?"
- Ask "What agents or chat choices do I have access to?"
- Request a workable example.
- Ask the guide to highlight a documented part of the UI.
- Explicitly authorize a short demonstration that selects the `hello-world` model, sends a test message, and identifies the expected response.
- Stop an active demonstration immediately by pressing Escape.

## Non-goals

The proof of concept will not:

- Fork or rebuild the Open WebUI frontend.
- Provide unrestricted browser automation.
- Allow an LLM to invent selectors, JavaScript, or arbitrary UI actions.
- Interact with passwords, accounts, administration, deletion, file upload, or provider settings.
- Claim that the deterministic `hello-world` provider is an LLM or reasoning agent.
- Introduce a vector database while the instruction manual remains small.
- Guarantee selectors across untested Open WebUI versions.

## User experience

### Entry path 1: select the guide

1. The user opens the model selector.
2. The user selects **Open WebUI Guide**.
3. The user asks a question or sends `Start the getting started tour`.
4. The Pipe returns grounded guidance and, where helpful, a structured UI directive.
5. The Guide Bridge renders directives as controls such as **Show me** or **Run example**.

Open WebUI Pipe Functions appear as selectable models, so this path follows the platform's existing interaction model.

### Entry path 2: Getting started CTA

The Guide Bridge adds a small persistent **Getting started** button near the existing new-chat/navigation area. It must be visually distinct but must not cover native controls.

When activated, it opens a confirmation panel:

> Start a new guide chat? Your current chat will not be changed. The guide will open in a new chat and show you the basics of Open WebUI.

After confirmation, the bridge runs the built-in `launch-getting-started` recipe:

1. Open a new chat.
2. Open the model selector.
3. Select **Open WebUI Guide**.
4. Enter `Start the getting started tour` in the message composer.
5. Submit the message.
6. Highlight the first relevant control when the guide responds.

The submitted starter text remains visible in chat. There is no hidden user message.

If the guide is unavailable, the CTA must not attempt partial automation. It should explain that the **Open WebUI Guide** Function is not installed or not available to the current user.

### Repeat and resume behaviour

- The CTA always starts a new chat, preventing accidental changes to the user's current conversation.
- Within a guide chat, the user can ask to repeat, skip, move backwards, stop, or continue.
- The initial proof of concept keeps tour progress in the chat conversation and active browser recipe only; it does not add durable cross-chat progress.

## Trigger contract

The guide's entry behaviour must be represented as a stable intent rather than being hard-coded only to the CTA:

```python
from dataclasses import dataclass, field
from typing import Any, Literal


TriggerSource = Literal["model", "cta", "prompt", "link", "api", "onboarding"]


@dataclass(frozen=True)
class GuideTrigger:
    intent: str
    source: TriggerSource
    version: int = 1
    parameters: dict[str, Any] = field(default_factory=dict)
```

The initial trigger is:

```json
{
  "version": 1,
  "intent": "getting_started",
  "source": "cta",
  "parameters": {}
}
```

For the proof of concept, the CTA translates this trigger into the visible starter message `Start the getting started tour`. The agent normalizes both that phrase and the structured intent to the same internal route.

This boundary permits later entry points without changing the guide's domain behaviour:

- An Open WebUI saved prompt or slash command.
- A link handled by the Guide Bridge.
- An organization onboarding page.
- A stable HTTP endpoint.
- An administrator-provided welcome experience.

Those additional entry points are future work, not part of the first proof of concept.

## Architecture

```text
Open WebUI browser
  |
  +-- native model selector -----------+
  |                                    |
  +-- Guide Bridge                     |
      +-- Getting started CTA          |
      +-- directive renderer           |
      +-- target highlighter           |
      +-- recipe runner                |
      +-- model availability check     |
                                           v
                                  Open WebUI server
                                           |
                                  How-To Pipe Function
                                           |
                         +-----------------+-----------------+
                         |                 |                 |
                    HowToAgent       visible model      configured
                    domain logic       catalog          base model
                         |
                  manual + UI map + recipes
```

### Responsibility boundaries

| Component | Responsibility |
| --- | --- |
| Open WebUI | Chat storage, authentication, model selection, rendering, and user-specific access control. |
| How-To Pipe | Present the guide as a selectable model; translate request/user context; call the domain package; optionally call a configured base model. |
| `HowToAgent` | Manual lookup, process navigation, intent handling, reply construction, and directive validation. |
| Instruction manual | Authoritative explanations of Open WebUI and the supported onboarding process. |
| UI map | Stable semantic IDs and version-specific locator candidates. |
| Guide Bridge | CTA, same-origin UI inspection, highlighting, confirmation, recipe execution, cancellation, and client-side enforcement. |
| Recipe files | Pre-authored, allow-listed demonstrations. |

## Proposed repository structure

```text
agent/
|-- system_prompt.md
|-- process_definition.example.yaml
`-- src/howto_agent/
    |-- __init__.py
    |-- agent.py
    |-- context.py
    |-- manual.py
    |-- replies.py
    |-- router.py
    |-- triggers.py
    `-- recipes.py

knowledge/
|-- open-webui-instruction-manual.md
|-- ui-map.yaml
`-- recipes/
    |-- launch-getting-started.yaml
    `-- hello-world-demo.yaml

openwebui/
|-- functions/
|   |-- README.md
|   |-- howto_pipe.py
|   `-- catalog.py
`-- guide-extension/
    |-- manifest.json
    |-- content.js
    |-- guide.css
    |-- ui-map.json
    `-- README.md

scripts/
|-- build-guide-assets.py
`-- install-howto-function.ps1

tests/
|-- test_agent.py
|-- test_manual.py
|-- test_triggers.py
|-- test_ui_directives.py
|-- test_recipes.py
|-- test_howto_pipe.py
`-- browser/
    `-- guide.spec.ts

docs/
|-- architecture.md
|-- next-steps.md
|-- howto-agent-proposal.md
`-- ui-automation-security.md
```

## Instruction manual design

`knowledge/open-webui-instruction-manual.md` is the authoritative guide. It should contain these sections at minimum:

```markdown
# Open WebUI instruction manual

## What is Open WebUI?

Open WebUI is the browser interface used to discover and chat with
models and configured agents.

## How do I use it?

1. Start a new chat using [ui:new-chat].
2. Choose a model or agent using [ui:model-picker].
3. Enter a request in [ui:message-composer].
4. Submit it using [ui:send-button].
5. Review the response in [ui:assistant-message].

## What is a model?

A model is the underlying system that generates a response. An agent
combines a model with instructions, knowledge, tools, and behaviour.

## What can I access?

Ask the guide to inspect the choices available to your current Open
WebUI account. Do not use a hard-coded list.

## Workable example

Use [recipe:hello-world-demo] to run the local connectivity example.
```

The manual loader should parse headings into addressable sections. All `[ui:...]` and `[recipe:...]` references must be validated against the UI map and recipe registry during automated tests.

For the proof of concept, direct section selection is preferable to retrieval-augmented generation. It is deterministic, inspectable, and sufficient for a small manual.

## Domain response contract

The domain agent returns Markdown plus optional validated directives:

```python
from dataclasses import dataclass, field
from typing import Literal


DirectiveKind = Literal["highlight", "inspect", "run_recipe"]


@dataclass(frozen=True)
class UiDirective:
    kind: DirectiveKind
    target: str | None = None
    recipe: str | None = None
    requires_confirmation: bool = False


@dataclass(frozen=True)
class AgentReply:
    markdown: str
    directives: tuple[UiDirective, ...] = field(default_factory=tuple)
```

Only semantic IDs from the source-controlled registries are valid:

```python
def validate_directive(
    directive: UiDirective,
    *,
    allowed_targets: set[str],
    allowed_recipes: set[str],
) -> None:
    if directive.target and directive.target not in allowed_targets:
        raise ValueError(f"unknown UI target: {directive.target}")

    if directive.recipe and directive.recipe not in allowed_recipes:
        raise ValueError(f"unknown UI recipe: {directive.recipe}")
```

The LLM, if one is configured, may help phrase grounded explanations. It must not generate executable selectors, action types, scripts, or unregistered recipe IDs.

## Pipe Function

The Pipe is intentionally thin:

```python
class Pipe:
    def __init__(self):
        self.name = "Open WebUI Guide"
        self.agent = build_agent(
            manual_path="/opt/howto/knowledge/open-webui-instruction-manual.md",
            ui_map_path="/opt/howto/knowledge/ui-map.yaml",
            recipe_dir="/opt/howto/knowledge/recipes",
        )

    async def pipe(self, body: dict, __user__: dict, __request__) -> str:
        choices = await visible_chat_choices(__request__, __user__)
        message = body["messages"][-1]["content"]

        reply = await self.agent.respond(
            message,
            visible_chat_choices=choices,
        )
        return render_reply_with_directives(reply)
```

Open WebUI integration imports are isolated in `openwebui/functions/catalog.py` because they may change between Open WebUI versions. That adapter must obtain the same user-filtered model list used by the UI rather than returning an administrator-wide list.

The answer should use **available chat choices** as its default language. Items should only be labelled as a base model, custom model, or agent when Open WebUI metadata provides enough evidence to classify them.

## Directive transport

The proof of concept transports directives in fenced Markdown blocks:

````markdown
The model selector is at the top of the chat. Choose **Show me** and I
will highlight it.

```owui-action
{"version":1,"kind":"highlight","target":"model-picker"}
```
````

The Guide Bridge observes newly rendered messages, validates the JSON, hides the raw directive block, and replaces it with a local control. Invalid or unknown directives remain inert and produce a non-blocking error in the extension console.

This transport is deliberately replaceable. If Open WebUI later exposes a stable first-class client extension/event contract, only the renderer and transport layer should change.

## UI map

The canonical `knowledge/ui-map.yaml` contains semantic targets and ordered locator candidates:

```yaml
open_webui_version: v0.11.0

targets:
  new-chat:
    description: Starts a new conversation.
    locators:
      - kind: role
        role: button
        accessible_name: [New chat]

  model-picker:
    description: Opens the current model or agent selector.
    locators:
      - kind: role
        role: button
        accessible_name: [Select a model, Models]
      - kind: test_id
        value: model-selector
      - kind: css_fallback
        value: "button[aria-haspopup='listbox']"

  message-composer:
    description: The main chat input.
    locators:
      - kind: role
        role: textbox
      - kind: css_fallback
        value: textarea
```

Roles, accessible names, and test IDs are preferred. CSS selectors are last-resort, version-pinned fallbacks. `scripts/build-guide-assets.py` validates this YAML and generates the extension's `ui-map.json`, avoiding two manually maintained copies.

## Guide Bridge and CTA

The extension is restricted to configured local Open WebUI origins:

```json
{
  "manifest_version": 3,
  "name": "Open WebUI Guide Bridge",
  "version": "0.1.0",
  "content_scripts": [
    {
      "matches": ["http://localhost:3000/*", "http://127.0.0.1:3000/*"],
      "js": ["content.js"],
      "css": ["guide.css"]
    }
  ]
}
```

The CTA must be injected once and survive client-side navigation without duplication:

```javascript
function ensureGettingStartedCta() {
  if (document.querySelector("[data-howto-guide-cta]")) return;

  const host = findKnownTarget("navigation-actions");
  if (!host) return;

  const button = document.createElement("button");
  button.dataset.howtoGuideCta = "true";
  button.type = "button";
  button.textContent = "Getting started";
  button.addEventListener("click", showGettingStartedConfirmation);
  host.appendChild(button);
}

const observer = new MutationObserver(ensureGettingStartedCta);
observer.observe(document.documentElement, { childList: true, subtree: true });
ensureGettingStartedCta();
```

The proof of concept should use native-looking but separately namespaced CSS. It should not copy or override Open WebUI styles globally.

## Recipe runner

### Launch recipe

```yaml
id: launch-getting-started
title: Open the getting started guide
requires_confirmation: true
steps:
  - action: click
    target: new-chat
  - action: click
    target: model-picker
  - action: choose_option
    target: model-picker
    value: Open WebUI Guide
  - action: type
    target: message-composer
    value: Start the getting started tour
  - action: click
    target: send-button
```

### Workable example recipe

```yaml
id: hello-world-demo
title: Try the Hello World model
requires_confirmation: true
steps:
  - action: click
    target: model-picker
  - action: choose_option
    target: model-picker
    value: hello-world
  - action: type
    target: message-composer
    value: Test the connection
  - action: click
    target: send-button
  - action: wait_for_text
    target: assistant-message
    value: "Hello, world! The baseline chat connection is working."
    timeout_ms: 15000
  - action: highlight
    target: assistant-message
```

Recipe execution is client-side and deterministic:

```javascript
async function runRecipe(recipeId) {
  const recipe = getAllowedRecipe(recipeId);
  const controller = new AbortController();
  activeRecipeController = controller;

  for (const step of recipe.steps) {
    await runAllowedStep(step, { signal: controller.signal });
  }
}

document.addEventListener("keydown", event => {
  if (event.key === "Escape") {
    activeRecipeController?.abort();
    clearGuideHighlights();
  }
});
```

## Safety and privacy controls

"Take over" means executing a short source-controlled recipe, not general browser control.

The proof of concept must enforce:

- Explicit confirmation before any recipe that clicks, types, or submits.
- Highlight-only actions may execute without confirmation.
- Allow-listed origin, target, recipe, action, and fixed example values.
- No arbitrary selector or script received from a model.
- No password, account, administration, deletion, upload, settings, or provider-credential targets.
- Escape immediately cancels the active recipe.
- A visible indicator while automation is active.
- Per-step timeout and maximum total recipe duration.
- Failure closed when a target is missing or ambiguous.
- No collection or transmission of unrelated page content.
- No hidden message submission.
- No continuation after navigation to an unapproved origin.

The Pipe and extension must validate directives independently. Server validation is not a substitute for client enforcement.

## Testing strategy

### Domain unit tests

- Loads the manual and selects all required sections.
- Recognizes each minimum FAQ and the `getting_started` intent.
- Treats CTA starter text and a structured trigger as the same intent.
- Returns user-visible chat choices from supplied context rather than a hard-coded list.
- Rejects unknown UI targets, recipes, and directive kinds.
- Detects broken `[ui:...]` and `[recipe:...]` manual references.

### Pipe contract tests

- Registers as **Open WebUI Guide**.
- Passes user and request context to the catalog adapter.
- Does not expose choices unavailable to the current user.
- Renders valid directive blocks.
- Handles a missing configured base model with a grounded fallback response.
- Does not recurse into the guide Pipe when using an underlying model.

### Browser tests

Run Playwright against the Compose-pinned Open WebUI container:

- Exactly one CTA is visible after initial load and client-side navigation.
- CTA confirmation can be cancelled without changing the current chat.
- Confirming the CTA opens a new chat, selects the guide, and sends the starter message.
- Missing guide availability produces a useful error and no partial recipe.
- **Show me** highlights the intended element and scrolls it into view.
- Unknown or malformed directives do not execute.
- The Hello World recipe produces and highlights the expected fixed response.
- Escape aborts between every recipe step.
- Recipes fail closed when targets are missing or ambiguous.

### Manual verification

Test at the minimum supported viewport and one narrow viewport. Verify that the CTA does not cover native controls, keyboard focus remains visible, confirmation is keyboard accessible, and highlighting is understandable without relying only on colour.

## Configuration and installation

For the proof of concept:

- Mount `agent/src` and `knowledge` read-only into the Open WebUI container.
- Add the mounted source directory to `PYTHONPATH`, or package and install the local project during image construction.
- Install the source-controlled Pipe Function through an administrator-controlled setup step.
- Load the unpacked Guide Bridge extension in Chrome or Edge for local testing.
- Keep automatic Function dependency installation disabled.
- Do not commit provider credentials or the local `.env` file.

The installation script should be idempotent or should clearly report when manual administrator action is required. It must not overwrite an existing Function silently.

## Observability

Use structured, privacy-conscious events for PoC evaluation:

- `guide_cta_shown`
- `guide_cta_started`
- `guide_cta_cancelled`
- `guide_cta_unavailable`
- `guide_question_answered` with a coarse intent, not message text
- `guide_directive_shown`
- `guide_recipe_started`
- `guide_recipe_completed`
- `guide_recipe_cancelled`
- `guide_recipe_failed` with recipe ID, step ID, and error category

Do not log full chat content, DOM content, credentials, or user-entered values.

## Acceptance criteria

The proof of concept is complete when:

1. **Open WebUI Guide** is selectable from the model selector.
2. A persistent **Getting started** CTA is visible with the Guide Bridge enabled.
3. Cancelling the CTA leaves the current chat untouched.
4. Confirming the CTA starts a new guide chat and submits the visible starter prompt.
5. The guide answers all five required subject areas from the instruction manual.
6. The guide reports the current user's visible chat choices without using a hard-coded list.
7. The guide can highlight every UI control referenced by the supported manual sections.
8. The user can run the consent-gated Hello World example successfully.
9. Escape stops either recipe without further clicks or submissions.
10. Unknown directives, targets, actions, and recipes remain inert.
11. Automated tests pass against the pinned Open WebUI version.
12. Setup, limitations, manual verification, and reset steps are documented.

## Proof-of-concept trade-offs and future path

The browser extension is the smallest practical way to prove a persistent CTA and DOM guidance while retaining the official Open WebUI image. It introduces a version-sensitive UI map and requires local extension installation. Those are acceptable PoC constraints but should be evaluated before production use.

If the experiment succeeds, compare these production options:

1. Continue with a managed organization browser extension.
2. Contribute or adopt a stable Open WebUI client extension point.
3. Maintain a small Open WebUI frontend customization if a first-class onboarding CTA becomes strategically important.

The trigger contract, manual, domain agent, and recipe schema remain useful under any of these options. Only the client adapter should need replacement.

## References

- [Open WebUI Functions](https://docs.openwebui.com/features/extensibility/plugin/functions/)
- [Open WebUI Pipe Functions](https://docs.openwebui.com/features/extensibility/plugin/functions/pipe/)
- [Open WebUI API endpoints](https://docs.openwebui.com/reference/api-endpoints/)
- [Open WebUI plugin development internals](https://docs.openwebui.com/features/extensibility/plugin/development/under-the-hood/)
- Repository architecture: `docs/architecture.md`
- Existing agent package: `agent/src/howto_agent/agent.py`
- Existing Hello World explanation: `knowledge/example-process.md`
