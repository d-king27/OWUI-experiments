# Architecture

## Objective

This project provides a replaceable local environment for experimenting with a conversational agent that guides a user through a defined process. It deliberately avoids modifying or forking Open WebUI.

## Separation of concerns

### UI

Open WebUI owns chat interaction, model selection, conversation display, and administration. It is an interaction layer rather than the home of the project's business logic.

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

The source-controlled Pipe Function is the initial adapter. Its responsibility is limited to translating Open WebUI messages and the current user's visible chat choices into domain contracts, calling `HowToAgent.respond`, and serializing the resulting Markdown and validated directives. Open WebUI v0.11.0 internal catalog imports are isolated in `openwebui/functions/catalog.py` so version changes do not leak into domain logic.

## Deferred decisions

The initial scaffold intentionally defers retrieval, tool execution, durable process state, workflow frameworks, databases, authentication integration, and deployment infrastructure.
