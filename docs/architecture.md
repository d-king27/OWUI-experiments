# Architecture

## Objective

This project provides a replaceable local environment for experimenting with a conversational agent that guides a user through a defined process. It deliberately avoids modifying or forking Open WebUI.

## Separation of concerns

### UI

Open WebUI owns chat interaction, model selection, conversation display, and administration. It is an interaction layer rather than the home of the project's business logic.

### LLM

An OpenAI-compatible provider supplies language-model inference. The provider may be OpenAI, another compatible service, or a local Ollama instance. Provider choice must not alter the process-domain model.

### Agent and domain logic

The future `HowToAgent` owns process lookup and orchestration. It lives in a standalone Python package and has no dependency on Open WebUI internals.

### Knowledge and process content

Source-controlled YAML describes process structure. Source-controlled Markdown provides supporting explanations. Keeping these separate allows either representation to evolve without forcing the other to change.

## Integration boundary

```text
Open WebUI -> thin adapter -> HowToAgent -> process and knowledge
```

A future Pipe Function is the most likely initial adapter. Its responsibility should be limited to translating Open WebUI messages and configuration into calls to the domain package, then returning an appropriate response.

## Deferred decisions

The initial scaffold intentionally defers retrieval, tool execution, durable process state, workflow frameworks, databases, authentication integration, and deployment infrastructure.
