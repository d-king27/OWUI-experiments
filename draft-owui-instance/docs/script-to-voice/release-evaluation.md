# Release evaluation — 2 November 2026

Status: mocked workflow demonstrated; production release acceptance remains open.

Latest generation-progress delta: Pipe v0.3.0 uses native animated OWUI status and bounded read-only job-result monitoring, returning player/downloads automatically when ready. An authenticated owned result route supplies real part counts, terminal outcomes and artifacts. Missing/broken emitter, long jobs and disconnects retain saved-job/status recovery; polling never dispatches speech. Static pinned frontend/backend contracts were inspected and new offline regression definitions added, but **no tests or provider/browser validation run**. Actual animation, automatic delivery and fallback/cancellation acceptance remain open. Service/Function-only deployment avoids restarting the current audio worker.

Latest Step 4 UX delta: “Line direction” accepts yes/proceed, then offers a single direction-package ZIP with readable full direction, README and optional technical requests. Automatic character/scene summaries were removed at user request. Step 5 asks the user to review the download then separately reply generate. Re-download uses saved data without fresh inference. Internal preparation/cast/budget/generation checks and bounded selection previews remain. Updated, unexecuted regression definitions cover the 600-line ZIP contents/order, deterministic archive output and retained explicit pagination. No tests or provider validation were run for this delta.

Latest Step 3 delta: default missing-role proposals, voice-ID/link mapping lines and simple `confirm cast` confirmation before conversational assignments. No user-facing code is required; internal scope/version checks protect the current review. Generated voice save and earlier-revision chat reuse stage changes rather than assigning immediately. All proposed voices are validated before one cast-version commit. Default suggestions may use existing capped Claude credit; no budget limits changed. New cast-review tests and affected journey/job/design fixtures are present but **not run**. No provider validation or paid calls were initiated; user acceptance remains pending. See the current journey contract.

Subsequent UX change: six-stage state-derived guidance, help/exit/source-browsing commands, wrong-file/selection recovery and a required current prepared-plan gate before chat generation. See guided-user-journeys.md for the transition contract and pending acceptance matrix. Offline regression definitions/affected job fixtures were updated, but **no tests or provider checks were run** under the user's no-testing instruction. Historical pass counts below do not cover this delta.

Latest configuration change: real ElevenLabs enabled for user-led dummy-FDX testing; mock/live flags changed locally and a mock-ID rejection guard added to the adapter. No tests, validation scripts or provider operations were run for this activation. All prior pass counts apply to their earlier code snapshot; live audio acceptance remains open. See live-elevenlabs-handoff.md.

## Verified

- OWUI runtime reports 0.11.0. Both Script to Voice and the existing Guide appear in model results and return successful API responses. Installer creates/enables once, explicit updates work, repeat installation is unchanged.
- Through OWUI API: FDX original upload/import, complete selection, all three roles, existing catalog voices, designed voice previews/chosen save/audition, inspectable plan, two-chunk durable render, polling, registered MP3/cue artifacts, downloads and HTTP 206 ranges.
- In actual browser: select Script to Voice beside Guide; attach stored original FDX; import; preview all five dialogue lines; assign all three characters including one-line role; generate; retrieve completed two-chunk job; load native audio player and click Play (control changes to Pause). Audio is a synthetic mock tone.
- Final local Python suite: **100 tests passed** (9.291s), including assembly-only recovery and explicit revision reconciliation. Guide extension suite: **28 passed**. CI workflow added but not executed remotely.
- Full-script deterministic fixture: 600 dialogue lines, 30 numbered scenes, 12 distinct roles, 60 bounded chunks, complete ordered coverage with no extra lines. Separate durable job tests prove successful-chunk retention across repository restart, duplicate submission handling, 401 stop, rate-limit backoff/recovery, cancellation, interrupted-request ambiguity, budget exhaustion, targeted revised take reuse and assembly-only recovery without new provider requests.
- Source defects addressed by tests: no empty/null-to-whole-script fallback; exact selected IDs govern speech; linked parentheticals retained; annotation-only direction; deterministic semantic hashes; safe XML rejection; authentication errors do not trigger recursive splitting.

## Not verified live

Text-planning update: native Claude Haiku 5.5 now passes the live text-only OWUI acceptance script on the synthetic fixture (intent, refinement, voice proposals, direction, plan cache, inspection and no speech jobs). Total test usage including failed probes: 19,832 input/962 output tokens across 10 calls, estimated $0.002469; conservative allowance reservations $0.50/$1. This supersedes older statements below that real inference is unconfigured/unperformed. It does not establish live ElevenLabs synthesis/design/audio quality, account billing balance or arbitrary screenplay planning quality.

Update 2 November 2026: read-only account requests now passed (GET subscription/models/voices, all 200). Creator account reports 233,340 remaining from 260,389 total and 27,049 used, reset 8 November 08:18:41 UTC; usage extension disabled; custom slots 12/30. V4 speech capability is listed and catalog lookup returns 57 voices. This supersedes the earlier missing-key/account-check status below. The key variable was normalized to ELEVENLABS_API_KEY. Actual speech/design requests, endpoint entitlement and quality remain unverified; mock and paid-dispatch mode settings remain unchanged.

No ElevenLabs account calls, real speech/design generation, model entitlement check, real text inference, listening scores or measured monetary costs. User approved a £5 total live-test cap, but the server key is absent and text-provider selection was deferred. Mock tones do not establish wording, identity, direction, pronunciation or naturalness in real audio.

The service remains in mock mode and paid dispatch remains disabled. Agree a current account-specific credit allowance within £5 before enabling live calls. Test real model/endpoint availability first; never fall back silently. Run 6–10 short scenes and record the effective payload, voice IDs/model, latency, usage and human scores once configured.

## Remaining acceptance and implementation gaps

- Authenticated multi-user OWUI deployment, browser cross-user downloads and expired/deleted OWUI files need their own environment checks. Internal owner-isolation tests pass; auth-disabled local mode is not proof of that deployment.
- Real-provider schema/Unicode-count behavior, accent/PVC behavior, optional model controls, IPA/dictionaries and continuity remain capability-gated. Current compilation rejects pronunciation substitutions; a persisted pronunciation glossary is not yet implemented.
- Cast persists across selections. Explicit cross-revision reconciliation now has domain/API/chat support and local tests for exact identity, target override preservation, foreign-owner and stale-version rejection. Actual browser revision-switch/reuse remains a separate check; fuzzy names are intentionally not merged.
- Planner adapter has bounded structured requests and versioned direction reuse, but dedicated usage accounting and live quality/repair/cache acceptance remain open. Detailed feature-change document records the deferred provider decision.
- Generated voice expiry, permissions and slot failures have safe domain/provider errors; a broader live matrix remains pending. Auditions are explicitly requested and mean artifact generation, not human approval.
- Cancellation stops later scheduling; transport abort of an already accepted provider request is not implemented. That request may still incur usage.
- Browser generated-voice/retry/restart flows were exercised through OWUI API plus domain tests, not every action repeated manually in the UI. Full-script audio production/restart with realistic speech remains unperformed.
- Remote CI, representative live listening, operational backup/restore rehearsal and upgrade checks are not passed.

Keep these gates open in progress.md. STV 16 remains deferred and no ElevenLabs MCP component was investigated or added.
