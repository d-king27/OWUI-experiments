# Architecture

## Objective

This project provides a replaceable local environment for experimenting with a conversational agent that guides a user through a defined process. It deliberately avoids modifying or forking Open WebUI.

## Separation of concerns

### UI

Open WebUI owns chat interaction, model selection, conversation display, and administration. It is an interaction layer rather than the home of the project's business logic.

The unpacked Guide Bridge is a separate browser-only adapter. It owns the persistent CTA, confirmation UI, and deterministic recipe runner. It independently validates source-generated UI-map and recipe assets before performing only allow-listed browser actions. The server-side Pipe cannot access or manipulate the browser DOM.

### LLM

An OpenAI-compatible provider supplies language-model inference. The provider may be OpenAI, another compatible service, or a local Ollama instance. Provider choice must not alter the process-domain model.

### Agent and domain logic

`HowToAgent` owns process loading, ordered step lookup, deterministic onboarding intent routing, grounded manual responses, and validated UI-directive construction. It lives in a standalone Python package and has no dependency on Open WebUI internals. Open WebUI-specific user catalog lookup, conversation-state persistence, and browser execution remain outside the domain package.

### Knowledge and process content

Source-controlled YAML describes process structure. Source-controlled Markdown provides supporting explanations. Keeping these separate allows either representation to evolve without forcing the other to change.

## Integration boundary

```text
Open WebUI -> thin adapter -> HowToAgent -> process and knowledge
```

The source-controlled Pipe Function is the server adapter. Its responsibility is limited to translating Open WebUI messages and the current user's visible chat choices into domain contracts, calling `HowToAgent.respond`, and serializing the resulting Markdown and validated directives. Open WebUI v0.11.0 internal catalog imports are isolated in `openwebui/functions/catalog.py` so version changes do not leak into domain logic.

The Guide Bridge is the browser adapter. It mounts a persistent CTA, obtains explicit confirmation, and passes a versioned local request through a private extension-world registration API. The runner validates exact source-generated contracts, preconditions the complete recipe, enforces per-step and total timeouts, shows progress, and aborts without later actions on Escape. The directive renderer independently validates assistant-only `owui-action` blocks before exposing local highlight or confirmed recipe controls. A separate telemetry boundary validates a small lifecycle allow-list before dispatching ephemeral local events; the PoC has no collector or persistence.

## Deferred decisions

The initial scaffold intentionally defers retrieval, tool execution, durable process state, workflow frameworks, databases, authentication integration, and deployment infrastructure.
