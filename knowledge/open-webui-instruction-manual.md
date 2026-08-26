---
id: open_webui_instruction_manual
title: Open WebUI instruction manual
version: 0.1.0-draft
status: draft
target_open_webui_version: v0.11.0
audience: new Open WebUI users
---

# Open WebUI instruction manual

## About this manual

This is the authoritative starter manual for the Open WebUI Guide proof of concept. The guide should ground its explanations in this document and should say when the document does not contain enough information.

References such as `[ui:model-picker]` point to semantic targets in `knowledge/ui-map.yaml`. References such as `[recipe:hello-world-demo]` point to allow-listed demonstrations in `knowledge/recipes/`.

The UI references are intentionally semantic. The visible label or underlying HTML may change between Open WebUI versions without changing what the control means.

## What is Open WebUI?

Open WebUI is the browser interface used in this project to discover and chat with available models and configured agents. It owns the chat screen, model selection, message history, and user-specific access to configured chat choices.

Open WebUI is not itself the model producing an answer. It sends a request to the selected model, provider, or Pipe agent and renders the result in the conversation.

In this repository, the current Hello World baseline follows this path:

```text
User message
    |
    v
Open WebUI
    |
    v
hello-provider
    |
    v
Fixed response rendered by Open WebUI
```

The fixed response proves that the browser, Open WebUI, and provider can exchange a chat request. It does not prove that a language model, agent, retrieval system, or tool has reasoned about the message.

## How do I use Open WebUI?

The basic chat workflow is:

1. Start a conversation using [ui:new-chat].
2. Open [ui:model-picker].
3. Choose the model or agent appropriate for your task.
4. Enter a clear request in [ui:message-composer].
5. Submit it using [ui:send-button].
6. Review the response shown in [ui:assistant-message].
7. Continue in the same chat when the next request depends on earlier context. Start a new chat when beginning a separate task.

You can ask the Open WebUI Guide to show a documented control. For example:

- `Show me where I select a model.`
- `Highlight the message box.`
- `Where will the answer appear?`

The guide may offer a **Show me** control. Highlighting identifies the element but does not click or submit anything.

## What is a model?

A model is the underlying system that receives input and generates output. Different models may have different strengths, context limits, supported input types, speed, and cost.

Selecting a model answers the question: **Which underlying capability should respond to this message?**

An agent is a configured experience built around a model or program. It may add:

- Instructions describing its role and behaviour.
- Knowledge documents.
- Tools or APIs.
- A defined process or workflow.
- State or rules for choosing the next action.

In Open WebUI, base models, custom models, and Pipe agents can all appear in the model selector. The interface therefore shows **chat choices**, even though not every choice is the same kind of thing.

The `hello-world` choice in this repository is neither a language model nor a reasoning agent. It is a deterministic development provider that returns the same response to every message.

## What models or agents can I access?

Availability is specific to the current Open WebUI user and configuration. The guide must inspect the user's current visible chat choices at runtime rather than rely on a hard-coded list in this manual.

Ask:

```text
What models or agents can I access?
```

The guide should:

1. Report the choices visible to the current user.
2. Use the neutral term **chat choice** when it cannot classify an item reliably.
3. Identify a base model, custom model, or Pipe agent only when Open WebUI supplies enough metadata.
4. Offer to highlight [ui:model-picker] so the user can inspect the same list in the interface.

If the runtime list cannot be obtained, the guide should explain that it cannot verify current access and should direct the user to [ui:model-picker]. It must not substitute an administrator-wide list or invent likely choices.

## What is the Open WebUI Guide?

The Open WebUI Guide is the How-To Agent proposed by this repository. It combines:

- This instruction manual.
- The source-controlled process definition.
- Runtime information about the current user's visible chat choices.
- A semantic map of supported Open WebUI controls.
- A small registry of consent-gated demonstration recipes.

The guide is available through two proof-of-concept entry paths:

1. Select **Open WebUI Guide** from [ui:model-picker].
2. Use the persistent [ui:getting-started-cta] supplied by the Guide Bridge browser extension.

