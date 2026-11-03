# Open WebUI How-To Agent

An experimental development environment for building a conversational process-guidance agent on top of Open WebUI.

The project is intentionally small and modular. Open WebUI provides the interaction layer, while process orchestration, prompts, process definitions, and supporting knowledge remain source controlled and independent of Open WebUI internals.

## Current status

The repository foundation and a working local Open WebUI baseline are in place. A deterministic development provider exposes a `hello-world` model so the chat UI can be tested without credentials or a real LLM. The framework-independent agent package can load the guide content, navigate the example process, answer the required onboarding questions, and return validated UI directives. A source-controlled Pipe adapter now exposes that behaviour as **Open WebUI Guide**, but it is not installed into the Compose baseline yet.

The proof-of-concept implementation now includes the selectable guide, persistent **Getting started** CTA, UI highlighting, consent-gated demonstration, browser contracts, and operational runbook. Its design and trade-offs are documented in [docs/howto-agent-proposal.md](docs/howto-agent-proposal.md).

For a concise, presentation-ready account of the implementation and its extension-free production path, see the [project debrief](docs/project-debrief.md).

LLM-backed task understanding and model recommendations are deferred to the [Anthropic-backed task-planning proposal](docs/next-phase-anthropic-task-planning.md). The current Guide uses deterministic Markdown section lookup; it does not run the draft system prompt or call an AI model.

## Architecture

```text
Browser
   |
   v
Open WebUI
   |
   v
Hello World provider

Later:

Open WebUI -> real LLM provider

Future:

Open WebUI
   |
   v
How-To Agent adapter
   |
   +-- Process engine
   +-- Knowledge
   +-- Tools and APIs
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `agent/` | Framework-independent agent and process-domain logic |
| `openwebui/` | Open WebUI infrastructure, Function adapter, and Guide Bridge extension |
| `knowledge/` | Supporting process documentation, kept separate from process structure |
| `scripts/` | Local development helper commands |
| `tests/` | Automated tests for the agent package |
| `docs/` | Architecture decisions and the experiment roadmap |

## Getting started

Requirements:

- Docker Desktop with Linux containers
- Docker Compose v2 or later

Create local configuration in PowerShell:

```powershell
Copy-Item .env.example .env
$secretBytes = [byte[]]::new(32)
[Security.Cryptography.RandomNumberGenerator]::Fill($secretBytes)
[Convert]::ToHexString($secretBytes).ToLowerInvariant()
```

Replace the placeholder `WEBUI_SECRET_KEY` in `.env` with the generated value, then start the baseline:

```powershell
docker compose up -d
```

Open <http://localhost:3000>, select the `hello-world` model if it is not already selected, and send any message. The response should be:

```text
Hello, world! The baseline chat connection is working.
```

## Install the Open WebUI Guide

An Open WebUI API key, OpenAI key, paid account, and actual LLM are not required. The primary PoC path is to install the source-controlled Pipe manually through the local Open WebUI administrator interface:

1. Open [openwebui/functions/howto_pipe.py](openwebui/functions/howto_pipe.py) and copy the entire file.
2. In Open WebUI, open **Admin Panel → Functions**. Some layouts expose this under **Workspace → Functions**.
3. Choose **Create**.
4. Set the ID to `open_webui_guide`, the name to **Open WebUI Guide**, and paste the complete Function source.
5. Save and enable the Function, then reload the chat.

The Compose service has already mounted the guide package, knowledge, and adapters read-only. Select **Open WebUI Guide** in the model selector and ask `What is Open WebUI?`. The Pipe is deterministic and does not require an LLM provider.

For a standalone walkthrough suitable for sharing, including startup, manual installation, extension testing, troubleshooting, and reset instructions, use [Start the Open WebUI Guide PoC without an API key](docs/getting-started-without-api-key.md).

### Optional automated Function installation

If an administrator Open WebUI API key is available, PowerShell 7 can install the same Function through the local API:

```powershell
$env:OPEN_WEBUI_API_KEY = "<admin-api-key>"
./scripts/install-howto-function.ps1
```

The installer is idempotent. A second run makes no changes when the stored Function has the same name and source. If the source has changed, replacement must be explicit:

```powershell
./scripts/install-howto-function.ps1 -Update
```

You can alternatively pass the administrator API key explicitly:

```powershell
./scripts/install-howto-function.ps1 -ApiKey $env:OPEN_WEBUI_API_KEY
```

## Install the Getting started CTA

Load [openwebui/guide-extension](openwebui/guide-extension) as an unpacked Chrome or Edge extension, then reload the local Open WebUI page. The extension injects one persistent **Getting started** CTA and asks for confirmation without changing the current chat when cancelled.

The consent-gated runner validates source-generated recipes independently, preflights the full launch, shows visible progress, and lets Escape stop it before any later UI action. Valid assistant directives become local **Show me** and **Run example** controls; malformed and user-authored directive blocks remain inert. If **Open WebUI Guide** is unavailable, launch fails before starting a new chat. Use the [PoC runbook](docs/poc-runbook.md) for consolidated setup, acceptance verification, limitations, observability, and reset instructions. The [Guide Bridge instructions](openwebui/guide-extension/README.md) and [UI automation security](docs/ui-automation-security.md) document the component boundaries.

Authentication is disabled for this local baseline, and port 3000 is bound to the loopback interface rather than the local network. Changing authentication mode later requires a fresh Open WebUI data volume.

View logs or stop the service without deleting its data:

```powershell
docker compose logs -f open-webui
docker compose down
```

> **Destructive reset:** `docker compose down -v` permanently deletes the local Open WebUI volume, including accounts, chats, settings, and uploaded data.

The Hello World provider is a disposable connectivity check, not an agent or LLM. See [Open WebUI integration](openwebui/README.md) for replacing it with a real model provider.

## Design principles

- Prefer the official Open WebUI container over a source fork.
- Keep domain logic outside Open WebUI extension code.
- Keep process structure separate from explanatory knowledge.
- Add frameworks and infrastructure only when experiments demonstrate a need.
- Treat all Open WebUI Functions and Tools as trusted server-side code.
