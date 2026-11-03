# Script to Voice: guided user journeys

Updated 2 November 2026. This is the current conversational UX contract, including recovery paths. The implementation is ready for user-led validation; **these new paths have not been tested**. Earlier mock/browser and text-planning results do not establish acceptance of this change or real ElevenLabs audio.

## 1. Purpose and entry points

The user selects **Script to Voice** in Open WebUI. The workflow guides them through:

**Upload FDX → Select dialogue → Cast characters → Line direction → Generate → Listen/download.**

Workflow chat responses include the active script, selection summary where applicable, the current numbered step, its missing requirement and concrete commands. Wrong-model exits deliberately focus on leaving; connection/context failures use recovery wording. Responses use saved, owner-scoped domain state. Guidance does not ask a model to invent the next step and does not itself call Claude or ElevenLabs.

The first prompt can simply be “hello” or “what can you do?” A script is required for production, but is not required to get help or leave a mistaken model choice. An existing chat with an active script resumes that context; it does not demand another upload. `scripts` lists saved projects for explicit reopening.

**UI boundary:** selecting the model alone does not display a new assistant message. The Pipe runs when the user sends a message. This change provides guided chat responses, not a custom wizard, clickable stepper or automatic popup. Existing OWUI attachment, model selector, audio and download controls provide the UI. If OWUI will not submit an attachment-only message, send `Use attached script` with it.

## 2. State and transition contract

| Step | Entry requirement | Guidance and user action | Successful transition |
|---|---|---|---|
| 1 — Upload script | No active revision | Attach one original `.fdx`; send it. Offer `scripts` for saved work and `wrong model` for exit. | Import reports source title, scene and character counts; advances to selection. |
| 2 — Select dialogue | Script loaded; selection absent/empty or awaiting a scope choice | Ask directly for **entire script**, **a single scene**, or **a single character**. Help specify the scene or character with a source-derived list and a follow-up question. | Exact ordered source dialogue and line IDs are shown. Context is separate from spoken dialogue. |
| 3 — Review casting | Missing assignments or unconfirmed casting changes | Show missing names and proposed character-to-voice mappings immediately. Ask for existing voice IDs/links, then ask the user to double-check and confirm the exact review. | Group validated and committed together; existing unchanged assignments remain. |
| 4 — Line direction | Casting confirmed; no current prepared direction | Ask whether the user wants to proceed with line direction. Reply yes/proceed to prepare suggested delivery while retaining original dialogue. | Offer one downloadable direction package; generation still needs separate authorization. |
| 5 — Review direction package | Prepared direction still matches selection and cast | Download `direction-package.zip`, review `line-direction.txt`, then reply `generate` when happy. No inline scene/character summaries. | Explicit audio authorization queues a durable job; guidance advances to progress/retrieval. |
| 6 — Listen/download or recover | Job corresponds to the prepared plan | Browser chat shows animated generation status and real completed-part counts, then returns the player/downloads automatically. `status` resumes checking after a disconnect or bounded wait. | User listens/downloads, or resolves a clearly described failure/cancellation. |

The stage follows saved state rather than the last word the user typed. A cast change invalidates the earlier plan by cast hash. New selections and direction overrides clear the prepared-plan reference. Script/project/revision switches clear active selection, overrides, prepared plan and job pointer; persisted objects and audio are retained. A direct typed API client continues to use its existing plan/hash contracts; the conversational review gate is in the chat workflow.

`generate` before line direction is prepared is stopped before planning or speech dispatch. Stale prepared requests also stop. Generation uses the saved plan internally; it does not silently re-plan, spend fresh Claude credit or expand selected scope. `generate` remains the user's separate authorization after reading the direction. An unchanged duplicate generation retains the existing idempotency behavior.

### Step 2 — direct choices and follow-up questions

The initial prompt is:

> Please specify one of the following:
>
> - **Entire script** — reply “entire script”.
> - **A single scene** — reply “single scene”; I’ll help you describe or specify it.
> - **A single character** — reply “single character”; I’ll ask for the character’s name.
>
> Only dialogue from your chosen scope will be spoken.

