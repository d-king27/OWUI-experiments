# Direct ElevenLabs activation — manual test handoff

2 November 2026. Requested change: use real ElevenLabs calls in the local application; the user will test with a dummy FDX. **No tests, validation scripts or provider operations were run for this change.** Build/recreation applies configuration; it is not a passing E2E result.

## Changes

- Local `.env`: `STV_MOCK=false`, `STV_LIVE_ENABLED=true`, `STV_LIVE_TESTS=false`. Existing server-side `ELEVENLABS_API_KEY` is retained and never printed.
- The existing service factory now selects `ElevenLabs` rather than `FakeVoiceProvider`. Catalog/lookup, design preview/save, auditions and dialogue use the existing direct REST adapter.
- `providers/elevenlabs.py` rejects IDs prefixed `mock-` or `preview-` before lookup, save or render transport. These are the earlier fake provider's ID forms. They must not enter a live request from an old mock cast/plan/preview.
- Native Claude configuration, $1 planner allowance, prior reservations, source fidelity/chunk limits, stored projects and audio are preserved. No new job is submitted by this change.
- Fake providers remain as offline test fixtures. Templates and CI retain mock-safe defaults; the local environment is explicitly live. No fallback to test tones occurs for a live provider error.

`STV_LIVE_TESTS=false` does **not** disable manual `generate`, `audition` or `design` actions: `STV_LIVE_ENABLED=true` permits those real operations. It simply leaves the separate opt-in live-test setting off.

## Your dummy-FDX test

The later [guided UX contract](C:/Users/Dan/Documents/Codex/OWUI-experiments/draft-owui-instance/docs/script-to-voice/guided-user-journeys.md) adds explicit help/current-step and mistake-recovery paths. It is also untested. Send `hello` for upload guidance, `what next` to resume, or `wrong model` to leave. `plan` is now required before chat `generate`; changing selection, cast or direction requires a new plan review.

1. Start a new OWUI chat with **Script to Voice**. Attach your dummy FDX as a new import/project; avoid resuming a previous mock job.
2. Select a short scene or a few lines. Use `voices` or `refresh voices` to list real account voices.
3. Check the automatically proposed character-to-voice list. Provide `CHARACTER: REAL_VOICE_ID` or an ElevenLabs link for any roles already cast. Double-check the updated full list and reply `confirm cast` before planning. No code is needed. `cast CHARACTER as REAL_VOICE_ID` now stages a change too. `mock-1` and earlier mock-designed IDs are invalid in live mode.
4. When Step 4 asks about line direction, reply `yes` or `proceed`. Download **direction-package.zip** and review **line-direction.txt** inside it. Chat does not list scenes/characters or individual delivery notes. README and optional technical JSON are included. Preparation makes no ElevenLabs speech request; uncached direction can use Claude. `direction package` or a repeat yes retrieves it without new inference. The older `plan` command remains supported.
5. Use `generate` once. The browser should show animated generation status and real completed-part counts, then the player/downloads automatically within the bounded chat wait. Use `status` to resume if a longer job is still running or after reconnecting. Check wording/order/voice identity, playback and download. This progress UX remains untested; do not resend generation to recover a lost chat response.
6. If testing Voice Design, explicitly request fresh live previews, select one, save it, confirm its casting review, then audition. Saving creates/saves the account voice but no longer assigns a character automatically. Old mock previews and saved mock voice IDs must not be reused.

Existing completed mock audio remains available as historical data and will still sound like a tone. Enabling the live provider does not convert old files into speech or overwrite those takes. Previous character assignments should be replaced with real account voices for new live work.

## Limits and pending acceptance

Chunking stays at 2,000 rendered code points/10 distinct voices, with the existing job character cap (default 20,000). Audition/preview project caps remain in place. These are character/action bounds, **not a complete ElevenLabs credit or currency cap**. Rendering, auditions and preview generation consume account credits; saving a voice can use a custom voice slot. The previously discussed live-test spending scope has not been expanded by this change.

No live synthesis, Voice Design, listening, actual credit delta or failure-recovery result has been marked passed. Earlier model/catalog/account reads and mocked E2E results remain historical evidence. User testing supplies the next live evidence.

Support scripts such as `check-stv-workflow.py` and `check-stv-text-planning.py` contain mock voice assumptions. Do not run them unchanged against this live voice-provider environment; use an isolated mock configuration for those checks. No automated script was executed here.

To disable paid ElevenLabs actions again, set `STV_LIVE_ENABLED=false` and recreate the service/worker while retaining volumes. Selecting `STV_MOCK=true` is a separate switch back to fake voice behavior. Do not delete volumes or clear planner reservations.

## Review-document baseline

The technical review guide and its fingerprint manifest were captured before this activation. Keep `technical-review-snapshot.json` as that historical reference; the live-ID guard is a subsequent source change. The snapshot is not regenerated to imply that this new, untested code was covered by earlier tests. Source links/line numbers in the old guide may need rechecking during review, especially the ElevenLabs adapter.
