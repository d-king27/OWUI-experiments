# Functions and adapters

This directory contains the source-controlled Open WebUI adapter for the How-To Agent.

The likely request path is:

```text
User
  |
  v
Open WebUI
  |
  v
How-To Agent adapter
  |
  v
HowToAgent domain logic
  +-- process definition
  +-- knowledge
  +-- semantic UI targets
  +-- allow-listed recipes
```

The initial guide is deterministic and does not call an underlying LLM.

## Open WebUI Guide Pipe

`howto_pipe.py` defines the top-level `Pipe` class detected by Open WebUI. When installed and enabled, it appears as **Open WebUI Guide** in the model selector.

The Pipe:

- Prefers `__metadata__["user_prompt"]`, preserving the user's original prompt when Open WebUI has wrapped a message with source context.
- Falls back to the most recent user message, including text blocks in multimodal content.
- Loads the model catalog only for availability questions.
- Calls the framework-independent `HowToAgent.respond` method.
- Serializes validated directives as fenced `owui-action` JSON blocks.
- Returns a grounded configuration message instead of preventing Function loading when mounted content is absent.

By default, content is loaded from `/opt/howto`. Set `HOWTO_CONTENT_ROOT` to change that root. The expected paths beneath it are:

```text
agent/process_definition.example.yaml
knowledge/open-webui-instruction-manual.md
knowledge/ui-map.yaml
knowledge/recipes/*.yaml
```

The committed Compose service mounts these paths read-only. After Open WebUI is healthy, create an administrator API key, set `OPEN_WEBUI_API_KEY`, and run `scripts/install-howto-function.ps1` to create and enable the Function. The installer refuses changed stored source unless `-Update` is supplied.

## User-visible catalog

`catalog.py` isolates internal APIs verified against Open WebUI v0.11.0. It resolves the current `__user__`, obtains all effective models, mirrors `/api/models` normalization, and then applies Open WebUI's own `get_filtered_models` access filter. Only the resulting ID, name, and conservatively inferred kind enter the domain context.

This adapter is intentionally version-sensitive. Re-test the imports and signatures whenever `WEBUI_DOCKER_TAG` changes.

## Directive transport

The Pipe appends one block per directive:

````markdown
```owui-action
{"kind":"highlight","requires_confirmation":false,"target":"model-picker","version":1}
```
````

The Guide Bridge validates its CTA recipe handoff independently. Later directive-rendering work must likewise validate the version, kind, target or recipe, and confirmation boundary before exposing a message-level UI control.

## Security

Open WebUI Functions execute server-side Python with the privileges of the Open WebUI process. Do not install arbitrary community Functions, download executable plugins at startup, or hard-code credentials. Review and source control every extension introduced here.

Catalog exceptions and configuration details are not returned to users. The Pipe emits no `tool_calls`, preventing Open WebUI from treating the self-contained guide response as a tool-execution continuation.