| Reply | Assistant response / next reply | Result |
|---|---|---|
| `entire script` | Show the exact dialogue selection. | All dialogue, in source order. No automatic casting or generation. |
| `single scene` / `a single scene` | Ask which scene; show its production number and heading for every scene. User replies with a number or location/time description. | Select only one uniquely identified scene. |
| `single character` / `a single character` | Ask which character; show source character names. User replies with a name. | Select that character's dialogue across the script, including exact known aliases. |
| `single scene: 12A` | Resolve directly from the supplied number. | Same single-scene selection, with no extra question. |
| `single character: MIRA` | Resolve directly from the supplied source name. | Same single-character selection, with no extra question. |
| A new scope choice while answering a follow-up | Switch to the chosen path. | No requirement to finish the previous choice first. |

Scene descriptions use the original scene heading/location/time metadata. For example, “the rooftop at night” can resolve a unique `EXT. ROOFTOP - NIGHT`. Descriptions of plot events that cannot be grounded in that metadata ask for a clearer number/description; they do not guess, call Claude or expand to the whole script. Ambiguous matches show candidate scenes. An unknown character asks for an exact name from the list.

Choosing the scene or character path clears the previous selection, its overrides and prepared-plan pointer before awaiting details. It preserves source, saved cast, audio and existing jobs. An unresolved follow-up stays at Step 2; it cannot silently render a previous selection. The pending choice is saved per chat, survives `help`/source browsing and clears on successful selection, explicit reset or script/revision switch. Established commands such as `select all`, `select scene NUMBER`, character-line queries and `find "exact phrase"` remain available alongside this simpler menu.

### Step 3 — proposal first, existing casting second, explicit confirmation

The default response after a nonempty selection now prepares voice proposals for missing roles and displays them without requiring the user to ask for a catalog. The presentation follows this order:

1. Missing character voices.
2. Proposed casting, with each character, actual account voice name/ID and proposed/confirmed status.
3. A request to double-check the full mapping and a specific confirmation phrase.
4. Final question: **“Are any of these characters already cast? If so, provide their voice IDs or ElevenLabs links, one line per character.”**

Users can reply with lines such as `VANCE: VOICE_ID` and `KIRA: ELEVENLABS_LINK`. These are character-to-voice mappings, not recorded samples, script dialogue or API credentials. Multiple lines update one saved review. The older `cast CHARACTER as VOICE_ID` syntax now stages a change too; it no longer assigns immediately.