Both paths route to the same `getting_started` intent. The CTA opens a new chat so the current conversation is not changed.

## Getting started tour

When the user sends `Start the getting started tour`, provide the following tour one section at a time:

1. Explain the difference between Open WebUI and a model.
2. Highlight [ui:model-picker] and explain chat choices.
3. Highlight [ui:message-composer] and explain how to write a request.
4. Highlight [ui:send-button] and explain submission.
5. Highlight [ui:assistant-message] and explain where results appear.
6. Offer [recipe:hello-world-demo] as an optional workable example.

Do not run the example automatically. The user must explicitly choose **Run example** and approve the confirmation describing what will be clicked, typed, and submitted.

The user may say `next`, `back`, `repeat`, `skip`, or `stop`. Do not claim a tour step is complete only because it was described; distinguish between explaining a control, highlighting it, and the user operating it.

## Workable example: Hello World connectivity

The [recipe:hello-world-demo] demonstration shows the smallest working chat flow in this repository.

With the user's confirmation, the Guide Bridge will:

1. Select `hello-world` using [ui:model-picker].
2. Type `Test the connection` in [ui:message-composer].
3. Submit the message with [ui:send-button].
4. Wait for this exact response in [ui:assistant-message]:

```text
Hello, world! The baseline chat connection is working.
```

5. Highlight the result.
6. Re-select **Open WebUI Guide** so the user can continue asking questions.

The content of the test message does not affect the Hello World response. A successful result demonstrates the UI-to-provider connection only.

If the expected response does not appear, stop the recipe and explain that the environment may need checking. Do not keep clicking or resubmit automatically.

## UI guidance and consent

The guide supports two categories of browser assistance:

### Highlighting

Highlighting may scroll a known element into view and visually identify it. It does not change Open WebUI state and does not require takeover confirmation.

### Demonstration recipes

A recipe may click, select, type fixed example text, or submit a fixed example message. Before it starts, the Guide Bridge must show exactly what it will do and require confirmation.

During a recipe:

- A visible automation indicator must remain present.
- Pressing Escape must stop the recipe immediately.
- A missing or ambiguous target must stop the recipe.
- The recipe must not continue on an unapproved site.
- The guide must never interact with passwords, accounts, administration, deletion, upload, provider settings, or credentials.

The language model cannot supply arbitrary selectors, scripts, or actions. Only semantic targets and recipes registered in this repository may execute.

## Common questions

### Why do I see both models and agents in one selector?

Open WebUI uses the model selector as the common entry point for several types of chat capability. A Pipe Function can appear there as an agent-like selectable model. When type information is unclear, treat each entry as a chat choice and describe only what can be verified.

### Will the Getting started button change my current chat?

No. The proof-of-concept CTA asks for confirmation and starts a new chat before selecting the Open WebUI Guide.

### Can the guide control any part of Open WebUI?

No. It can highlight allow-listed targets and execute a small number of source-controlled recipes. Unknown targets and actions must remain inert.

### Can I stop a demonstration?

Yes. Press Escape. The Guide Bridge should stop before executing another step and remove active highlighting or progress UI.

### Why can the guide not find a control?

Open WebUI markup can change between versions, the current viewport can alter navigation, or the control may not be available to the current user. The guide should stop safely and report which semantic target could not be resolved.

## Troubleshooting the local proof of concept

If the Hello World response does not appear, check the local services before changing agent behaviour:

```powershell
docker compose ps
docker compose logs hello-provider open-webui
```

If **Open WebUI Guide** is missing from [ui:model-picker], verify that the source-controlled Pipe Function has been installed and enabled for the current user.

If [ui:getting-started-cta] is missing, verify that the Guide Bridge extension is installed, enabled, and permitted to run on the local Open WebUI origin.

If a highlight or recipe reports that a target is unavailable, record the Open WebUI version and refine the provisional locators in `knowledge/ui-map.yaml`. Do not work around the failure with an unrestricted selector supplied through chat.

