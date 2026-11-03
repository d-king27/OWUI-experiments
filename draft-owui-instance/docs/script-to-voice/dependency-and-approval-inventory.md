# Script to Voice: dependency and approval inventory

2 November 2026. Source/configuration inventory for organisational review. This is not an approval, licence assessment, vulnerability scan or complete container software bill of materials (SBOM).

## Loading/progress change

**No new third-party dependency, downloaded spinner component, browser extension or UI framework was introduced by this change.**

- The animated status text is part of the existing pinned Open WebUI v0.11.0 interface.
- The locally written Script to Voice Pipe emits OWUI native status events and polls the private STV service for persisted progress.
- Polling reuses the existing `httpx` dependency plus Python standard-library `asyncio` and URL helpers.
- The service's new job-result route uses the already installed FastAPI/database code.
- No npm package, CDN script, analytics service or hosted progress service was added. The recent ZIP-download feature uses Python's built-in `zipfile`; voice links are normal ElevenLabs HTTPS links.

This change updated application source and the installed STV Function; it did not add package requirements or change package pins. Rebuilding the service installed its existing frozen dependencies. The audio worker and Guide were not recreated for this progress deployment.

## Custom integration and browser extensions

| Component | Status | Approval relevance |
|---|---|---|
| **Script to Voice OWUI Function / Pipe** | Locally written server-side code installed using OWUI's supported Function API | This is a custom extension inside OWUI. An organisation may require approval of Functions/custom server code even though it is not a third-party marketplace plugin. |
| **STV private service and worker** | Locally written Python application in Docker; owns source parsing, casting, planning, jobs and assembly | Application/deployment/source review applies. Service and worker share a separate persistent data volume. |
| **Open WebUI Guide Bridge** | Existing, separate browser-extension source in `openwebui/guide-extension`; preserved | STV and its progress indicator do not require it. Its browser installation/policy approval is independent; this inventory does not audit which extensions are installed in a user's browser. |
| **ElevenLabs MCP** | Not used by STV; STV 16 excluded | No ElevenLabs MCP investigation, installation or connection is part of this feature. |
| **Anthropic/ElevenLabs SDK packages** | Not used by the STV adapters | Both adapters use direct HTTP requests through `httpx`. Third-party services themselves still need review. |

The Function does not declare auto-installable frontmatter requirements. Compose has `ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS=false`; application packages are installed through the service build instead.

## Direct application dependencies

These seven pinned packages were added for the broader STV feature, before the latest progress change. They are declared in `pyproject.toml` under the `stv` optional dependency group.

| Package | Declared version | Use |
|---|---|---|
| `pydantic` | 2.12.3 | Validate immutable source, selection, casting, direction and request contracts. |
| `fastapi` | 0.120.4 | Private service/API. |
| `httpx` | 0.28.1 | Direct Anthropic/ElevenLabs HTTP calls and Pipe-to-service requests/polling. |
| `defusedxml` | 0.7.1 | Parse original FDX XML. |
| `python-multipart` | 0.0.20 | File/multipart support used by the integration. |
| `uvicorn` | 0.38.0 | Run the private API service. |
| `imageio-ffmpeg` | 0.6.0 | Locate/provide an FFmpeg executable for audio decoding/assembly/MP3 encoding. |

`PyYAML>=6.0,<7` was already a project dependency for the existing Guide; the current lock resolves 6.0.3. It was not added for the spinner.

The dependencies above bring transitive packages, recorded in `uv.lock`, including Starlette, AnyIO, pydantic-core, httpcore, h11, certifi and typing support. The seven rows are **not** a complete transitive inventory or a list of everything inside the OWUI/Python container images.

**FFmpeg deserves a separate binary review:** assembly executes the binary returned by `imageio_ffmpeg.get_ffmpeg_exe()` and uses its MP3 encoder. Review the actual distributed executable, its components/build and applicable terms in addition to the Python wrapper. This document does not establish its licence/compliance status.

## Runtime, build and development components

| Component | Current source declaration | Scope |
|---|---|---|
| Open WebUI image | `ghcr.io/open-webui/open-webui`, default tag `v0.11.0` | Existing UI/server platform; has its own dependencies. |
| STV Python image | `python:3.12.12-slim-bookworm` | STV service/worker runtime and Debian base components. |
| Docker / Compose | Existing local deployment tooling | Runs the application, private network and persistent volumes. |
| `uv` | 0.9.7 in the STV Dockerfile | Dependency installation from the frozen lockfile. |
| pip / setuptools | pip from the Python image; project build requires `setuptools>=68` | Build tooling; this inventory does not pin/audit every build-tool version. |
| `pytest` | 8.4.2 in the optional `test` extra | Test tooling; not selected by the production Docker build. |
| Node / GitHub Actions | Node 22, checkout@v4, setup-python@v5, setup-node@v4 in the mock CI workflow | Development/CI, not required by the STV Python runtime. CI approval is separate from deployment approval. |

Builds obtain base images and Python packages from their configured registries. `uv.lock` records resolved Python package sources/hashes; it does not cover every OS, OWUI or FFmpeg component. The current source does not constitute a complete reproducible-build or supply-chain approval package.

## External services and data flow

| Service | Why it is used | Data involved |
|---|---|---|
| **Anthropic / Claude API** | Interpret freeform selections, propose casting and infer bounded line direction | Relevant user requests, source metadata, selected/context excerpts and casting information, depending on the task. |
| **ElevenLabs API** | Read account voices/model capabilities; design/save voices; audition and generate dialogue audio | Voice descriptions/preview text and selected source wording with voice IDs/delivery tags; generated audio/metadata returns to the server. |
| **ElevenLabs website** | User clicks a voice ID to inspect it | The voice ID in the link; the browser's normal ElevenLabs session/access applies. No server API key is placed in that URL. |

Keys stay in the server environment. Progress polling stays between OWUI and the private STV service; it does not add another external service or dispatch extra generation. The original FDX and persisted workflow data are stored locally; relevant content still leaves the environment for the API tasks described above. This is therefore not a wholly offline feature.

## Evidence and outstanding review

Read from current source: `pyproject.toml`, `uv.lock`, `docker/script-to-voice.Dockerfile`, `docker-compose.yml`, Pipe, provider/assembly code, existing Guide extension manifest and `.github/workflows/script-to-voice.yml`. Compared the tracked pre-STV project declaration: PyYAML was its only direct application dependency. No credentials were read or displayed for this inventory.

The organisation can use this list to scope approval of custom OWUI Functions, external AI data processing, direct/transitive Python dependencies, the FFmpeg executable, container/base-image components and build/CI tooling. A complete SBOM, exact binary/build licence review, vulnerability assessment and organisational sign-off have **not** been performed. No tests, provider calls, runtime installation or deployment changes were made to produce this document.