Actual voice IDs in proposed/retained casting and catalog/confirmed-cast lists are clickable links to the ElevenLabs Voice Library, using `https://elevenlabs.io/app/voice-library?voiceId=ID`. This format was checked against the official public [Voice Library](https://elevenlabs.io/voice-library) “Use voice” links. The label remains the copyable ID. Mock/preview IDs remain plain text; no API key or service credential is included. Opening a link does not apply a casting assignment. ElevenLabs account access/login still applies; private/generated-voice navigation and actual OWUI link rendering remain pending user browser validation. No account API call or browser test was run to verify this change.

The assistant displays the updated review and asks the user to reply **confirm cast**, with no code to copy. This confirms the latest pending review in this chat. Revision, selection and confirmed-cast-version checks remain internal: an absent or stale review cannot be applied. A plain “yes”, “no”, “none” or “accept suggestions” does not commit anything or invoke interpretation. A complete mapping is required before confirmation; unresolved roles remain at Step 3. Editing voice lines shows the updated review; the same simple confirmation phrase applies to that latest list.

Confirmation checks availability of **every** proposed voice before writing one new cast version. An unavailable voice prevents the whole group being applied. Unchanged confirmed roles are retained. Staging changes invalidates the prepared plan, and chat planning/generation cannot bypass a pending review. `discard cast changes` removes the draft while retaining previously confirmed assignments. Explicit earlier-revision reuse also stages its exact matches for review instead of applying them immediately.

**Cost boundary:** requesting a new dialogue selection can now use Claude to propose casting automatically, even when resolving the selection itself was deterministic. The existing total/per-attempt allowance, cache and server-side enable guard apply unchanged. Suggestions are creative proposals from the bounded account catalog, not source facts. Help/`what next` and redisplaying a saved review do not request fresh suggestions. `cast` / `review cast` can prepare a missing review; `suggest voices` explicitly refreshes suggestions while retaining user-entered choices. If planning/catalog access fails or a proposal omits a role, show the requirement/error and accept explicit voice mappings; do not invent IDs or auto-assign a fallback.

**Links:** the implementation extracts one ID from supported ElevenLabs HTTPS links (a `voiceId`/`voice_id` query, `/voices/ID`, or a share path ending `/share/PUBLIC_USER/VOICE_ID`). It does not follow the URL, import a shared voice, create a clone or bypass account permissions. Unknown/ambiguous formats ask the user to copy the voice ID instead. A provider lookup checks account access before staging and confirmation. ElevenLabs documents [voice IDs](https://elevenlabs.io/docs/help-center/technical/how-do-i-find-the-voice-id-of-my-voices-via-the-website-and-api), [sharing/access](https://elevenlabs.io/docs/help-center/product/voices/my-voices/how-do-i-share-a-voice) and a [separate shared-voice import operation](https://elevenlabs.io/docs/api-reference/voices/voice-library/share); this UX does not perform that import automatically.

**Generated voices:** saving a chosen preview explicitly creates/saves the provider voice and consumes any applicable voice slot, but no longer assigns the character automatically. The saved voice joins the same review, and the user must confirm casting before planning or ordinary character audition. An explicit `audition CHARACTER as VOICE_ID` can still audition a candidate without assigning it. Design previews and auditions remain separately requested paid operations.

**API boundary:** this confirmation is the OWUI conversational journey. Existing typed cast PUT/reconciliation endpoints remain explicit programmatic assignment operations with their version/ownership checks; API clients must implement their own review UI. The voice-save domain/API operation now returns a saved account voice without auto-assignment. Earlier saved voices/casts are preserved, not retroactively unassigned.

### Step 4 — confirm proceeding with line direction

The default prompt no longer asks the user to understand a “plan”, source mapping, voice IDs or request splitting:

> **Step 4 of 6 · Line direction**
>
> Your cast is confirmed. Would you like to proceed with line direction? I’ll suggest how the selected dialogue should be delivered, such as tone and pauses, while keeping the original words unchanged.
>
> Reply **yes** or **proceed** to continue. This may use Claude credit; no audio is generated at this stage.

`yes` at Step 4, `proceed`, `proceed with line direction` and `confirm line direction` prepare direction through the existing guarded/cached operation. The older `plan` / `prepare` commands remain advanced aliases. No inference is dispatched just because Step 4 is displayed. Missing/unconfirmed casting still blocks this step. A “yes” while reviewing unconfirmed casting does not apply the cast; after direction is already prepared it does not repeat inference or authorize audio. `no` / `not yet` starts no new direction/audio work.

After proceeding, the chat simply says the **direction package is ready**. Step 5 asks the user to download it, review it outside chat, then reply **generate** when happy. There are no automatic character/scene summaries, cue-count tables or line-by-line reviews, regardless of script length.

The single attached **direction-package.zip** contains:

- **line-direction.txt** — complete readable dialogue and delivery notes, grouped by scene, retaining all selected wording/order.
- **README.txt** — how to review the package, any preparation notes and the next action in chat.
- **render-plan.json** — complete requests/source mappings for optional technical inspection.

The package is assembled locally from saved direction and requests. Re-downloading unchanged preparation is byte-identical and needs no new inference or speech. `direction package` or `download direction package` retrieves it again; a repeat yes after preparation also retrieves it without repeating inference or generating audio. The earlier `direction summary` alias now returns the package rather than a summary.

Advanced detail/pagination commands remain available for explicitly requested inspection, but are not advertised in the default journey. They retain the earlier twenty-line/240-character bounds and cannot expand selected scope. Source/cast changes and pending casting changes invalidate access to old prepared results. Selection previews remain bounded to ten lines and explicitly retain the entire selected scope. Existing planning/context/character/budget limits remain unchanged; this UX simplification does not make larger paid requests automatically permissible.

## 3. Journey A — first visit, existing voices

1. Choose **Script to Voice** and send `hello`. Read the brief journey and Step 1 upload instruction.
2. Attach one original FDX and send `Use attached script`. Confirm its title and counts. An import response does not execute an accompanying selection/generation instruction; send the next command separately.
3. Reply `single scene`, then specify its number or location/time using the returned list. Alternatively choose `entire script` or `single character` and answer the character-name question. Confirm every displayed spoken line and character. Prefer one short scene for the first live demo.
4. Read the proposed casting shown automatically. If any character already has a chosen voice, provide `CHARACTER: VOICE_ID` or its ElevenLabs link, one per line. Check the updated full list, then reply `confirm cast`. Nothing is assigned by providing the lines alone.
5. Optionally send `audition CHARACTER` to hear a short source excerpt. This is an explicit ElevenLabs request; it is not automatic after casting.
6. When asked about line direction, reply `yes` or `proceed`. Download `direction-package.zip` and open `line-direction.txt` to review it. Preparation may use the guarded Claude allowance; downloading does not. No audio is generated yet.
7. Send `generate` once. Watch the animated generation status; the player and downloads appear automatically when ready within the chat wait. After a disconnect or longer wait, send `status` to resume watching the same job. Play/download the final MP3 and cue sheet; report any wording, ordering, voice or player issues.

## 4. Journey B — generate a new voice

Follow Journey A through selection, then for a missing character:

1. Send `design voice for CHARACTER: DESCRIPTION` with an intentional voice description of at least twenty characters. This requests paid ElevenLabs previews; it is a separate action from audio generation.
2. Listen to the returned candidates. The response shows internal candidate IDs and players/downloads. Step 3 acknowledges unsaved, unexpired candidates so the user is not told to repeatedly request previews.
3. Choose one and send `save voice PREVIEW_ID as NAME` with its exact displayed candidate ID. Saving consumes an account voice slot and stages the resulting speech voice for that character. A preview ID is not a speech voice ID.
4. Double-check the updated casting review and confirm it with its exact phrase. Then optionally audition explicitly and continue at `proceed` (line direction) → `generate` → `status`.

Do not send every candidate to the save command. Do not use an earlier mock voice or mock preview in live mode. Expired/unavailable previews, permission errors and slot limits require the correction described in the response; an uncertain save needs administrator review before another request.

## 5. Journey C — resume or revise saved work

| Intent | User path | What is retained or reset |
|---|---|---|
| Resume after disconnect in the same chat | Send `what next` or `status`. | Current context and durable job progress remain. Help does not submit generation. |
| Reopen a saved script | `scripts` → `use project PROJECT_ID` → select dialogue. | Saved project/revisions/cast/audio remain; active selection, prepared plan and job pointer reset. |
| Inspect/switch revision | `revisions` → `use revision REVISION_ID`. | Active selection/overrides/plan/job pointer reset. Reuse another revision's cast only with `reuse cast from revision SOURCE_REVISION_ID`. |
| Choose different lines | Send another exact selection command, or `clear selection` and choose again. | Cast and earlier audio remain; selection-specific direction and prepared-plan reference reset. |
| Change a voice | Provide `CHARACTER: VOICE_ID` or link → review updated list → `confirm cast` → `proceed`. | Staging clears the prepared requests; old confirmed cast remains until confirmation. Earlier takes and active jobs remain. |
| Change delivery | `direct CHARACTER restrained` (or another supported tag) → `proceed`. | Current implementation replaces the chat's override list with this command's matching lines. Prepared requests reset; old audio remains. |
| Revise a completed chunk | `status` → `regenerate chunk CHUNK_ID with restrained`. | Explicitly authorizes a new take and potentially paid planning/rendering. Byte-identical unaffected chunks reuse saved audio; earlier job remains stored. |

Changing a script, selection, cast or model **does not cancel** already queued provider work. Send `cancel` while the job is still active in the chat if stopping future chunks is intended. Script switching resets the active job pointer, so inspect/cancel before switching. Browsing all historical jobs and resuming a cancelled job through a friendly chat picker remain future work.

## 6. Journey D — wrong model, file or request

| Mistake or missing requirement | Expected response | Clear recovery path |
|---|---|---|
| Selected STV when intending Guide/general chat | `wrong model` (also “I picked/chose/selected the wrong model”) returns exit guidance without importing attachments or calling providers. | Use the model selector at the top of the chat. Choose **Open WebUI Guide**, or an independently configured chat model. No FDX is needed to leave. |
| Sent a text prompt without a script | Explain this workflow, Step 1 and FDX requirement. | Attach FDX; `scripts` to resume; `wrong model` to leave. No inference or speech dispatch. |
| Uploaded PDF/DOCX/audio/other unsupported attachment | Explain the supported original format; reject the request before service import or planning, including mixed supported/unsupported attachments. | Remove other attachments and attach one FDX. Do not silently use an older active script. |
| Attached multiple new FDX files | Explain that only one new script may be imported per message. | Remove extras and resend the intended FDX. Service rejects before creating any new project for that batch. Previously known file IDs are not re-imported. |
| Empty text with attached FDX | Treat submission as `Use attached script`. | Import once, then prompt for selection. OWUI may itself require a short accompanying message. |
| Malformed/unsafe/contentless FDX | Controlled parser error plus upload/current-state guidance. | Obtain a valid Final Draft FDX export; attach it again. Previous active context stays available. No paid call. |
| Uploaded the wrong valid script | `wrong script` / `change script` explains replacement and saved-project choices. | Attach the correct FDX or use `scripts`; no silent deletion or inferred replacement. |
| Selected the wrong lines | `wrong selection`, `change selection` or `clear selection` clears the active selection/overrides/prepared plan. | Choose another scene, character or phrase. Saved cast/audio remain; any existing job needs separate cancellation. |
| Ambiguous scene/character | Explain ambiguity with grounded source choices and current step. | Send an exact source name/scene number. Do not guess or widen scope. |
| No dialogue matches | Show zero selected lines and selection guidance. The empty selection replaces the earlier one. | Broaden/correct the query; no fallback to the whole script or previous spoken scope. |
| Asked to generate too early | Missing selection/cast/prepared-plan requirement is shown. | Complete the displayed step; `plan` and review before `generate`. No automatic casting or synthesis. |
| Used a wrong/unavailable voice or old mock ID | Explain the provider/domain error and current requirement. | `voices` → real account voice → assign again → `plan`. Preview candidates must first be saved. |

`help`, `start`, `what next`, `next`, `hello`, `hi`, “what can you do?” and “how does this work?” are explicit non-inference navigation commands. In the Pipe they bypass attachments, so help/exit still work with a mistaken file attached; help does not import an FDX attached to that message. Remove a rejected attachment before resuming other commands. Other freeform requests with an active script may use Claude to interpret scope; general chat is better sent to a configured chat model.

## 7. Journey E — failure and paid-action recovery

| Outcome | Guidance | Recovery boundary |
|---|---|---|
| Service disconnect/response lost | Explain reconnect and `status`. | Do not repeat a paid action just because the chat missed its response. Help can show current saved context after reconnecting. |
| Authentication/permission/voice-slot error | Report controlled error; retain workflow stage. | Administrator fixes server key/permissions/slots. Never ask for a key in chat. |
| Claude allowance/context limit reached | Show error and current step. | `planner budget` is a local ledger report. Select a shorter scene when indicated; do not automatically raise/reset the allowance. |
| Some chunks failed | Job status and completed-chunk count remain visible. | Fix the cause, then `retry failed` for definitively failed chunks. This may cost credits; successful chunks remain. |
| Provider attempt uncertain | Explicit warning against blind retry. | Administrator checks saved attempts/provider history. Uncertain chunk retry requires explicit API duplicate-billing-risk acceptance; chat does not perform it. |
| Cancellation requested | Explain future scheduling stops; in-flight work may finish. | `status` inspects retained output. Friendly cancelled-job resume is not implemented; use administrator assistance. |
| Voice design/save/audition uncertain | Controlled action-state error; no automatic duplicate. | Administrator reviews saved action/provider account before requesting another action. Do not substitute a new action key to evade uncertainty. |

### Visible progress during generation

The v0.3.0 Pipe uses OWUI's existing animated status label while a request is active: “Working on your Script to Voice request…”, “Generating audio… X of Y parts ready”, then download/player preparation and a terminal status. Counts reflect persisted completed parts; they are not invented percentages or a prediction of completion time. The label is the pinned UI's shimmer animation, rather than a custom circular spinner. No core frontend/Guide extension is changed.

After generation/retry/revised-take queuing, browser requests with a usable injected event emitter watch the specific owner-scoped saved job. The Pipe polls the private read-only result route every two seconds, for up to three minutes, and returns completed audio/cue artifacts through the existing OWUI file adapter. No further chat planning, render submission, paid retry or provider generation is triggered by polling. Completed/failed/cancelled results close the indicator; failures describe the recovery requirement instead of claiming success. Status is also closed after request errors, rejected attachments and normal responses.

Longer jobs continue in the background when the chat wait ends. A lost event channel/progress connection gives a saved-job recovery message. `status` resumes watching an active job; without an emitter (for example an ordinary API client) the Pipe returns the queued result immediately with manual-status guidance. Background title/tag tasks still exit before all progress/work. A stopped chat response or browser disconnect ends the UI wait, **not** the durable job: to stop future audio parts, stop waiting and send `cancel`. An accepted provider request may finish. This preserves the existing cancellation/uncertainty behavior and usage limits.

Technical contract: chat render replies may include `job` metadata (`id`, `status`, `completed`, `total`, `cancellation_requested`). `GET /v1/render-jobs/{id}/result` returns that metadata, controlled display text and terminal artifacts after owner authentication; it never dispatches speech. The native status contract was checked against pinned [ResponseMessage](https://github.com/open-webui/open-webui/blob/v0.11.0/src/lib/components/chat/Messages/ResponseMessage.svelte), [StatusItem](https://github.com/open-webui/open-webui/blob/v0.11.0/src/lib/components/chat/Messages/ResponseMessage/StatusHistory/StatusItem.svelte) and the already inspected event-emitter backend. Actual browser animation and automatic delivery remain untested under the user's standing instruction.

Earlier historical mock audio can still be downloaded, but cannot establish current live synthesis quality.

## 8. Cost and source guarantees in the journey

- Help, exit, scene/character browsing, saved-project listing, a saved casting review and status do not call Claude or synthesize speech. Voice catalog, staged IDs and confirmation can perform ElevenLabs read-only lookups.
- Freeform interpretation, automatic missing-role proposals after selection, preparing/refreshing a casting review, uncached direction planning and revised-take planning may use the guarded Claude allowance. Existing configured caps and reservations are unchanged.
- Voice design, explicit auditions, `generate`, revised takes and eligible retries are deliberate paid operations. No example or help response executes those commands for the user.
- The character cap is a request envelope, not a currency or exact provider-credit limit. Actual ElevenLabs account usage and audio quality remain user validation items.
- The source original is retained. Selection, casting, direction and request compilation continue to preserve original wording, order and character identity. Navigation never changes the source text.

## 9. Implementation map and review boundaries

| File | Change |
|---|---|
| `agent/src/script_to_voice/service/journey.py` | Read-only stage derivation, introduction/exit wording, three-choice selection menu and deterministic scene/character follow-up resolution. |
| `agent/src/script_to_voice/service/workflow.py` | Chat-only recovery envelope; navigation and source browsing; prepared-plan reference/review gate; source/selection invalidation; cast summary; single-new-file import rule. Typed domain API routes retain their existing errors. |
| `agent/src/script_to_voice/service/cast_review.py`, `casting/service.py`, `casting/design.py` | Persisted unconfirmed casting, voice-ID/link mapping, simple confirmation with internal version/scope checks, all-or-nothing assignment and separate provider-save/character-confirm steps. |
| `openwebui/functions/script_to_voice_pipe.py`, workflow job-result route | v0.3.0 native animated status events, bounded read-only monitoring and automatic player/download return; API/emitter/disconnect fallback. |
| `openwebui/functions/script_to_voice_pipe.py` | v0.2.0: attachment-only prompt, explicit wrong-format recovery, help/exit bypass of attachments, transport-recovery wording. Installed Function source must be updated. |
| `tests/script_to_voice/test_journey.py`, `test_jobs.py` | Added offline navigation/review-gate/empty-scope regression definitions; updated three job scenarios to prepare a plan before generation. Not executed. |

No core OWUI frontend changes, Guide edits, schema migration, provider/model change, credential change, budget reset or historical-data deletion. Session fields are additive. New valid imports no longer carry the preceding script's direction or active job pointer. The review snapshot remains the historical pre-live/pre-guidance baseline; these changes are a later delta, especially review-guide P04 and P16. Existing automated workflows that sent `generate` without `plan` must add the review step before they can pass again.

Known limits: state guidance does not enumerate every historical job; service failure uses the Pipe's fallback wording; file-read failures may require administrator inspection; invalid imports can leave an empty project record because project creation precedes parsing. Model selection alone cannot trigger chat guidance. Concurrent chat updates retain the existing optimistic-conflict behavior. These paths require the acceptance checks below.

## 10. Acceptance checklist — all pending, not executed

Deployment: the local STV service/worker were rebuilt and recreated, and the stored STV Function was updated to v0.2.0 through its supported installer. Compose startup health and a successful installation are infrastructure results, not workflow acceptance. The Guide and data volumes were retained.

The user explicitly retained ownership of testing after live activation. No tests, provider validation, paid requests or browser workflow were run for this UX change. Perform provider-free cases first; use one short dummy-FDX scene for paid steps.

| Check | Expected evidence | Status |
|---|---|---|
| Fresh chat: hello/help/empty prompt | Step 1; no planner reservation or voice action. | Pending |
| Wrong model, including with unsupported attachment | Clear model-selector exit; no import/inference/speech. Guide remains usable. | Pending |
| Unsupported/mixed attachments, multiple new FDX | Actionable message; active script unchanged; no paid action. | Pending |
| Attachment-only and duplicate FDX | Import correct source once; Step 2. Help with attached FDX does not import it. | Pending |
| Malformed/unsafe FDX | Parser failure; previous context retained; no generation. | Pending |
| Browse scenes/characters, exact and ambiguous selection | Grounded options; ordered exact preview; no inference for deterministic resolution. Successful selections may separately prepare capped casting proposals. | Pending |
| Three Step 2 choices and follow-ups | Entire script; scene number/location-time description; character name/alias; ambiguity, unknown name, scope switching and reload/help while awaiting detail. No old-scope fallback or speech; casting proposals use separate allowance rules. | Pending — regression definition added, not run |
| Step 3 default proposals, IDs/links, confirmation | Missing list → actual proposals → double-check → existing-cast question; `confirm cast` applies the latest review; no assignment on proposal/mapping/plain yes; stale review rejected; entire group blocked on one bad voice. | Pending — regression definitions added, not run |
| Generated save and earlier-revision reuse | Saving a voice/reusing assignments stages a review; explicit confirmation applies cast. Save deduplicates; no automatic audition. | Pending |
| Step 4 confirmation and download review | Step accepts yes/proceed; chat has no character/scene summary; one ZIP contains readable full direction, README and request JSON; all 600 source lines appear once/in order; repeated downloads/yes cause no fresh inference or audio. | Pending — regression definitions updated, not run |
| Zero matches / wrong-selection reset | Step 2, no previous-scope synthesis; cast/audio retained. | Pending |
| Missing role and premature generate | Step 3 or review requirement; zero speech dispatch. | Pending |
| Existing voice, design previews, save, audition | Real voice identity; one chosen candidate; slot/credit usage recorded separately. | Pending — live |
| Plan → generate; direction/cast/selection changes | Stage 4/5 correct; stale plan blocked; generate uses saved plan. | Pending |
| Multi-chunk progress, playback and download | Polling, MP3/cue files, exact source coverage, audible identity/order. | Pending — live |
| Animated generation and automatic delivery | Browser with emitter: active label, real part counts, terminal player/downloads; no second render submission. Failure/cancel/error closes indicator; timeout/disconnect preserves job; API without emitter returns promptly. | Pending — mocked test definitions added, not run |
| Failure, uncertainty, retry and cancel | Outcome-specific guidance; no blind duplicate; completed audio retained. | Pending |
| Disconnect, script/revision switch and prior mock project | Correct current context and explicit job-pointer limitations; mock IDs blocked live. | Pending |
| Automated mock regression suite and Guide checks | New journey tests and adjusted job fixtures are present; run relevant/full suites when testing is authorized. | Pending — not run |

Record feedback, exact failing step and sanitized error text in `progress.md`; do not paste credentials. Live results must be recorded separately from mock checks.
