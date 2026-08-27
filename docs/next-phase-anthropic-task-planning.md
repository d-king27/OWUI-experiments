# Next phase: Anthropic-backed task planning

Status: **deferred planning proposal**. This document records the intended next phase; it does not change the current proof of concept or enable an external AI service.

## Goal

Evolve the deterministic Open WebUI Guide into a grounded assistant that can understand a broader request such as “I need help with my spreadsheet”, recommend an appropriate chat choice that the user can actually access, and explain how to complete the task in Open WebUI.

The work should happen in two ordered increments:

1. Connect and verify an Anthropic model in the local Open WebUI environment.
2. Add an LLM-backed task planner behind a constrained, testable interface while retaining the existing deterministic guide as a fallback.

An Anthropic API key alone does not make the current Guide AI-powered. The Guide code must explicitly invoke a configured model, validate its result, and ground recommendations in the current user's visible chat choices.

## Current behavior to preserve

The current Guide does not use a language model. At startup it:

1. Loads `knowledge/open-webui-instruction-manual.md` as UTF-8 Markdown.
2. Parses YAML frontmatter and each level-two (`##`) heading into an addressable section. A heading such as `## What is a model?` becomes the ID `what-is-a-model`.
3. Extracts `[ui:...]` and `[recipe:...]` references and checks them against the source-controlled UI map and recipe registry.
4. Matches the user's message with regular expressions in `agent/src/howto_agent/router.py`.
5. Returns the corresponding stored section, plus a validated UI directive where applicable.

That is structured document lookup, not AI comprehension or retrieval. Unsupported wording or topics use a fixed “not enough information” response.

`agent/system_prompt.md` is currently a design artifact. The runtime Pipe does not load or execute it. The Anthropic-backed planner will be the first runtime component that needs model instructions derived from that file.

## Proposed architecture

```text
User request
    |
    v
Deterministic router ----------------------+
    | known onboarding question            | unknown/broader task
    v                                      v
Existing manual response            Anthropic-backed planner
                                           |
                         manual + capability policy + user's
                         currently visible chat choices
                                           |
                                           v
                                  structured plan candidate
                                           |
                                           v
                                  deterministic validator
                                           |
                                           v
                              explanation and safe UI offers
```

Keep the LLM responsible for interpreting and drafting. Keep code responsible for authorization and truth: available chat choices, allowed capabilities, UI targets, recipes, and whether an action needs confirmation.

## Increment A: connect Anthropic

- Configure Anthropic through Open WebUI's provider connection using `https://api.anthropic.com/v1`.
- Enter the API key through the local Open WebUI administrator UI or a local secret mechanism. Never commit it to this repository, place it in browser-extension code, or include it in telemetry.
- Select one Claude model for the experiment and record its configurable model ID rather than hard-coding a display name throughout the code.
- Verify an ordinary Open WebUI chat reaches Anthropic before changing the Guide.
- Add a short operator check for missing credentials, insufficient API credit, rate limiting, and provider unavailability.

Anthropic API usage is billed separately from consumer Claude subscriptions. The existing `hello-world` provider should remain available as a credential-free connectivity test.

## Increment B: add grounded task planning

Introduce a provider-neutral planner boundary so Anthropic is the first implementation, not a permanent dependency of the domain model.

```python
class TaskPlanner(Protocol):
    async def plan(self, request: PlanRequest) -> PlanCandidate: ...

@dataclass(frozen=True)
class PlanRequest:
    user_request: str
    manual_context: tuple[str, ...]
    visible_chat_choices: tuple[ChatChoice, ...]
    capability_profiles: tuple[CapabilityProfile, ...]

@dataclass(frozen=True)
class PlanCandidate:
    understood_goal: str
    recommended_choice_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    steps: tuple[str, ...]
    clarification: str | None = None
```

Add an organization-controlled capability registry describing evidence-backed strengths such as spreadsheet analysis, file support, tool access, cost tier, and data-handling constraints. Recommendations must be the intersection of:

- choices visible to the current user;
- entries the organization has profiled and approved; and
- capabilities required by the request.

Do not ask the model to guess which model is “best” from its general knowledge. If no approved visible choice satisfies the request, say so and explain how the user can inspect the selector or ask an administrator.

The first vertical slice should support this example:

> I need help cleaning and summarizing a spreadsheet.

Expected behavior:

1. Identify that the task involves a spreadsheet and likely requires file analysis.
2. Ask one focused question only if file type, desired output, or data sensitivity materially affects the choice.
3. Recommend one or more approved, visible chat choices with a short evidence-backed reason.
4. Explain how to select the choice, attach the file if that capability is allowed, and write a useful prompt.
5. Offer only registered highlights. Do not upload a file, switch models, or submit sensitive content automatically.

## Prompt and grounding changes

- Convert the useful behavioral constraints in `agent/system_prompt.md` into a versioned runtime prompt template.
- Retrieve only relevant manual sections for the request; include their IDs in the planner input and log IDs rather than document contents.
- Treat manual text and user-supplied files as untrusted content, not executable instructions.
- Require schema-constrained planner output and reject unknown choice IDs, UI target IDs, recipe IDs, and action types.
- Fall back to the current deterministic response when the planner is disabled, unavailable, times out, or returns invalid output.

## Delivery tickets

### N1 — Anthropic connection and secret-safe operator guide

Document local provider configuration, keep credentials out of source control, and verify a direct Claude chat. Acceptance: a named Claude model responds in Open WebUI and failure modes are documented.

### N2 — Planner contracts and feature flag

Add `TaskPlanner`, request/result schemas, a disabled-by-default feature flag, and a no-op/failure fallback. Acceptance: existing deterministic tests remain unchanged and passing when planning is disabled.

### N3 — Anthropic planner adapter

Implement the model call through the selected provider integration, load the versioned runtime prompt, enforce timeouts and structured output, and avoid logging secrets or raw user content. Acceptance: mocked success, timeout, provider error, and malformed-output tests pass.

### N4 — Capability registry and recommendation validator

Define organization-owned capability profiles and validate all planner recommendations against both the registry and the user's live catalog. Acceptance: the Guide cannot recommend an unavailable, unapproved, or unprofiled choice.

### N5 — Spreadsheet-help vertical slice and evaluations

Add representative spreadsheet requests, clarification cases, sensitive-data cases, and unavailable-capability cases. Acceptance: the Guide produces a practical Open WebUI plan without claiming it inspected a file or selected a model when it did not.

### N6 — Native welcome-page CTA handoff

Move the Getting started entry point into the organization's welcome page and retain the browser extension only as a PoC harness. Acceptance: both direct Guide selection and the native CTA produce the same versioned trigger, with no extension required in the target product.

## Evaluation and release gates

- Known onboarding questions still use deterministic manual answers.
- Every recommended choice is visible to the current user and supported by an approved capability profile.
- Invalid or unavailable planner output degrades to a safe, useful response.
- No API key, raw authorization header, spreadsheet content, or full prompt is written to repository files or local telemetry.
- UI control remains limited to registered highlights and separately confirmed allow-listed recipes.
- The browser extension is explicitly excluded from the production architecture.
- The feature remains behind a flag until the spreadsheet evaluation set and a small manual acceptance run pass.

## Deferred decisions

- Which Claude model balances quality, latency, and API cost for planning.
- Whether Open WebUI should broker planner calls or the Pipe should use a separately configured provider adapter.
- Whether task state belongs in conversation context or an external store.
- Which capability metadata the organization can maintain reliably.
- Whether future file-aware guidance needs document retrieval, tool execution, or instructions only.

Useful provider setup references: [Open WebUI: starting with Anthropic](https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-anthropic/) and [Anthropic API billing](https://support.anthropic.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console).
