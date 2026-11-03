# Feature change: real text-model planning for Script to Voice

Subsequent voice-provider activation: the local app now uses real ElevenLabs (`STV_MOCK=false`, `STV_LIVE_ENABLED=true`) for user-led dummy-FDX testing. No tests/provider validation were run for that switch. The text-only acceptance results below used mocked speech and remain historical; they do not validate live audio. See live-elevenlabs-handoff.md.

## Implemented and live-verified — 2 November 2026

Native Anthropic Messages planning is configured and enabled with `claude-haiku-5-5`, using the server-side `STV_LLM_API_KEY`. Account model listing confirmed structured-output support. Prices verified from [Anthropic's model pricing](https://platform.claude.com/docs/en/about-claude/pricing): $0.10/million input tokens and $0.50/million output tokens for this model with prompts below 100k tokens (the app bound is far smaller). No automatic model fallback or price substitution.

`providers/anthropic.py` uses `/v1/messages`, `x-api-key`, pinned API version `2023-06-01` and `output_config.format` JSON schema, with thinking disabled and no tool definitions. Unsupported provider-schema bounds are represented as descriptions and enforced by the original strict Pydantic contracts locally. Refusals, truncation, unexpected completion types/model changes, timeouts, auth/access/rate-limit failures stop safely. Malformed structured output gets at most one budgeted repair. See [structured output documentation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).

Intent receives the active selection for follow-ups, accepts exact supplied character IDs/names and resolves deterministically. A scene/time filter without a named scene is normalized to filter scope; explicit narrowing follow-ups retain the earlier selection. Unknown dialogue IDs remain rejected. More precise schema descriptions prevent mixing character, scene and dialogue identifiers. Live tests initially exposed these ambiguities; regressions were added before final acceptance.

Explicit `suggest voices` uses grounded excerpts, character names, available voice IDs and existing locked choices. Suggestions are displayed as proposals and never assigned automatically. Plain `cast` is inspection and costs no inference. Casting proposals, intent proposals and versioned direction results are cached; bounded beat results persist immediately, and plans too large for the remaining allowance stop before starting beat inference. Missing cast stops before direction requests. User overrides and explicit parentheticals retain precedence.

Live through OWUI using the synthetic two-scene fixture: freeform all-Mira selection, night-only follow-up, cast suggestion, all-role manual casting, two-scene direction/plan, exact source-backed request artifacts, cache reuse, ordinary inspection and zero render jobs passed. This was real Claude inference with mocked ElevenLabs voices/speech. It is not a live audio quality test or a claim about arbitrary full-script planning quality.

Total implementation validation (including failed probes): **10 requests**, **19,832 input tokens**, **962 output tokens**. Token/rate-based estimated cost **$0.002469**; this is not a provider billing statement or account balance. Conservative reservations remain **$0.50** against the **$1.00** app allowance, leaving **$0.50 / 10 attempts**. No reservations were refunded/reset. ElevenLabs live generation remains disabled.

Database migration v3 preserves prior data and adds sanitized usage metadata keyed to each reservation (tokens, estimated cost, request ID, stop reason/outcome and elapsed time). Prompts, scripts, keys and raw model responses are not written to that ledger. `planner budget` shows reservation and reported-token cost estimates. The Anthropic account's credit balance is not queried by the regular service, and other apps are outside this guard.

Repeatable live check: `scripts/check-stv-text-planning.py` (explicitly paid, uses the same persistent allowance; do not run as ordinary CI). Read-only availability check: `scripts/check-anthropic-models.py`. Native HTTP and cached-workflow tests use mocks. The historical design below records earlier decisions; this current implementation section supersedes its pending-adapter/provider statements.

Status: provider decision deferred by the user on 2 November 2026. A configurable adapter exists and has mock HTTP tests. No real text endpoint or credential is configured; no live text-model acceptance has passed.

Update: the user subsequently selected Anthropic API credit as the preferred provider. No Anthropic credential or model has been configured yet. Official [compatibility documentation](https://platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk) states `response_format=json_object` is rejected; the existing adapter sends that format. Simply pointing it at Anthropic is therefore insufficient. Next implementation should use native Messages with validated structured output (or explicitly tested strict JSON-schema compatibility), server-side credential/header handling, refusal/truncation/error tests and usage accounting. Using Anthropic directly from the STV service does not require adding Claude as a separate OWUI chat model; that is an optional separate UI integration.

## Purpose and user-visible change

Script to Voice currently supports deterministic commands such as `all Mira's lines`, `select scene 12A`, `find "exact phrase"`, and `only night scenes`. These commands resolve directly against the saved FDX revision. The existing hello-world provider cannot interpret freeform requests.

Enabling a real text model adds interpretation of requests such as “find the exchange where Mira first mentions the radio”, grounded casting suggestions, and sparse inferred direction based on action and surrounding dialogue. The text model proposes structured operations or annotations. Deterministic code still selects source IDs, validates ownership, preserves wording and compiles speech requests.

The selectable model remains **Script to Voice**. Users should not need to choose the underlying planner model for each message. ElevenLabs continues to provide voices and speech; its API key does not supply text inference.

## Current implementation

- `agent/src/script_to_voice/providers/planning.py`: shared asynchronous OpenAI-compatible chat-completions transport with separate intent/casting/direction schemas and prompts.
- `selection/resolver.py`: exact command recognition and deterministic resolution. Recognized commands bypass inference; otherwise an enabled planner can propose an intent.
- `casting/service.py`: account catalog shortlist and evidence profiles; optional structured planner suggestions. Suggestions never automatically replace locked assignments or authorize voice design.
- `service/workflow.py`: direction planning in bounded beats of 20 elements, with up to four adjacent elements before/after. Only selected dialogue may receive annotations. Source parentheticals and explicit user direction take precedence over inference.
- Pydantic contracts forbid unknown fields. Returned IDs and offsets are checked against the actual revision. The model cannot provide replacement dialogue or a provider request body.

Transport limits include a 60,000-context-character hard bound, a tighter default paid-request bound of 16,000 serialized UTF-8 bytes, 1,000 output tokens, a 30-second timeout, temperature zero, and one repair at most. Paid requests now require a persistent reservation ledger: $1 cumulative, $0.05 per attempt, verified exact-model prices and an explicit enable switch (off). See runbook.md for details and limitations. Endpoint errors omit provider bodies and credentials.

Mock success, malformed JSON, timeout, invented IDs, prompt instruction boundaries and prohibited recursive/mock model targets have local tests. Provider-specific schema compatibility, quality, latency, costs and behavior on real screenplay content remain unverified.

## Configuration decision to make

Choose one endpoint and model that can reliably return JSON using the supplied schema. Possible deployment approaches:

| Approach | Implications | Verification needed |
|---|---|---|
| Organisation-approved hosted endpoint | Server can call it directly; scripts/context leave the local environment under that provider's terms | Approved destination, retention policy, supported request fields, credential scope, rates and account limits |
| Existing local OpenAI-compatible server | Can keep inference local if the deployment does so; quality depends on model and hardware | Container network reachability, model identity, structured-output behavior, context limits and throughput |
| OWUI-brokered inference | Could reuse configured model access and per-user permissions | Not implemented; requires a separate OWUI access-controlled adapter and explicit recursion prevention |

The current implementation supports the first two via a direct OpenAI-compatible endpoint. It does not automatically discover or borrow OWUI provider credentials. OWUI-brokered inference is a future implementation choice, not a current capability.

Do not select hello-world, `script_to_voice`, or the Guide as the planner. A model name alone is insufficient; the service needs a reachable endpoint and, where required, a server-side credential.

## Configuration procedure

Set these values securely in the target environment:

```dotenv
STV_LLM_BASE_URL=https://your-approved-endpoint.example/v1
STV_LLM_MODEL=your-selected-model-id
STV_LLM_API_KEY=
```

The endpoint shown is illustrative and must be replaced. The base URL should include its API prefix; the adapter appends `/chat/completions`. Configure the actual key outside source control and chat. Local endpoints may leave the key blank if that is their intended authenticated network arrangement. The service should reach a host-local server through the environment's verified container-to-host route; `localhost` inside the service container refers to that container itself.

Recreate both service and worker after changing environment configuration. A plain process restart does not update an existing container's environment. Keep `STV_MOCK=true` during planner evaluation so text planning can be tested without speech charges. Leave `STV_LIVE_ENABLED=false` until separately authorizing ElevenLabs generation.

Clearing `STV_LLM_MODEL` restores deterministic-command-only operation after recreating the containers. Saved scripts, casts, jobs and audio remain on disk.

## Request contracts and source fidelity

Intent proposals are limited to inspect/select/refine operations and script/character/scene/text/filter/ID scopes. The resolver executes these against the full manifest, including minor roles. Context returned for understanding is separate from selected speech IDs. Empty results stay empty. Ambiguous scene/character references produce clarification rather than an arbitrary match.

Casting proposals refer to known character IDs and a bounded account-catalog shortlist. Creative traits must be presented as suggestions, distinct from script facts. Accepted manual assignments remain locked. An account voice is validated separately before assignment; preview IDs cannot be used for speech.

Direction proposals contain source IDs, offsets, allowed tags and evidence IDs. They cannot rewrite dialogue. Inference is marked as inference regardless of the origin label returned by the model. Explicit source parentheticals beat inference; explicit user overrides beat both at the same source location. Unsupported pronunciation/model controls remain disabled until capability verification.

Screenplay content and user requests are untrusted planning data, never permission to call tools, change configuration, generate a voice, or spend speech credits. Planner responses cannot enqueue jobs. Explicit generate/design/audition commands remain the authorization boundary.

## Data, security and operational considerations

Keep provider keys in the service/worker environment. Do not place them in Function frontmatter, browser code, downloadable plans or logs. Errors should include a correlation ID and safe category rather than raw provider payloads. Existing owner-scoped storage and session checks still apply to every referenced script/selection.

Before enabling a hosted endpoint, confirm that the screenplay content sent in prompts is permitted at that destination. Intent planning currently sends compact scene/character catalogs and the user's request; casting sends profiles/catalog candidates; direction sends bounded original script context. No audio/base64 is sent to the text model.

Timeouts and malformed results should leave saved selections/casts intact. Exact deterministic commands remain useful for recovery. Large context failures should ask for a narrower beat or exact source reference, not silently truncate source coverage.

## Cost and performance

Text inference charges are separate from ElevenLabs speech, design previews, saved voice slots and auditions. The approved £5 live-test ceiling must include any chargeable activity intended to fall within that test budget; do not assume output/context limits enforce it in pounds.

Before paid planner evaluation, verify current exact-model rates. Conservative per-attempt dollar reservations now persist, but actual token-charge reconciliation, the Anthropic credit balance and a pound-denominated cap are not implemented. This is not an account-wide spend guarantee. Record measured usage/latency/repairs during later live acceptance; native Claude transport and pricing verification remain prerequisites.

Start with short representative scenes and deterministic commands as a comparison. A full script can require many bounded direction requests. Cache versioned direction results and measure quality before expanding scope; do not regenerate inference merely to inspect an already-saved plan.

## Acceptance checklist

1. Verify the chosen model and endpoint with one bounded structured request in mock-speech mode; record exact provider/model/version and effective settings.
2. Test character aliases, production scene 12A, ambiguous descriptions, exact phrase search, discontiguous selections and follow-up refinements after reload.
3. Confirm invented/foreign IDs, rewritten dialogue, unknown tags, bad offsets and injected screenplay instructions are rejected without speech calls.
4. Test malformed/truncated JSON, timeout, authentication, rate limit and endpoint-specific unsupported fields. Repairs stay bounded and do not expose secrets.
5. Test all selected roles, including one-line characters; locked cast remains unchanged; suggested voices exist in the account catalog.
6. Compare inferred direction with explicit parentheticals/user overrides on 6–10 short scenes. Score source grounding, sparse useful direction, wording preservation and latency.
7. Confirm source context is bounded without losing authoritative selection completeness. Preserve previous valid artifacts when planning fails.
8. Add planner usage recording, a test allowance and cache validation before paid full-script planning.
9. Verify disabling the planner restores deterministic commands and preserves saved data and the Guide.

## Remaining work and release status

Provider/model selection is intentionally open. No credential, account connection or paid text request was created for this change. Live evaluation and provider-specific adjustments remain pending. Versioned direction reuse is implemented using selection, cast, overrides, model and prompt-version dependencies. Its live cache validation, dedicated planner usage accounting, persisted pronunciation glossary and any OWUI-brokered adapter require further work before claiming the complete text-planning release gate.

Continue tracking actual implementation/test results in `progress.md`; use `runbook.md` for the functioning mock workflow. This document records the feature change and decisions to review, not a claim that live planning is ready.
