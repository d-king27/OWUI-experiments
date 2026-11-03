# Direct provider contract snapshot

Local activation update: direct ElevenLabs is enabled for user-led testing (`STV_MOCK=false`, `STV_LIVE_ENABLED=true`). Tests and validation scripts were explicitly not run for this switch. The direct adapter now rejects earlier mock voice/preview ID prefixes before transport. Template/CI mock defaults and historical fixture results below are retained; see the live-elevenlabs-handoff.md for the manual test steps.

Retrieved 2026-11-02. The executable sanitized HTTP fixtures are `tests/script_to_voice/test_provider.py`. These are representative contract fixtures, not captured live account results.

- GET `/v1/models`: check explicit `eleven_v4` and `can_do_text_to_speech` before speech; no fallback.
- GET `/v2/voices`: `page_size=100`, optional `next_page_token`; response voices/has_more/next_page_token.
- GET `/v1/voices/{voice_id}`: confirm availability before cast/render.
- POST `/v1/text-to-voice/design`: `model_id=eleven_ttv_v3`, `voice_description` 20–1000, `text` 100–1000; response previews with `generated_voice_id`, `audio_base_64`, `media_type`. Up to three candidates accepted locally.
- POST `/v1/text-to-voice`: `generated_voice_id`, `voice_name`, `voice_description`; response saved `voice_id`, never interchangeable with preview ID.
- POST `/v1/text-to-dialogue/with-timestamps?output_format=mp3_44100_128`: only model_id and ordered text/voice inputs. 2000 Unicode code points and 10 distinct voices maximum. Code-point behavior still requires live confirmation with non-BMP text. No optional controls, IPA, dictionaries or continuity until verified.
- Response: bounded audio_base64 decoded server-side; preserve raw alignments/voice_segments and validate input index/voice identity. No fabricated timing if absent.
- Keys read at execution, only in xi-api-key transport header. Typed safe errors; no raw response or headers logged. 401/403 stop; 429 uses Retry-After; 5xx bounded worker policy; paid read/write timeouts are ambiguous and never automatically repeated.

Sources: [models](https://elevenlabs.io/docs/overview/models), [timestamped dialogue](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert-with-timestamps), [design](https://elevenlabs.io/docs/api-reference/text-to-voice/design), [save](https://elevenlabs.io/docs/api-reference/text-to-voice/create), [voice search](https://elevenlabs.io/docs/api-reference/voices/search).

Mocks are default. Live dispatch additionally requires `STV_LIVE_ENABLED=true` and explicit plan authorization within a configured character cap. `STV_LIVE_TESTS` is separately reserved for opt-in tests. A configured key alone cannot spend credits. Account capabilities, quality, accent/PVC behavior and actual costs are unverified.
