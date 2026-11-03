# Integration contracts — STV 01

Checked 2 November 2026. The specification and both copies of its tickets were read in full. They are proposed design inputs; the user's direct request controls scope. STV 16 is excluded.

## Destination and decision

No applicable AGENTS.md was found in the destination or its ancestors. The pre-existing working tree contains deleted root files and an untracked `draft-owui-instance/` replacement directory. Preserve this relocation; do not stage, reset or revert it. The Python project definition is at the application root, not `agent/pyproject.toml` as stated in the plan. Keep the existing Guide package, Function, installer and browser extension intact.

Adopt a separate Python domain package, private FastAPI service and single durable worker, with SQLite WAL and artifacts on a new named volume. No public service port. The Pipe supplies authenticated server identity using a service token; object lookup additionally scopes by owner. Original source, search normalization and rendered speech remain distinct. External content is data, never operational instructions.

Compose and the nonsecret `.env` values pin `v0.11.0`, port 3000, authentication false. The existing named OWUI volume is `howto-agent-open-webui-data`. Docker was stopped at initial inspection; actual running image and browser compatibility remain pending. No volumes were reset. Local authentication-disabled mode is not evidence of multi-user security.

## Version-specific OWUI boundary

Source: [v0.11.0 functions.py](https://github.com/open-webui/open-webui/blob/v0.11.0/backend/open_webui/functions.py), [file routes](https://github.com/open-webui/open-webui/blob/v0.11.0/backend/open_webui/routers/files.py), [file models](https://github.com/open-webui/open-webui/blob/v0.11.0/backend/open_webui/models/files.py). Retrieved source inspected, not inferred from latest docs.

- Active single Pipe functions become model entries with the Function ID/name. Register `script_to_voice` / `Script to Voice`; retain `open_webui_guide`.
- `generate_function_chat_completion` filters injected parameters by the Pipe signature. Available: `__user__` (server UserModel dump), `__request__`, `__metadata__`, `__files__`, `__chat_id__`, `__task__`, and optional `__event_emitter__`. Metadata contains unwrapped `user_prompt`. Background task requests must return before paid actions.
- Read original records using async `Files.get_file_by_id(id)` and check `file.user_id` against the injected user before `Storage.get_file(file.path)`. Initial STV sharing policy is owner-only, stricter than OWUI admin/share access. Never use retrieval excerpts or user-supplied filesystem paths.
- Register outputs with async `upload_file_handler(request, file=UploadFile(...), metadata=..., process=False, process_in_background=False, user=UserModel(...), background_tasks=None, db=None)`. This uses supported backend storage/model routines; no direct OWUI database writes.
- Browser content URL is `/api/v1/files/{id}/content`; downloads append `?attachment=true`. The route authenticates and checks owner/admin/share access, then returns FileResponse with stored MIME. Range/playback must be tested in the actual browser. Do not import `get_file_content_by_id` directly: that Python name is redefined for a later route in this version.
- Runtime correction: v0.11.0 `src/lib/components/chat/Messages/Markdown/HTMLToken.svelte` reads audio source from the tag **body**. Use a complete block: `<div>\n<audio>/api/v1/files/ID/content</audio>\n</div>`. Without the div, inline tokenization separates the audio tags and displays literal text. Browser verified native player loaded 1-second test audio and changed from Play to Pause on click. No core UI changes or extension needed.
- Upload preserves original bytes before extraction. With `process=False`, extension extraction filtering is bypassed. Normal chat upload extension configuration and FDX extraction failures require runtime verification. Never claim RAG extraction is the original XML.
- Events exist only with session/chat/message metadata. Poll persisted jobs on `status`; do not assume background push or emit tool calls.

Later v0.3.0 progress delta: the Pipe now emits optional native `status` events with `description` and `done`, whose pinned `StatusItem.svelte` applies its shimmer animation while unfinished. It holds an active browser response and polls the private owned job-result endpoint every two seconds for at most 180 seconds, returning player/downloads on completion. This is bounded read-only monitoring, not asynchronous push after the Pipe has returned; API/missing-emitter/timeout/disconnect fallback still uses saved jobs and `status`. No tool calls, core UI changes or extra provider requests. Native frontend source inspected; actual new browser animation remains unverified.

The existing installer checks admin access, normalizes source, creates/enables once, and refuses replacement without `-Update`. Reuse this behavior for STV with its own defaults.

## Provider verification

[Models](https://elevenlabs.io/docs/overview/models) explicitly lists `eleven_v4` and multi-speaker support. [Timestamped dialogue](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert-with-timestamps) documents the endpoint, default v3 model, 2,000 total rendered characters and 10 distinct voices. Explicitly send v4. Keep optional settings, IPA, dictionaries and continuity disabled until independently validated; a general model listing is not endpoint/account entitlement.

[Voice Design](https://elevenlabs.io/docs/api-reference/text-to-voice/design) documents separate `eleven_ttv_v3`/`eleven_multilingual_ttv_v2`, description 20–1,000 characters, preview text 100–1,000, and `generated_voice_id`. Saving returns a different speech `voice_id`. The linked v4-specific guide was unavailable through the documentation reader; do not treat its detailed control claims as verified.

No account request or paid generation has occurred. Before live execution, require server-side key, `/v1/models` availability check, explicit live mode and a user-approved character/preview budget. No silent model fallback. Planner choice remains pending: support a separately configured OpenAI-compatible endpoint, never the deterministic hello-world server or this Pipe itself.

## Gate evidence

Baseline: `uv run ... python -m unittest discover -s tests -q`: **69 passed**. Static pinned-source APIs are concrete above. Runtime file upload, model installation, authenticated range playback and browser behavior remain explicit release gates, not passed checks.
